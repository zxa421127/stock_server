from __future__ import annotations

import time

from auto_tests.common import Result, load_tokens, request, save_report
from services.market_data_service import get_provider_catalog


def _request_with_retry(path: str, token: str, attempts: int = 3):
    last = (500, {"success": False, "data": [], "msg": "未执行"}, 0.0)
    for index in range(max(attempts, 1)):
        last = request(path, token)
        status = last[0]
        if status < 500:
            return last
        if index + 1 < attempts:
            time.sleep(1 + index * 2)
    return last


def main() -> int:
    results = []
    try:
        token = load_tokens()["special"]
        status, payload, _ = _request_with_retry("/api/v1/market/providers", token)
        providers = {
            str(item.get("code") or "").strip()
            for item in (payload.get("data", []) if isinstance(payload, dict) else [])
            if item.get("code")
        } if status == 200 else set()
        required_ok = {"tushare", "kaipanla"}.issubset(providers)
        results.append(Result(
            "catalog",
            "特殊套餐可见数据源",
            status == 200 and required_ok,
            "至少包含tushare和kaipanla",
            f"HTTP {status}: {sorted(providers)}",
        ))

        # A failed provider-discovery request must never turn into a misleading
        # "0 expected / 0 actual" success report.
        if status != 200 or not providers:
            results.append(Result(
                "catalog",
                "数据接口总数",
                False,
                "当前代码目录接口数（大于0）",
                "无法统计：数据源接口返回失败",
            ))
            save_report("04_来源与接口数量测试", results)
            return 1

        expected = {provider: len(get_provider_catalog(provider)) for provider in providers}
        total = 0
        all_catalogs_ok = True
        for provider, count in sorted(expected.items()):
            catalog_status, catalog_payload, _ = _request_with_retry(
                f"/api/v1/market/{provider}/catalog", token
            )
            actual = int(catalog_payload.get("count", -1)) if isinstance(catalog_payload, dict) else -1
            total += max(actual, 0)
            passed = catalog_status == 200 and actual == count
            all_catalogs_ok = all_catalogs_ok and passed
            results.append(Result(
                "catalog",
                f"{provider}接口数量",
                passed,
                f"HTTP 200且{count}个",
                f"HTTP {catalog_status}且{actual}个",
            ))
        target = sum(expected.values())
        results.append(Result(
            "catalog",
            "数据接口总数",
            all_catalogs_ok and total == target and target > 0,
            f"{target}个",
            f"{total}个",
        ))
    except Exception as exc:
        results.append(Result("catalog", "目录数量执行", False, "脚本正常完成", "异常", str(exc)))
    save_report("04_来源与接口数量测试", results)
    return 0 if all(item.passed for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
