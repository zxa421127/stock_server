# -*- coding: utf-8 -*-
"""Generate a machine-readable audit of the active administrator API specs."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from services.market_interface_spec_service import MarketInterfaceSpecService


def build_audit_report(service: MarketInterfaceSpecService) -> dict[str, Any]:
    service.ensure_seed_release()
    specs = service.list_effective_specs()
    providers = Counter(str(row.get("provider") or "") for row in specs)
    categories = Counter(str(row.get("category") or "其他/未分类") for row in specs)
    interfaces: list[dict[str, Any]] = []
    for spec in specs:
        inputs = list(spec.get("input_params") or [])
        outputs = list(spec.get("output_fields") or [])
        input_names = [str(row.get("name") or "") for row in inputs]
        sample_description_count = sum(
            1 for row in outputs
            if "项目响应样例字段" in str(row.get("description") or "")
        )
        unsupported_unknown_count = sum(
            1 for row in outputs
            if str(row.get("normalized_type") or "").lower() == "unknown"
            and str(row.get("official_type") or "").strip().lower() not in {"", "none", "unknown"}
        )
        interfaces.append({
            "provider": spec.get("provider"),
            "category": spec.get("category") or "其他/未分类",
            "api_name": spec.get("api_name"),
            "title": spec.get("title"),
            "official_verified": bool(spec.get("official_verified")),
            "spec_status": spec.get("spec_status"),
            "input_count": len(inputs),
            "output_count": len(outputs),
            "has_forbidden_fields_input": "fields" in input_names,
            "official_url": spec.get("official_url"),
            "source_kind": spec.get("source_kind"),
            "sample_description_count": sample_description_count,
            "unsupported_unknown_count": unsupported_unknown_count,
        })
    official_verified = sum(1 for row in specs if row.get("official_verified"))
    tushare_pending = sum(
        1 for row in specs
        if row.get("provider") == "tushare" and not row.get("official_verified")
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_version": service.current_version(),
        "total": len(specs),
        "providers": dict(sorted(providers.items())),
        "categories": dict(sorted(categories.items())),
        "official_verified": official_verified,
        "tushare_pending_official": tushare_pending,
        "incomplete": sum(1 for row in specs if row.get("spec_status") != "complete"),
        "missing_input_count": sum(1 for row in specs if not row.get("input_params")),
        "missing_output_count": sum(
            1 for row in specs
            if not row.get("output_fields") and str(row.get("output_schema_mode") or "fixed") != "dynamic"
        ),
        "forbidden_fields_input_count": sum(
            1 for row in interfaces if row["has_forbidden_fields_input"]
        ),
        "catalog_seed_count": sum(
            1 for row in interfaces if row.get("provider") == "tushare" and row.get("source_kind") == "catalog_seed"
        ),
        "sample_description_count": sum(row["sample_description_count"] for row in interfaces),
        "unsupported_unknown_count": sum(row["unsupported_unknown_count"] for row in interfaces),
        "interfaces": interfaces,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="审计当前管理员接口规格")
    parser.add_argument("--output", help="将JSON报告写入指定文件")
    parser.add_argument(
        "--require-official-tushare",
        action="store_true",
        help="当仍有TuShare接口未完成官网确认时返回非零状态",
    )
    args = parser.parse_args()
    report = build_audit_report(MarketInterfaceSpecService())
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    invalid = bool(
        report["incomplete"] or report["missing_output_count"]
        or report["forbidden_fields_input_count"]
        or report["sample_description_count"]
        or report["unsupported_unknown_count"]
    )
    if args.require_official_tushare and report["tushare_pending_official"]:
        invalid = True
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
