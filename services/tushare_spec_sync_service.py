# -*- coding: utf-8 -*-
"""Offline/administrator-driven synchronization of Tushare official specs."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

import requests

from services.market_interface_spec_service import MarketInterfaceSpecService


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _normalize_type(value: str) -> str:
    text = (value or "").strip().lower()
    if text in {"int", "integer", "long"}:
        return "integer"
    if text in {"float", "double", "decimal", "number"}:
        return "number"
    if text in {"bool", "boolean"}:
        return "boolean"
    if text in {"list", "array"}:
        return "array"
    if text in {"dict", "object", "json"}:
        return "object"
    if text in {"none", "", "unknown"}:
        return "unknown"
    return "string"


def _doc_id(url: str) -> int | None:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("doc_id") or []
    candidate = values[0] if values else ""
    if not candidate:
        match = re.search(r"/documents/(\d+)\.md(?:$|[?#])", parsed.path)
        candidate = match.group(1) if match else ""
    try:
        return int(candidate) if candidate else None
    except (TypeError, ValueError):
        return None




def _canonical_text_hash(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _semantic_document_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": raw.get("provider"),
        "api_name": raw.get("api_name"),
        "official_doc_id": raw.get("official_doc_id"),
        "official_title": raw.get("official_title"),
        "official_description": raw.get("official_description"),
        "permission_text": raw.get("permission_text"),
        "limit_text": raw.get("limit_text"),
        "inputs": raw.get("inputs") or [],
        "outputs": raw.get("outputs") or [],
        "output_schema_mode": raw.get("output_schema_mode") or "fixed",
        "dynamic_output_reason": raw.get("dynamic_output_reason") or "",
    }


def _attach_document_hashes(raw: dict[str, Any], source_text: str) -> dict[str, Any]:
    raw["raw_content_hash"] = _canonical_text_hash(source_text)
    raw["semantic_spec_hash"] = hashlib.sha256(
        json.dumps(_semantic_document_payload(raw), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    # Backward-compatible alias.  Unlike the previous implementation this is
    # stable because fetch timestamps are excluded.
    raw["source_hash"] = raw["semantic_spec_hash"]
    return raw


class _DocumentParser(HTMLParser):
    BLOCK_TAGS = {"h1", "h2", "h3", "h4", "p", "li", "pre"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._tag_stack: list[str] = []
        self._block_tag = ""
        self._block_parts: list[str] = []
        self.blocks: list[tuple[str, str]] = []
        self.tables: list[dict[str, Any]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None
        self._last_heading = ""

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        self._tag_stack.append(tag)
        if tag in self.BLOCK_TAGS:
            self._block_tag = tag
            self._block_parts = []
        elif tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell_parts = []

    def handle_data(self, data: str):
        text = data.strip()
        if not text:
            return
        if self._cell_parts is not None:
            self._cell_parts.append(text)
        if self._block_tag:
            self._block_parts.append(text)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in {"td", "th"} and self._cell_parts is not None and self._row is not None:
            self._row.append(" ".join(self._cell_parts).strip())
            self._cell_parts = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(cell for cell in self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append({"heading": self._last_heading, "rows": self._table})
            self._table = None
        if tag in self.BLOCK_TAGS and self._block_tag == tag:
            text = " ".join(self._block_parts).strip()
            if text:
                self.blocks.append((tag, text))
                if tag.startswith("h"):
                    self._last_heading = text
            self._block_tag = ""
            self._block_parts = []
        if self._tag_stack:
            for index in range(len(self._tag_stack) - 1, -1, -1):
                if self._tag_stack[index] == tag:
                    del self._tag_stack[index:]
                    break


def _normalize_header_cell(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip().lower()


def _header_index(header: list[str], aliases: tuple[str, ...]) -> int | None:
    normalized = [_normalize_header_cell(value) for value in header]
    for index, value in enumerate(normalized):
        if any(alias in value for alias in aliases):
            return index
    return None


def _find_parameter_table(tables: list[dict[str, Any]], *, output: bool) -> list[list[str]]:
    for table in tables:
        rows = table.get("rows") or []
        if not rows:
            continue
        header = list(rows[0])
        heading = _normalize_header_cell(str(table.get("heading") or ""))
        has_name_type = _header_index(header, ("名称",)) is not None and _header_index(header, ("类型",)) is not None
        if not has_name_type:
            continue
        if output:
            has_default = _header_index(header, ("默认显示", "默认输出")) is not None
            has_description = _header_index(header, ("描述", "说明")) is not None
            if has_default or ("输出" in heading and has_description):
                return rows
        else:
            has_required = _header_index(header, ("必选", "必填", "必须")) is not None
            if has_required or (("输入" in heading or "接口参数" in heading) and len(header) >= 3):
                return rows
    return []


def _parse_input_rows(table: list[list[str]]) -> list[dict[str, Any]]:
    if not table:
        return []
    header = table[0]
    name_index = _header_index(header, ("名称",))
    type_index = _header_index(header, ("类型",))
    required_index = _header_index(header, ("必选", "必填", "必须"))
    description_index = _header_index(header, ("描述", "说明"))
    if name_index is None or type_index is None or required_index is None:
        return []
    result: list[dict[str, Any]] = []
    for order, row in enumerate(table[1:], start=1):
        if max(name_index, type_index, required_index) >= len(row) or not row[name_index]:
            continue
        flag = row[required_index].strip()
        description = row[description_index].strip() if description_index is not None and description_index < len(row) else ""
        result.append({
            "name": row[name_index].strip(),
            "official_type": row[type_index].strip(),
            "required": flag.lower() in {"y", "yes", "是", "必填", "必须"},
            "official_required": flag,
            "description": description,
            "source_order": order,
        })
    return result


def _parse_output_rows(table: list[list[str]]) -> list[dict[str, Any]]:
    if not table:
        return []
    header = table[0]
    name_index = _header_index(header, ("名称",))
    type_index = _header_index(header, ("类型",))
    default_index = _header_index(header, ("默认显示", "默认输出"))
    description_index = _header_index(header, ("描述", "说明"))
    if name_index is None or type_index is None or description_index is None:
        return []
    inferred = default_index is None
    result: list[dict[str, Any]] = []
    for order, row in enumerate(table[1:], start=1):
        if max(name_index, type_index, description_index) >= len(row) or not row[name_index]:
            continue
        if default_index is None:
            flag = ""
            default_display = True
        else:
            flag = row[default_index].strip() if default_index < len(row) else ""
            default_display = flag.lower() in {"y", "yes", "是", "默认"}
        result.append({
            "name": row[name_index].strip(),
            "official_type": row[type_index].strip(),
            "default_display": default_display,
            "official_default_display": flag,
            "default_display_inferred": inferred,
            "description": row[description_index].strip(),
            "source_order": order,
        })
    return result

def parse_tushare_document_html(html: str, official_url: str) -> dict[str, Any]:
    parser = _DocumentParser()
    parser.feed(html or "")
    api_name = ""
    interface_index = -1
    for index, (_, text) in enumerate(parser.blocks):
        match = re.search(r"(?:接口名称|接口)[：:]\s*([A-Za-z0-9_]+)", text)
        if match:
            api_name = match.group(1).strip().lower()
            interface_index = index
            break
    title = ""
    if interface_index >= 0:
        for tag, text in reversed(parser.blocks[:interface_index]):
            if tag in {"h1", "h2", "h3"} and text not in {"数据接口", "Tushare数据"}:
                title = text
                break
    if not title:
        headings = [text for tag, text in parser.blocks if tag in {"h1", "h2", "h3"}]
        title = headings[-1] if headings else api_name
    input_table = _find_parameter_table(parser.tables, output=False)
    output_table = _find_parameter_table(parser.tables, output=True)
    output_schema_mode = "dynamic" if api_name == "pro_bar" and not output_table else "fixed"
    warnings: list[str] = []
    if not api_name:
        warnings.append("未识别接口英文名")
    if len(input_table) < 1:
        warnings.append("未识别输入参数表")
    if output_schema_mode == "fixed" and len(output_table) < 2:
        warnings.append("未识别输出参数表")

    inputs = _parse_input_rows(input_table)
    outputs = _parse_output_rows(output_table)
    detail_lines = []
    permission_text = ""
    limit_text = ""
    if interface_index >= 0:
        for tag, text in parser.blocks[interface_index + 1:]:
            if text in {"输入参数", "输出参数", "接口示例", "数据样例"}:
                if text == "输入参数":
                    break
            if tag == "p":
                detail_lines.append(text)
                if text.startswith(("调取说明", "权限")):
                    permission_text = text
                if "每次" in text or "单次" in text or "条数据" in text:
                    limit_text = text
    raw = {
        "provider": "tushare",
        "api_name": api_name,
        "official_doc_id": _doc_id(official_url),
        "official_url": official_url,
        "official_title": title,
        "official_description": "\n".join(detail_lines),
        "permission_text": permission_text,
        "limit_text": limit_text,
        "inputs": inputs,
        "outputs": outputs,
        "output_schema_mode": output_schema_mode,
        "dynamic_output_reason": (
            "pro_bar为TuShare Python SDK动态计算接口，返回字段随asset、freq和ma参数变化，官网未提供固定输出参数表。"
            if output_schema_mode == "dynamic" else ""
        ),
        "source_fetched_at": datetime.now().isoformat(timespec="seconds"),
        "parse_warnings": warnings,
    }
    return _attach_document_hashes(raw, html)



def _markdown_section(text: str, start_label: str, end_labels: tuple[str, ...]) -> str:
    start = re.search(rf"(?:\*\*)?{re.escape(start_label)}(?:\*\*)?", text, flags=re.I)
    if not start:
        return ""
    tail = text[start.end():]
    end_positions = []
    for label in end_labels:
        match = re.search(rf"(?:\*\*)?{re.escape(label)}(?:\*\*)?", tail, flags=re.I)
        if match:
            end_positions.append(match.start())
    return tail[:min(end_positions)] if end_positions else tail


def _markdown_section_any(text: str, start_labels: tuple[str, ...], end_labels: tuple[str, ...]) -> str:
    starts: list[tuple[int, str]] = []
    for label in start_labels:
        match = re.search(rf"(?:\*\*)?{re.escape(label)}(?:\*\*)?", text, flags=re.I)
        if match:
            starts.append((match.start(), label))
    if not starts:
        return ""
    _, selected = min(starts, key=lambda value: value[0])
    return _markdown_section(text, selected, end_labels)


def _parse_compact_markdown_table(section: str, *, role: str) -> list[list[str]]:
    """Parse TuShare machine Markdown whose whole table is collapsed to one line."""
    compact = re.sub(r"\s+", " ", section or "").strip()
    if not compact or "名称" not in compact or "类型" not in compact:
        return []
    input_role = role == "input"
    if input_role:
        header_match = re.search(r"名称\s*\|\s*类型\s*\|\s*(必选|必填|必须)\s*\|\s*(描述|说明)", compact, flags=re.I)
        if not header_match:
            return []
        row_pattern = re.compile(
            r"(?P<name>[A-Za-z][A-Za-z0-9_]*)\s*\|\s*"
            r"(?P<type>[A-Za-z][A-Za-z0-9_./+\-]*)\s*\|\s*"
            r"(?P<flag>Y|N|YES|NO|是|否|必填|必须|可选)\s*\|\s*",
            flags=re.I,
        )
        matches = list(row_pattern.finditer(compact))
        if not matches:
            return []
        rows: list[list[str]] = [["名称", "类型", header_match.group(1), header_match.group(2)]]
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(compact)
            description = compact[match.end():end].strip(" |-")
            rows.append([match.group("name").strip(), match.group("type").strip(), match.group("flag").strip(), description])
        return rows

    default_header = re.search(r"名称\s*\|\s*类型\s*\|\s*(默认显示|默认输出)\s*\|\s*(描述|说明)", compact, flags=re.I)
    if default_header:
        row_pattern = re.compile(
            r"(?P<name>[A-Za-z][A-Za-z0-9_]*)\s*\|\s*"
            r"(?P<type>[A-Za-z][A-Za-z0-9_./+\-]*)\s*\|\s*"
            r"(?P<flag>Y|N|YES|NO|是|否|默认)\s*\|\s*",
            flags=re.I,
        )
        matches = list(row_pattern.finditer(compact))
        if not matches:
            return []
        rows = [["名称", "类型", default_header.group(1), default_header.group(2)]]
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(compact)
            description = compact[match.end():end].strip(" |-")
            rows.append([match.group("name").strip(), match.group("type").strip(), match.group("flag").strip(), description])
        return rows

    three_header = re.search(r"名称\s*\|\s*类型\s*\|\s*(描述|说明)", compact, flags=re.I)
    if not three_header:
        return []
    row_pattern = re.compile(
        r"(?P<name>[A-Za-z][A-Za-z0-9_]*)\s*\|\s*"
        r"(?P<type>[A-Za-z][A-Za-z0-9_./+\-]*)\s*\|\s*",
        flags=re.I,
    )
    matches = list(row_pattern.finditer(compact))
    if not matches:
        return []
    rows = [["名称", "类型", three_header.group(1)]]
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(compact)
        description = compact[match.end():end].strip(" |-")
        rows.append([match.group("name").strip(), match.group("type").strip(), description])
    return rows


def _parse_markdown_table(section: str, *, role: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if line.count("|") < 2:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        rows.append(cells)
    if rows:
        header = rows[0]
        has_name_type = _header_index(header, ("名称",)) is not None and _header_index(header, ("类型",)) is not None
        if role == "input":
            valid_header = has_name_type and _header_index(header, ("必选", "必填", "必须")) is not None
        else:
            valid_header = has_name_type and (
                _header_index(header, ("默认显示", "默认输出")) is not None
                or _header_index(header, ("描述", "说明")) is not None
            )
        if valid_header and len(rows[0]) <= 6:
            return rows
    return _parse_compact_markdown_table(section, role=role)

def _extract_markdown_label(text: str, label: str, next_labels: tuple[str, ...]) -> str:
    labels = "|".join(re.escape(value) for value in next_labels)
    match = re.search(
        rf"(?:^|\s|[-*])(?:\*\*)?{re.escape(label)}(?:\*\*)?[：:]\s*(.+?)"
        rf"(?=\s+(?:\*\*)?(?:{labels})(?:\*\*)?[：:]|\Z)",
        text or "",
        flags=re.I | re.S,
    )
    return re.sub(r"\s+", " ", match.group(1)).strip(" -*") if match else ""


def _assert_unique_fields(rows: list[dict[str, Any]], label: str) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    if duplicates:
        raise ValueError(f"重复{label}字段：{','.join(duplicates)}")


def parse_tushare_document_markdown(markdown: str, official_url: str) -> dict[str, Any]:
    text = (markdown or "").replace("\r\n", "\n").replace("\r", "\n")
    title_match = re.search(r"^\s*#{1,4}\s+(.+?)\s*$", text, flags=re.M)
    title = title_match.group(1).strip().strip("- ") if title_match else ""
    # Compact machine documents may append metadata to the heading itself.
    title = re.split(r"\s+-{2,}\s+接口[：:]|\s+接口[：:]", title, maxsplit=1)[0].strip("- ")
    api_match = re.search(
        r"(?:\*\*)?(?:接口名称|接口)(?:\*\*)?\s*[：:]\s*`?([A-Za-z0-9_]+)`?",
        text, flags=re.I,
    )
    api_name = api_match.group(1).strip().lower() if api_match else ""
    input_section = _markdown_section_any(
        text, ("输入参数", "接口参数"),
        ("输出参数", "接口示例", "接口使用说明", "接口用法", "接口用例", "数据样例", "数据示例"),
    )
    output_section = _markdown_section_any(
        text, ("输出参数",),
        ("接口示例", "接口使用说明", "接口用法", "接口用例", "接口调用", "数据样例", "数据示例"),
    )
    input_table = _parse_markdown_table(input_section, role="input")
    output_table = _parse_markdown_table(output_section, role="output")

    inputs = _parse_input_rows(input_table)
    outputs = _parse_output_rows(output_table)
    _assert_unique_fields(inputs, "输入")
    _assert_unique_fields(outputs, "输出")

    input_heading = re.search(r"(?:\*\*)?(?:输入参数|接口参数)(?:\*\*)?", text)
    metadata_area = text[: input_heading.start()] if input_heading else text
    description = _extract_markdown_label(
        metadata_area, "描述", ("接口说明", "限量", "权限", "积分", "提示", "输入参数", "接口参数"),
    ) or _extract_markdown_label(
        metadata_area, "接口说明", ("描述", "限量", "权限", "积分", "提示", "输入参数", "接口参数"),
    )
    permission_lines = []
    limit_lines = []
    permission = _extract_markdown_label(
        metadata_area, "权限", ("限量", "积分", "提示", "输入参数"),
    )
    points = _extract_markdown_label(
        metadata_area, "积分", ("限量", "权限", "提示", "输入参数"),
    )
    limit_value = _extract_markdown_label(
        metadata_area, "限量", ("权限", "积分", "提示", "输入参数"),
    )
    if permission:
        permission_lines.append("权限：" + permission)
    if points:
        permission_lines.append("积分：" + points)
    if limit_value:
        limit_lines.append("限量：" + limit_value)
    # Preserve support for conventional multi-line documents and labels such
    # as 调取说明 that are not represented by the compact helper above.
    for line in metadata_area.splitlines():
        clean = line.strip().strip("-")
        if clean.startswith(("权限：", "权限:", "积分：", "积分:")) and clean not in permission_lines:
            permission_lines.append(clean)
        if clean.startswith(("限量：", "限量:", "调取说明：", "调取说明:")) and clean not in limit_lines:
            limit_lines.append(clean)
    output_schema_mode = "dynamic" if api_name == "pro_bar" and not output_table else "fixed"
    warnings: list[str] = []
    if not api_name:
        warnings.append("未识别接口英文名")
    if not input_table:
        warnings.append("未识别输入参数表")
    if output_schema_mode == "fixed" and (not output_table or not outputs):
        warnings.append("未识别输出参数表")
    raw = {
        "provider": "tushare",
        "api_name": api_name,
        "official_doc_id": _doc_id(official_url),
        "official_url": official_url,
        "official_title": title or api_name,
        "official_description": description,
        "permission_text": "\n".join(permission_lines),
        "limit_text": "\n".join(limit_lines),
        "inputs": inputs,
        "outputs": outputs,
        "output_schema_mode": output_schema_mode,
        "dynamic_output_reason": (
            "pro_bar为TuShare Python SDK动态计算接口，返回字段随asset、freq和ma参数变化，官网未提供固定输出参数表。"
            if output_schema_mode == "dynamic" else ""
        ),
        "source_fetched_at": datetime.now().isoformat(timespec="seconds"),
        "source_format": "markdown",
        "parse_warnings": warnings,
    }
    return _attach_document_hashes(raw, text)


def parse_tushare_official_document(text: str, official_url: str, *, content_type: str = "") -> dict[str, Any]:
    lowered = (content_type or "").lower()
    if "html" in lowered or re.search(r"<\s*(?:html|body|table|h[1-4])\b", text or "", flags=re.I):
        return parse_tushare_document_html(text, official_url)
    return parse_tushare_document_markdown(text, official_url)


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("name") or ""): row for row in rows if row.get("name")}


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _permission_contract(current: dict[str, Any], permission_text: str) -> tuple[str, str]:
    """Return scope and label derived from the official point requirement.

    The catalog used to keep a stale permission label even after official
    synchronization changed the displayed permission text.  Deriving both
    values from the same official sentence prevents the UI, authorization
    scope and documentation from disagreeing.
    """
    match = re.search(r"(?<!\d)(\d{3,6})\s*积分", permission_text or "")
    if not match:
        return str(current.get("scope") or ""), str(current.get("permission_label") or "")
    points = int(match.group(1))
    return f"tushare:points{points}:read", f"通用接口（{points}积分权限）"


def diff_interface_specs(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    """Compare every official contract dimension, including order and metadata."""
    diffs: list[dict[str, Any]] = []
    metadata = (
        ("title", "title_changed", "info"),
        ("description", "description_changed", "info"),
        ("permission_text", "permission_text_changed", "info"),
        ("limit_text", "limit_text_changed", "info"),
        ("official_doc_id", "official_doc_id_changed", "warning"),
        ("official_url", "official_url_changed", "warning"),
        ("output_schema_mode", "output_schema_mode_changed", "blocking"),
        ("dynamic_output_reason", "dynamic_output_reason_changed", "info"),
    )
    for field, change_type, severity in metadata:
        left, right = old.get(field), new.get(field)
        equal = _compact(left) == _compact(right) if isinstance(left, str) or isinstance(right, str) else left == right
        if not equal:
            diffs.append({
                "section": "interface", "field": field, "change_type": change_type,
                "severity": severity, "old": left, "new": right,
            })

    for section, key in (("input", "input_params"), ("output", "output_fields")):
        old_list = list(old.get(key) or [])
        new_list = list(new.get(key) or [])
        old_rows, new_rows = _index(old_list), _index(new_list)
        for name in [row.get("name") for row in new_list if row.get("name") not in old_rows]:
            required = bool(new_rows[name].get("required")) if section == "input" else False
            diffs.append({
                "section": section, "field": name, "change_type": f"{section}_added",
                "severity": "blocking" if required else "warning", "old": None, "new": new_rows[name],
            })
        for name in [row.get("name") for row in old_list if row.get("name") not in new_rows]:
            diffs.append({
                "section": section, "field": name, "change_type": f"{section}_removed",
                "severity": "blocking", "old": old_rows[name], "new": None,
            })
        old_order = [str(row.get("name") or "") for row in old_list]
        new_order = [str(row.get("name") or "") for row in new_list]
        if old_order != new_order and set(old_order) == set(new_order):
            diffs.append({
                "section": section, "field": "__order__", "change_type": f"{section}_order_changed",
                "severity": "warning", "old": old_order, "new": new_order,
            })
        for name in [value for value in new_order if value in old_rows]:
            left, right = old_rows[name], new_rows[name]
            old_type = str(left.get("official_type") or left.get("normalized_type") or "").strip().lower()
            new_type = str(right.get("official_type") or right.get("normalized_type") or "").strip().lower()
            if old_type != new_type:
                diffs.append({
                    "section": section, "field": name, "change_type": f"{section}_type_changed",
                    "severity": "blocking", "old": old_type, "new": new_type,
                })
            if section == "input" and bool(left.get("required")) != bool(right.get("required")):
                diffs.append({
                    "section": section, "field": name, "change_type": "input_required_changed",
                    "severity": "blocking", "old": bool(left.get("required")), "new": bool(right.get("required")),
                })
            if section == "output" and bool(left.get("default_display")) != bool(right.get("default_display")):
                diffs.append({
                    "section": section, "field": name, "change_type": "output_default_display_changed",
                    "severity": "warning", "old": bool(left.get("default_display")), "new": bool(right.get("default_display")),
                })
            if _compact(left.get("description")) != _compact(right.get("description")):
                diffs.append({
                    "section": section, "field": name, "change_type": f"{section}_description_changed",
                    "severity": "info", "old": left.get("description"), "new": right.get("description"),
                })
    return diffs


class OfficialSpecSyncError(RuntimeError):
    def __init__(self, message: str, *, stage: str):
        super().__init__(message)
        self.stage = stage


class TushareSpecSyncService:
    def __init__(self, spec_service: MarketInterfaceSpecService | None = None, *, session: requests.Session | None = None):
        self.spec_service = spec_service or MarketInterfaceSpecService()
        self.spec_service.ensure_seed_release()
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "stock-server-admin-spec-sync/1.0")

    def build_effective_spec(self, current: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
        current_inputs = _index(current.get("input_params") or [])
        current_outputs = _index(current.get("output_fields") or [])
        inputs = []
        for row in raw.get("inputs") or []:
            prior = current_inputs.get(row["name"], {})
            description = row.get("description") or ""
            name = row["name"]
            date_like = name.endswith("date") or "日期" in description
            normalized = _normalize_type(str(row.get("official_type") or ""))
            inputs.append({
                "name": name,
                "official_type": row.get("official_type") or "",
                "normalized_type": normalized,
                "required": bool(row.get("required")),
                "official_required": row.get("official_required") or ("Y" if row.get("required") else "N"),
                "description": description,
                "example": prior.get("example"),
                "default_value": prior.get("default_value"),
                "format": prior.get("format") or ("YYYYMMDD" if date_like else ""),
                "multiple": bool(prior.get("multiple", "多个" in description or "逗号" in description)),
                "separator": prior.get("separator") or ",",
                "enum_values": list(prior.get("enum_values") or []),
                "min_value": prior.get("min_value"),
                "max_value": prior.get("max_value"),
                "max_length": prior.get("max_length"),
                "pattern": prior.get("pattern") or "",
                "widget": prior.get("widget") or ("date" if date_like else "number" if normalized in {"integer", "number"} else "text"),
                "batch_value_template": prior.get("batch_value_template"),
                "source": "tushare_official",
                "source_order": row.get("source_order"),
            })
        outputs = []
        for row in raw.get("outputs") or []:
            prior = current_outputs.get(row["name"], {})
            outputs.append({
                "name": row["name"],
                "official_type": row.get("official_type") or "",
                "normalized_type": _normalize_type(str(row.get("official_type") or "")),
                "default_display": bool(row.get("default_display")),
                "official_default_display": row.get("official_default_display") or ("Y" if row.get("default_display") else "N"),
                "default_display_inferred": bool(row.get("default_display_inferred")),
                "description": row.get("description") or "",
                "unit": prior.get("unit") or "",
                "nullable": prior.get("nullable", "unknown"),
                "source": "tushare_official",
                "source_order": row.get("source_order"),
            })
        effective = copy.deepcopy(current)
        scope, permission_label = _permission_contract(
            current, str(raw.get("permission_text") or ""),
        )
        sanitized_presets = []
        for preset in effective.get("presets") or []:
            cleaned = copy.deepcopy(preset)
            cleaned["params"] = {
                key: value
                for key, value in (cleaned.get("params") or {}).items()
                if str(key).strip().lower() != "fields"
            }
            sanitized_presets.append(cleaned)
        effective.update({
            "title": raw.get("official_title") or current.get("title"),
            "description": raw.get("official_description") or current.get("description"),
            "official_doc_id": raw.get("official_doc_id"),
            "scope": scope,
            "permission_label": permission_label,
            "permission_text": raw.get("permission_text") or "",
            "limit_text": raw.get("limit_text") or "",
            "input_params": inputs,
            "output_fields": outputs,
            "output_schema_mode": str(raw.get("output_schema_mode") or "fixed"),
            "dynamic_output_reason": str(raw.get("dynamic_output_reason") or ""),
            "source_kind": "tushare_official",
            "official_verified": not bool(raw.get("parse_warnings")),
            "official_source_hash": raw.get("semantic_spec_hash") or raw.get("source_hash"),
            "official_raw_content_hash": raw.get("raw_content_hash"),
            "official_semantic_spec_hash": raw.get("semantic_spec_hash") or raw.get("source_hash"),
            "official_fetched_at": raw.get("source_fetched_at"),
            "spec_status": (
                "complete"
                if inputs is not None and (outputs or str(raw.get("output_schema_mode") or "fixed") == "dynamic")
                else "incomplete"
            ),
            "change_status": "pending_confirmation",
            "parse_warnings": list(raw.get("parse_warnings") or []),
            "presets": sanitized_presets,
        })
        diffs = diff_interface_specs(current, effective)
        effective["blocking_change"] = any(row["severity"] == "blocking" for row in diffs)
        effective["publish_issues"] = self.spec_service._candidate_publish_issues(effective)
        effective["publish_eligible"] = not effective["publish_issues"]
        effective["spec_hash"] = hashlib.sha256(
            json.dumps({key: value for key, value in effective.items() if key != "spec_hash"}, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return effective

    @staticmethod
    def official_markdown_url(spec: dict[str, Any]) -> str:
        doc_id = spec.get("official_doc_id") or _doc_id(str(spec.get("official_url") or ""))
        if not doc_id:
            return ""
        return f"https://tushare.pro/wctapi/documents/{int(doc_id)}.md"

    def create_candidate_from_document_map(
        self,
        documents: dict[str, dict[str, str]],
        *,
        candidate_version: str | None = None,
        target_count: int | None = None,
    ) -> dict[str, Any]:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        version = candidate_version or f"candidate-{timestamp}"
        candidate_dir = self.spec_service.candidates_dir / version
        if candidate_dir.exists():
            raise ValueError(f"候选版本已存在：{version}")
        source_dir = self.spec_service.root / "source" / "tushare"
        candidate_specs: list[dict[str, Any]] = []
        all_diffs: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        success_count = 0
        for api_name, document in documents.items():
            current = self.spec_service.get_effective_spec("tushare", api_name)
            if not current:
                errors.append({"api_name": api_name, "stage": "catalog", "error": "当前Provider目录不存在该接口"})
                continue
            source_url = str(document.get("url") or current.get("official_url") or "")
            try:
                supplied_raw = document.get("raw")
                raw = copy.deepcopy(supplied_raw) if isinstance(supplied_raw, dict) else parse_tushare_official_document(
                    str(document.get("text") or ""),
                    source_url,
                    content_type=str(document.get("content_type") or ""),
                )
                parsed_name = str(raw.get("api_name") or "")
                if parsed_name and parsed_name != api_name:
                    raise ValueError(f"页面接口名{parsed_name}与目录{api_name}不一致")
                if raw.get("parse_warnings"):
                    raise ValueError("；".join(str(value) for value in raw["parse_warnings"]))
                raw["api_name"] = api_name
                # Preserve the canonical public page while recording the fetched machine-readable source.
                raw["official_url"] = str(current.get("official_url") or source_url)
                raw["source_url"] = source_url
                _atomic_json(source_dir / f"{api_name}.json", raw)
                effective = self.build_effective_spec(current, raw)
                diffs = diff_interface_specs(current, effective)
                for row in diffs:
                    row.update({"provider": "tushare", "api_name": api_name})
                needs_initial_verification = not bool(current.get("official_verified"))
                if diffs or needs_initial_verification:
                    candidate_specs.append(effective)
                    all_diffs.extend(diffs)
                success_count += 1
            except Exception as exc:
                errors.append({"api_name": api_name, "stage": "parse", "error": str(exc)})
        candidate_dir.mkdir(parents=True, exist_ok=True)
        _atomic_json(candidate_dir / "effective_specs.json", candidate_specs)
        _atomic_json(candidate_dir / "diffs.json", all_diffs)
        blocking_interfaces = sorted({row["api_name"] for row in all_diffs if row.get("severity") == "blocking"})
        failed_interfaces = list(errors)
        resolved_target_count = int(target_count if target_count is not None else len(documents))
        coverage_percent = round((success_count / resolved_target_count * 100), 2) if resolved_target_count else 100.0
        manifest = {
            "version": version,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "base_version": self.spec_service.current_version(),
            "target_count": resolved_target_count,
            "requested_count": len(documents),
            "success_count": success_count,
            "coverage_percent": coverage_percent,
            "complete_sync": success_count == resolved_target_count and not errors,
            "changed_count": len(candidate_specs),
            "unchanged_count": max(0, success_count - len(candidate_specs)),
            "blocking_count": len(blocking_interfaces),
            "blocking_interfaces": blocking_interfaces,
            "error_count": len(errors),
            "errors": errors,
            "fetch_error_count": 0,
            "parse_error_count": sum(1 for row in errors if row.get("stage") == "parse"),
            "failed_interfaces": failed_interfaces,
            "publishable_count": sum(1 for row in candidate_specs if row.get("publish_eligible")),
        }
        _atomic_json(candidate_dir / "manifest.json", manifest)
        return manifest

    def create_candidate_from_html_map(self, html_map: dict[str, str], *, candidate_version: str | None = None) -> dict[str, Any]:
        documents = {
            api_name: {"text": html, "url": str((self.spec_service.get_effective_spec("tushare", api_name) or {}).get("official_url") or ""), "content_type": "text/html"}
            for api_name, html in html_map.items()
        }
        return self.create_candidate_from_document_map(documents, candidate_version=candidate_version)

    def _fetch_document(self, url: str, *, timeout: int, retries: int) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(max(1, retries + 1)):
            try:
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                return response
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(min(0.25 * (attempt + 1), 1.0))
        assert last_error is not None
        raise last_error

    def _official_attempt_urls(self, spec: dict[str, Any]) -> list[str]:
        markdown_url = self.official_markdown_url(spec)
        public_url = str(spec.get("official_url") or "")
        return list(dict.fromkeys(url for url in (markdown_url, public_url) if url))

    def _fetch_url_document(self, url: str) -> dict[str, str]:
        import config
        timeout = int(config.ADMIN_API_TEST_OFFICIAL_SYNC_TIMEOUT_SECONDS)
        retries = int(getattr(config, "ADMIN_API_TEST_OFFICIAL_SYNC_RETRIES", 1))
        response = self._fetch_document(url, timeout=timeout, retries=retries)
        return {
            "text": response.text,
            "url": url,
            "content_type": str(getattr(response, "headers", {}).get("Content-Type") or ""),
        }

    def fetch_official_document(self, spec: dict[str, Any]) -> dict[str, str]:
        """Fetch one official document, preferring machine-readable Markdown.

        This fetch-only compatibility method is retained for callers that need
        raw source text.  Synchronization and monitoring use
        :meth:`fetch_and_parse_official_spec` so a syntactically reachable but
        unparsable Markdown document can fall back to the public HTML page.
        """
        api_name = str(spec.get("api_name") or "")
        attempts = self._official_attempt_urls(spec)
        if not attempts:
            raise ValueError(f"{api_name}缺少官方URL")
        errors: list[str] = []
        for url in attempts:
            try:
                return self._fetch_url_document(url)
            except Exception as exc:
                errors.append(f"{url}: {exc}")
        raise OfficialSpecSyncError("；".join(errors), stage="fetch")

    def fetch_and_parse_official_spec(
        self, spec: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Fetch and validate one official contract with parse-aware fallback."""
        api_name = str(spec.get("api_name") or "").strip().lower()
        attempts = self._official_attempt_urls(spec)
        if not attempts:
            raise OfficialSpecSyncError(f"{api_name}缺少官方URL", stage="fetch")
        errors: list[str] = []
        fetched_any = False
        parse_failed = False
        for url in attempts:
            try:
                document = self._fetch_url_document(url)
                fetched_any = True
            except Exception as exc:
                errors.append(f"抓取失败 {url}: {exc}")
                continue
            try:
                raw = parse_tushare_official_document(
                    str(document.get("text") or ""),
                    str(document.get("url") or url),
                    content_type=str(document.get("content_type") or ""),
                )
                parsed_name = str(raw.get("api_name") or "").strip().lower()
                if parsed_name and parsed_name != api_name:
                    raise ValueError(f"页面接口名{parsed_name}与目录{api_name}不一致")
                if raw.get("parse_warnings"):
                    raise ValueError("；".join(str(value) for value in raw["parse_warnings"]))
                if not raw.get("outputs") and str(raw.get("output_schema_mode") or "fixed") != "dynamic":
                    raise ValueError("官网输出参数为空")
                raw["api_name"] = api_name
                raw["source_url"] = str(document.get("url") or url)
                raw["official_url"] = str(spec.get("official_url") or document.get("url") or url)
                return raw, document
            except Exception as exc:
                parse_failed = True
                errors.append(f"解析失败 {url}: {exc}")
        stage = "parse" if fetched_any and parse_failed else "fetch"
        raise OfficialSpecSyncError("；".join(errors) or f"{api_name}官网规格获取失败", stage=stage)

    def sync_official_specs(
        self,
        api_names: Iterable[str] | None = None,
        *,
        candidate_version: str | None = None,
    ) -> dict[str, Any]:
        import config
        current_rows = self.spec_service.list_effective_specs(provider="tushare")
        selected = {str(value).strip().lower() for value in api_names or [] if str(value).strip()}
        targets = [row for row in current_rows if not selected or str(row.get("api_name") or "") in selected]
        documents: dict[str, dict[str, Any]] = {}
        fetch_errors: list[dict[str, str]] = []
        for row in targets:
            api_name = str(row.get("api_name") or "")
            try:
                raw, document = self.fetch_and_parse_official_spec(row)
                documents[api_name] = {**document, "raw": raw}
            except Exception as exc:
                stage = str(getattr(exc, "stage", "fetch_or_parse"))
                fetch_errors.append({"api_name": api_name, "stage": stage, "error": str(exc)})
            delay_ms = int(config.ADMIN_API_TEST_OFFICIAL_SYNC_DELAY_MS)
            if delay_ms:
                time.sleep(delay_ms / 1000.0)
        manifest = self.create_candidate_from_document_map(
            documents,
            candidate_version=candidate_version,
            target_count=len(targets),
        )
        candidate_dir = self.spec_service.candidates_dir / manifest["version"]
        stored = json.loads((candidate_dir / "manifest.json").read_text(encoding="utf-8"))
        stored["fetch_error_count"] = sum(1 for row in fetch_errors if row.get("stage") == "fetch")
        stored["parse_error_count"] = int(stored.get("parse_error_count") or 0) + sum(
            1 for row in fetch_errors if row.get("stage") == "parse"
        )
        stored["fetch_errors"] = fetch_errors
        stored["error_count"] = int(stored.get("parse_error_count") or 0) + int(stored.get("fetch_error_count") or 0)
        stored["failed_interfaces"] = [*fetch_errors, *list(stored.get("errors") or [])]
        target_count = int(stored.get("target_count") or 0)
        success_count = int(stored.get("success_count") or 0)
        stored["coverage_percent"] = round((success_count / target_count * 100), 2) if target_count else 100.0
        stored["complete_sync"] = success_count == target_count and stored["error_count"] == 0
        _atomic_json(candidate_dir / "manifest.json", stored)
        return stored
