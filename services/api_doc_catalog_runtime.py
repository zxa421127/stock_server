# -*- coding: utf-8 -*-
"""Build the API-document catalog from the published interface specifications.

``services.api_doc_catalog`` remains a compatibility seed containing examples and
presentation-only data.  Runtime parameter definitions, official descriptions,
permissions and limits are overlaid from ``interface_specs/current.json`` so the
API documentation and interface tester do not drift apart.
"""
from __future__ import annotations

from copy import deepcopy
import json
import logging
from pathlib import Path
from typing import Any

from services.api_doc_catalog import (
    FULL_API_DOCS as _SEED_DOCS,
    FULL_API_DOCS_VERSION as _SEED_VERSION,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SPEC_ROOT = _PROJECT_ROOT / "interface_specs"


def _read_current_specs() -> tuple[str, list[dict[str, Any]]]:
    pointer = json.loads((_SPEC_ROOT / "current.json").read_text(encoding="utf-8"))
    version = str(pointer.get("version") or "").strip()
    if not version:
        raise ValueError("interface_specs/current.json 缺少 version")
    release_dir = _SPEC_ROOT / "releases" / version
    spec_name = str(pointer.get("spec_file") or "effective_specs.json")
    payload = json.loads((release_dir / spec_name).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("interfaces") or payload.get("specs") or []
    if not isinstance(payload, list):
        raise ValueError("正式接口规格必须是列表")
    return version, [item for item in payload if isinstance(item, dict)]


def _first_preset_values(spec: dict[str, Any]) -> dict[str, Any]:
    for preset in spec.get("presets") or []:
        if isinstance(preset, dict) and isinstance(preset.get("params"), dict):
            return dict(preset["params"])
    return {}


def _official_description(spec: dict[str, Any], seed: dict[str, Any]) -> str:
    lines = [str(spec.get("description") or seed.get("description") or "").strip()]
    permission = str(spec.get("permission_text") or "").strip()
    limit_text = str(spec.get("limit_text") or "").strip()
    official_url = str(spec.get("official_url") or seed.get("official_url") or "").strip()
    if permission:
        lines.append(permission)
    elif spec.get("permission_label"):
        lines.append(f"权限：{spec['permission_label']}")
    if limit_text:
        lines.append(limit_text)
    if official_url:
        lines.append(f"官方文档：{official_url}")
    return "\n".join(line for line in lines if line)


def _overlay_doc(seed: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(seed)
    preset_values = _first_preset_values(spec)
    seed_params = {
        str(item.get("name") or ""): item
        for item in seed.get("params") or []
        if isinstance(item, dict)
    }
    params: list[dict[str, Any]] = []
    for item in sorted(
        (entry for entry in spec.get("input_params") or [] if isinstance(entry, dict)),
        key=lambda entry: int(entry.get("source_order") or 0),
    ):
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        previous = seed_params.get(name, {})
        example = item.get("example")
        if example in (None, ""):
            example = preset_values.get(name, previous.get("example", ""))
        params.append(
            {
                "name": name,
                "type": str(item.get("official_type") or item.get("normalized_type") or "string"),
                "required": "Y" if bool(item.get("required")) else "N",
                "example": "" if example is None else str(example),
                "description": str(item.get("description") or ""),
            }
        )

    for key in (
        "provider",
        "api_name",
        "title",
        "category",
        "category_sort_order",
        "sort_order",
        "method",
        "base_path",
        "scope",
        "official_url",
    ):
        value = spec.get(key)
        if value not in (None, ""):
            result[key] = value
    result["params"] = params
    result["description"] = _official_description(spec, seed)
    if spec.get("permission_text"):
        result["permission_label"] = str(spec["permission_text"])
    elif spec.get("permission_label"):
        result["permission_label"] = str(spec["permission_label"])
    result["official_verified"] = bool(spec.get("official_verified"))
    result["spec_status"] = str(spec.get("spec_status") or "")
    result["source_kind"] = str(spec.get("source_kind") or "")
    return result


def build_runtime_catalog() -> tuple[list[dict[str, Any]], str]:
    docs = [deepcopy(item) for item in _SEED_DOCS]
    try:
        version, specs = _read_current_specs()
    except Exception as exc:
        logging.error("[API文档] 正式规格读取失败，使用兼容目录种子: %s", exc)
        return docs, _SEED_VERSION

    by_key = {
        (str(item.get("provider") or ""), str(item.get("api_name") or "")): item
        for item in specs
    }
    overlaid: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for seed in docs:
        key = (str(seed.get("provider") or ""), str(seed.get("api_name") or ""))
        spec = by_key.get(key)
        overlaid.append(_overlay_doc(seed, spec) if spec else seed)
        seen.add(key)

    # A newly published interface may not exist in the old compatibility seed.
    for key, spec in by_key.items():
        if key in seen:
            continue
        base_path = str(spec.get("base_path") or "")
        seed = {
            "provider": key[0],
            "api_name": key[1],
            "title": str(spec.get("title") or key[1]),
            "category": str(spec.get("category") or "其他"),
            "category_description": "",
            "category_sort_order": int(spec.get("category_sort_order") or 999),
            "sort_order": int(spec.get("sort_order") or 999),
            "method": str(spec.get("method") or "GET"),
            "path": base_path,
            "base_path": base_path,
            "scope": str(spec.get("scope") or ""),
            "permission_label": str(spec.get("permission_label") or ""),
            "description": "",
            "params": [],
            "request_example": f"GET {base_path}" if base_path else "",
            "response_example": "",
            "official_url": str(spec.get("official_url") or ""),
            "test_status": "未测试",
            "test_count": 0,
            "is_callable": True,
            "has_data": False,
        }
        overlaid.append(_overlay_doc(seed, spec))

    overlaid.sort(
        key=lambda item: (
            int(item.get("category_sort_order") or 999),
            int(item.get("sort_order") or 999),
            str(item.get("provider") or ""),
            str(item.get("api_name") or ""),
        )
    )
    return overlaid, f"{_SEED_VERSION}+{version}"


FULL_API_DOCS, FULL_API_DOCS_VERSION = build_runtime_catalog()
FULL_API_DOCS_TOTAL = len(FULL_API_DOCS)
