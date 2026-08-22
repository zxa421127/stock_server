# -*- coding: utf-8 -*-
"""直接测试开盘啦上游原始 JSON，不经过业务路由和历史降级。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from integrations.kaipanla import evaluate_kaipanla_business_status
from integrations.kaipanla.morning_bidding import get_morning_bidding_page_raw


def build_debug_summary(
    *,
    raw: Any,
    error: str | None,
    dataframe_rows: int,
    public_params: dict[str, Any],
) -> dict[str, Any]:
    """Build a credential-free summary shared by tests and CLI output."""
    status = evaluate_kaipanla_business_status(raw)
    payload = raw if isinstance(raw, dict) else {}
    info = payload.get("info")
    info_count = len(info) if isinstance(info, list) else 0
    return {
        "安全请求参数": dict(public_params),
        "错误信息": error,
        "DataFrame行数": int(dataframe_rows),
        "原始返回类型": type(raw).__name__,
        "业务成功": bool(status.success and error is None),
        "状态协议": status.protocol,
        "状态码": status.code,
        "业务消息": error or status.message,
        "原始info条数": info_count,
        "day": payload.get("day"),
        "time": payload.get("time"),
        "status": payload.get("status"),
        "errcode": payload.get("errcode"),
        "ret": payload.get("ret"),
        "msg": payload.get("msg"),
    }


def main() -> int:
    output_dir = Path("data/debug_kaipanla")
    output_dir.mkdir(parents=True, exist_ok=True)

    frame, raw, error, public_params = get_morning_bidding_page_raw(
        order=1,
        st=20,
        index=0,
        pid_type=0,
        b_type=4,
    )
    summary = build_debug_summary(
        raw=raw,
        error=error,
        dataframe_rows=len(frame),
        public_params=public_params,
    )

    print("=" * 70)
    print("开盘啦原始接口测试")
    print("=" * 70)
    for key, value in summary.items():
        print(f"{key}： {value}")

    if isinstance(raw, dict):
        print("原始JSON顶层字段：", list(raw.keys()))
        info = raw.get("info")
        if isinstance(info, list) and info:
            print("\n第一条最原始记录：")
            print(json.dumps(info[0], ensure_ascii=False, indent=2, default=str))

    raw_file = output_dir / "kaipanla_raw_page.json"
    raw_file.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    mapped_file = output_dir / "kaipanla_mapped_table.csv"
    frame.to_csv(mapped_file, index=False, encoding="utf-8-sig")
    summary_file = output_dir / "kaipanla_debug_summary.json"
    summary_file.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print("\n已保存原始JSON：", raw_file)
    print("已保存映射表格：", mapped_file)
    print("已保存状态摘要：", summary_file)

    return 0 if summary["业务成功"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
