from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from auto_tests.common import BASE_URL, RESULT_DIR, load_tokens, message, request
from tools.interface_tester import (
    InterfaceTester,
    build_sample_param_candidates,
)
from integrations.market_data.tushare.latest_available import is_latest_available_api

REQUEST_TIMEOUT_SECONDS = int(os.getenv("STOCK_TEST_REQUEST_TIMEOUT_SECONDS", "75"))
INTERVAL_SECONDS = float(os.getenv("STOCK_TEST_INTERVAL_SECONDS", "0.20"))
BYPASS_CACHE = os.getenv("STOCK_TEST_BYPASS_CACHE", "1").strip().lower() not in {
    "0", "false", "no", "off"
}
TRANSIENT_RETRIES = max(0, int(os.getenv("STOCK_TEST_TRANSIENT_RETRIES", "2")))
TRANSIENT_BACKOFF_SECONDS = [2.0, 5.0, 10.0]
AUTO_CONFIRM = os.getenv("STOCK_TEST_AUTO_CONFIRM", "").strip().upper() in {"YES", "Y", "TRUE", "1"}
CATALOG_RETRIES = max(1, int(os.getenv("STOCK_TEST_CATALOG_RETRIES", "3")))



def evidence_rows(payload: dict, limit: int = 3) -> list[dict]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    return [row for row in data[:limit] if isinstance(row, dict)]


def _text(payload: dict) -> str:
    return message(payload).lower()


def classify(status: int | str, payload: dict, *, lifecycle: str = "active") -> tuple[str, bool, bool, str]:
    """Return verdict, has_data, callable, problem_category."""
    data = payload.get("data")
    count = payload.get("count")
    actual_count = len(data) if isinstance(data, list) else 0
    try:
        declared_count = int(count)
    except (TypeError, ValueError):
        declared_count = actual_count

    if status == 200 and payload.get("success") is True and declared_count > 0 and actual_count > 0:
        freshness = payload.get("freshness") if isinstance(payload.get("freshness"), dict) else {}
        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        fallback_used = bool(freshness.get("fallback_used") or source.get("fallback_used"))
        if fallback_used:
            return "接口正常，已返回最近可用数据", True, True, "正常可用"
        return "成功且取得数据", True, True, "正常可用"
    if status == 200:
        if lifecycle == "historical":
            return "历史/停更接口：本次无数据", False, True, "历史接口或测试日期无数据"
        return "接口可调用但没有匹配数据", False, True, "参数或数据覆盖待确认"

    text = _text(payload)
    if status in {401, 402, 403}:
        return "账户或套餐权限失败", False, False, "网站账户权限"
    if status == 429:
        return "触发限流", False, False, "网站限流"
    if status == 400:
        return "请求参数或接口契约不符合", False, False, "请求参数或接口契约"
    if status == 413:
        return "单次响应规模超过安全上限", False, False, "响应规模超限（测试参数需收窄）"
    if status == 502:
        if "无接口权限" in text or "api not allowed" in text:
            return "上游接口权限受限", False, False, "中转Token未开通"
        if "api not configured" in text:
            return "中转未配置官方接口", False, False, "中转路由未配置"
        if "no upstream available" in text:
            return "中转上游临时不可用", False, False, "中转临时故障"
        if "正确的接口名" in text or "不支持" in text:
            return "当前中转不支持", False, False, "中转明确不支持"
        if "timed out" in text or "timeout" in text:
            return "上游响应超时", False, False, "中转或上游性能"
        return "上游数据源失败", False, False, "中转或上游异常"
    return "服务器或网络异常", False, False, "网络或服务器异常"


def _is_clear_nonempty_blocker(status: int | str, payload: dict) -> bool:
    """Do not waste extra candidate calls after a clear permission/route error."""
    # 400/413 are often acceptance-sample problems rather than broken routes.
    # When a bounded secondary candidate exists, allow the caller to try it.
    if status in {400, 413}:
        return False
    if status != 502:
        return status not in {200}
    text = _text(payload)
    return any(token in text for token in (
        "api not allowed",
        "无接口权限",
        "api not configured",
        "正确的接口名",
        "不支持",
    ))


def _is_transient_upstream_failure(status: int | str, payload: dict) -> bool:
    text = _text(payload)
    return status in {502, 503} and (
        "no upstream available" in text
        or "temporarily unavailable" in text
        or "connection reset" in text
    )


def _dynamic_candidates(
    provider: str,
    api_name: str,
    previous_payloads: dict[str, dict],
) -> list[dict[str, Any]]:
    # The production provider now resolves latest-available data, including the
    # ccass_hold -> ccass_hold_detail dependency.  The acceptance test should
    # exercise that same path instead of manufacturing its own detail sample.
    candidates = build_sample_param_candidates(provider, api_name)
    # Deduplicate bounded candidates.
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        marker = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
        if marker not in seen:
            seen.add(marker)
            unique.append(dict(item))
    return unique


def _call_path(provider: str, api_name: str) -> str:
    if BYPASS_CACHE:
        return f"/api/v1/market/cache/query/{provider}/{api_name}"
    return f"/api/v1/market/{provider}/{api_name}"


def main() -> int:
    tokens = load_tokens()
    catalog_tester = InterfaceTester(BASE_URL, tokens["special"])
    providers: list[str] = []
    for retry_index in range(CATALOG_RETRIES):
        providers = catalog_tester.providers()
        if providers:
            break
        if retry_index + 1 < CATALOG_RETRIES:
            delay = 1 + retry_index * 2
            print(f"数据源目录暂时不可用，{delay}秒后重试")
            time.sleep(delay)
    if not providers:
        print("读取数据源失败：未发现任何数据源。本次不生成0接口报告。")
        return 1

    refs: list[tuple[str, str, dict[str, Any]]] = []
    for provider in providers:
        rows = catalog_tester.catalog(provider)
        if not rows:
            print(f"读取 {provider} 接口目录失败或目录为空。本次不生成不完整报告。")
            return 1
        for row in rows:
            if row.get("api_name"):
                refs.append((provider, str(row["api_name"]), dict(row)))
    if not refs:
        print("接口目录为空。本次不生成0接口报告。")
        return 1

    mode = "强制上游（管理员旁路缓存）" if BYPASS_CACHE else "生产缓存路由"
    data_token = tokens["admin"] if BYPASS_CACHE else tokens["special"]
    print(f"服务：{BASE_URL}")
    print(f"发现 {len(providers)} 个数据来源、{len(refs)} 个数据接口。")
    print(f"测试模式：{mode}")
    print("严格数据规则：只有HTTP 200、success=true、count>0且data非空才算取得数据。")
    print("同时单独统计接口连通性，HTTP 200空数据不再等同于接口损坏。")
    print("稀疏/历史接口可能尝试少量备用参数；503会做有限退避重试。")
    if not AUTO_CONFIRM:
        if input(f"将真实调用全部 {len(refs)} 个接口并消耗上游额度，输入 YES 继续：").strip() != "YES":
            print("已取消。")
            return 0
    else:
        print(f"自动确认：将真实调用全部 {len(refs)} 个接口。")

    rows: list[dict[str, Any]] = []
    previous_payloads: dict[str, dict] = {}
    for index, (provider, api_name, meta) in enumerate(refs, 1):
        lifecycle = str(meta.get("lifecycle") or "active")
        candidates = _dynamic_candidates(provider, api_name, previous_payloads)
        attempts: list[dict[str, Any]] = []
        final_status: int | str = "NETWORK_ERROR"
        final_payload: dict[str, Any] = {"success": False, "data": [], "msg": "未执行"}
        final_params: dict[str, Any] = candidates[0] if candidates else {}
        started_total = time.perf_counter()

        for candidate_index, params in enumerate(candidates, 1):
            retry_index = 0
            while True:
                attempt_started = time.perf_counter()
                try:
                    status, payload, request_ms = request(
                        _call_path(provider, api_name),
                        data_token,
                        "POST",
                        params,
                        REQUEST_TIMEOUT_SECONDS,
                    )
                except Exception as exc:
                    status = "NETWORK_ERROR"
                    payload = {"success": False, "data": [], "msg": str(exc)}
                    request_ms = round((time.perf_counter() - attempt_started) * 1000, 1)

                freshness = payload.get("freshness") if isinstance(payload.get("freshness"), dict) else {}
                attempts.append({
                    "候选序号": candidate_index,
                    "重试序号": retry_index,
                    "参数": params,
                    "HTTP状态": status,
                    "数据条数": len(payload.get("data") or []) if isinstance(payload.get("data"), list) else 0,
                    "耗时毫秒": request_ms,
                    "消息": message(payload),
                    "缓存来源": payload.get("source") or {},
                    "请求交易日": freshness.get("requested_trade_date"),
                    "实际数据日期": freshness.get("actual_trade_date"),
                    "是否回退最近数据": bool(freshness.get("fallback_used")),
                    "数据新鲜度": freshness.get("data_freshness"),
                })
                final_status, final_payload, final_params = status, payload, params

                if _is_transient_upstream_failure(status, payload) and retry_index < TRANSIENT_RETRIES:
                    delay = TRANSIENT_BACKOFF_SECONDS[min(retry_index, len(TRANSIENT_BACKOFF_SECONDS) - 1)]
                    print(f"  {provider}.{api_name} 临时503，{delay:.0f}秒后重试")
                    time.sleep(delay)
                    retry_index += 1
                    continue
                break

            data = final_payload.get("data")
            actual_count = len(data) if isinstance(data, list) else 0
            if final_status == 200 and final_payload.get("success") is True and actual_count > 0:
                break
            if _is_clear_nonempty_blocker(final_status, final_payload):
                break
            # Only HTTP 200 empty results proceed to the next bounded candidate.

        verdict, has_data, callable_ok, problem_category = classify(
            final_status,
            final_payload,
            lifecycle=lifecycle,
        )
        data = final_payload.get("data") if isinstance(final_payload, dict) else []
        actual_count = len(data) if isinstance(data, list) else 0
        source = final_payload.get("source") if isinstance(final_payload, dict) else {}
        source = source if isinstance(source, dict) else {}
        freshness = final_payload.get("freshness") if isinstance(final_payload, dict) else {}
        freshness = freshness if isinstance(freshness, dict) else {}
        fallback_used = bool(freshness.get("fallback_used") or source.get("fallback_used"))
        requested_trade_date = freshness.get("requested_trade_date") or source.get("requested_trade_date")
        actual_trade_date = freshness.get("actual_trade_date") or source.get("actual_trade_date")
        data_freshness = freshness.get("data_freshness") or source.get("data_freshness")
        fallback_attempt_count = (
            freshness.get("fallback_attempt_count")
            if freshness.get("fallback_attempt_count") is not None
            else source.get("fallback_attempt_count", 0)
        )
        evidence = evidence_rows(final_payload)
        row = {
            "序号": index,
            "数据来源": provider,
            "接口": api_name,
            "接口生命周期": lifecycle,
            "测试说明": str(meta.get("test_note") or ""),
            "是否取得数据": "是" if has_data else "否",
            "接口是否可调用": "是" if callable_ok else "否",
            "结论": verdict,
            "问题分类": problem_category,
            "HTTP状态": final_status,
            "数据条数": actual_count,
            "总耗时毫秒": round((time.perf_counter() - started_total) * 1000, 1),
            "上游耗时毫秒": source.get("upstream_elapsed_ms", ""),
            "缓存模式": mode,
            "缓存命中": source.get("cache_hit", False),
            "缓存是否陈旧": source.get("cache_stale", False),
            "消息": message(final_payload),
            "最终请求参数": final_params,
            "候选参数尝试次数": len(attempts),
            "请求交易日": requested_trade_date,
            "实际数据日期": actual_trade_date,
            "是否回退最近数据": fallback_used,
            "数据新鲜度": data_freshness,
            "日期回退尝试次数": fallback_attempt_count or 0,
            "全部尝试": attempts,
            "数据证据_前3条": evidence,
        }
        rows.append(row)
        if isinstance(final_payload, dict):
            previous_payloads[api_name] = final_payload
        mark = "回退" if (has_data and fallback_used) else ("通过" if has_data else ("可调用" if callable_ok else "未通过"))
        print(
            f"[{index}/{len(refs)}] [{mark}] {provider}.{api_name} | "
            f"{verdict} | 数据={actual_count}条 | 尝试={len(attempts)}"
        )
        time.sleep(INTERVAL_SECONDS)

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    json_path = RESULT_DIR / f"全部真实数据接口_{stamp}.json"
    csv_path = RESULT_DIR / f"全部真实数据接口_{stamp}.csv"
    data_passed = sum(row["是否取得数据"] == "是" for row in rows)
    callable_count = sum(row["接口是否可调用"] == "是" for row in rows)
    fallback_data_count = sum(
        row["是否取得数据"] == "是" and bool(row.get("是否回退最近数据"))
        for row in rows
    )
    direct_data_count = data_passed - fallback_data_count
    latest_target_rows = [
        row for row in rows
        if row["数据来源"] == "tushare" and is_latest_available_api(row["接口"])
    ]
    latest_target_current_count = sum(
        row["是否取得数据"] == "是" and not bool(row.get("是否回退最近数据"))
        for row in latest_target_rows
    )
    latest_target_fallback_count = sum(
        row["是否取得数据"] == "是" and bool(row.get("是否回退最近数据"))
        for row in latest_target_rows
    )
    latest_target_empty_count = sum(row["是否取得数据"] != "是" for row in latest_target_rows)
    categories: dict[str, int] = {}
    for row in rows:
        categories[row["问题分类"]] = categories.get(row["问题分类"], 0) + 1
    summary = {
        "报告版本": 3,
        "生成时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "测试地址": BASE_URL,
        "测试模式": mode,
        "严格成功标准": "HTTP 200 + success=true + count>0 + data非空",
        "接口连通标准": "HTTP 200 + success=true，允许data为空",
        "总接口数": len(rows),
        "取得数据接口数": data_passed,
        "未取得数据接口数": len(rows) - data_passed,
        "可调用接口数": callable_count,
        "当前日期或原请求直接取得数据接口数": direct_data_count,
        "回退最近可用日期后取得数据接口数": fallback_data_count,
        "不可调用接口数": len(rows) - callable_count,
        "最新数据回退目标接口数": len(latest_target_rows),
        "目标接口当前日期已有数据数": latest_target_current_count,
        "目标接口回退后有数据数": latest_target_fallback_count,
        "目标接口回退后仍为空数": latest_target_empty_count,
        "问题分类统计": categories,
        "结果": rows,
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        fields = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key in ("最终请求参数", "全部尝试", "数据证据_前3条"):
                out[key] = json.dumps(out[key], ensure_ascii=False)
            writer.writerow(out)

    print("\n真实数据测试汇总")
    print(f"总接口：{len(rows)}")
    print(f"接口可调用：{callable_count}")
    print(f"当前日期或原请求直接取得数据：{direct_data_count}")
    print(f"回退最近可用日期后取得数据：{fallback_data_count}")
    print(f"真正不可调用：{len(rows) - callable_count}")
    print(f"成功取得数据合计：{data_passed}")
    print(f"未取得数据：{len(rows) - data_passed}")
    print(
        "最新数据回退目标接口："
        f"当前日期有数据={latest_target_current_count}，"
        f"回退后有数据={latest_target_fallback_count}，"
        f"仍为空={latest_target_empty_count}"
    )
    for key, value in sorted(categories.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {key}: {value}")
    print(f"JSON详细证据：{json_path}")
    print(f"CSV汇总：{csv_path}")
    # This is an evidence command, not a unit test.  Upstream permission/no-data
    # findings should not make the batch file look like a local code failure.
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
