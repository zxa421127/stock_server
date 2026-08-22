# -*- coding: utf-8 -*-
"""Versioned interface specifications for the administrator testing center.

The seed release is generated from the project's 140-interface catalog so the
feature is usable immediately.  Tushare official synchronization later
replaces catalog-seed rows with official input/output definitions through a
candidate-and-publish workflow; runtime never depends on the website.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from services.api_doc_catalog import FULL_API_DOCS, FULL_API_DOCS_VERSION


_SECRET_PARAM_NAMES = {
    "token", "api_token", "tushare_token", "kaipanla_token", "password",
    "csrf_token", "cookie", "session", "secret", "api_key",
}

_VALIDATION_RULE_TYPES = {
    "required", "at_least_one", "exactly_one", "mutually_exclusive",
    "requires", "required_if", "date_range", "datetime_range",
    "single_value_only", "max_items", "min_items",
}
_INPUT_OVERRIDE_KEYS = {
    "normalized_type", "example", "default_value", "format", "multiple",
    "separator", "enum_values", "min_value", "max_value", "max_length",
    "pattern", "widget", "batch_value_template",
}
_OUTPUT_OVERRIDE_KEYS = {"normalized_type", "unit", "nullable"}


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _infer_type(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _normalize_type(value: str) -> str:
    text = (value or "").strip().lower()
    if text in {"int", "integer", "long"}:
        return "integer"
    if text in {"float", "double", "number", "decimal"}:
        return "number"
    if text in {"bool", "boolean"}:
        return "boolean"
    if text in {"dict", "object", "json"}:
        return "object"
    if text in {"list", "array"}:
        return "array"
    return "string" if text not in {"none", "unknown", ""} else "unknown"


def _required(value: Any) -> bool:
    return str(value or "").strip().lower() in {"y", "yes", "true", "1", "是", "必填"}


def _doc_id(url: str) -> int | None:
    text = url or ""
    match = re.search(r"[?&]doc_id=(\d+)(?:&|$)", text)
    if not match:
        match = re.search(r"/(\d+)(?:\D|$)", text)
    return int(match.group(1)) if match else None


def _safe_key(provider: str, api_name: str) -> str:
    return f"{provider.strip().lower()}::{api_name.strip().lower().replace('-', '_')}"


# The existing catalog intentionally stores only the latest executable example.
# These common additions keep the seed release useful until the first official
# synchronization.  Official candidate releases replace them rather than merge
# hidden parameters indefinitely.
_SEED_INPUT_ADDITIONS: dict[str, list[dict[str, Any]]] = {
    "daily": [
        {"name": "trade_date", "type": "string", "required": False, "example": "20260724", "description": "交易日期（YYYYMMDD）"},
    ],
    "weekly": [{"name": "trade_date", "type": "string", "required": False, "example": "20260724", "description": "交易日期（YYYYMMDD）"}],
    "monthly": [{"name": "trade_date", "type": "string", "required": False, "example": "20260724", "description": "交易日期（YYYYMMDD）"}],
}


_ETF_BASIC_OFFICIAL_INPUTS = [
    {"name": "ts_code", "type": "str", "required": False, "description": "ETF代码（带.SZ/.SH后缀的6位数字，如：159526.SZ）"},
    {"name": "index_code", "type": "str", "required": False, "description": "跟踪指数代码"},
    {"name": "list_date", "type": "str", "required": False, "description": "上市日期（格式：YYYYMMDD）"},
    {"name": "list_status", "type": "str", "required": False, "description": "上市状态（L上市 D退市 P待上市）", "enum_values": ["L", "D", "P"], "widget": "select", "example": "L"},
    {"name": "exchange", "type": "str", "required": False, "description": "交易所（SH上交所 SZ深交所）", "enum_values": ["SH", "SZ"], "widget": "select"},
    {"name": "mgr", "type": "str", "required": False, "description": "管理人（简称，e.g.华夏基金）"},
]

_ETF_BASIC_OFFICIAL_OUTPUTS = [
    ("ts_code", "str", "基金交易代码"),
    ("csname", "str", "ETF中文简称"),
    ("extname", "str", "ETF扩位简称(对应交易所简称)"),
    ("cname", "str", "基金中文全称"),
    ("index_code", "str", "ETF基准指数代码"),
    ("index_name", "str", "ETF基准指数中文全称"),
    ("setup_date", "str", "设立日期（格式：YYYYMMDD）"),
    ("list_date", "str", "上市日期（格式：YYYYMMDD）"),
    ("list_status", "str", "存续状态（L上市 D退市 P待上市）"),
    ("exchange", "str", "交易所（上交所SH 深交所SZ）"),
    ("mgr_name", "str", "基金管理人简称"),
    ("custod_name", "str", "基金托管人名称"),
    ("mgt_fee", "float", "基金管理人收取的费用"),
    ("etf_type", "str", "基金投资通道类型（境内、QDII）"),
]

_ETF_INDEX_OFFICIAL_INPUTS = [
    {"name": "ts_code", "type": "str", "required": False, "description": "指数代码"},
    {"name": "pub_date", "type": "str", "required": False, "description": "发布日期（格式：YYYYMMDD）"},
    {"name": "base_date", "type": "str", "required": False, "description": "指数基期（格式：YYYYMMDD）"},
]

_ETF_INDEX_OFFICIAL_OUTPUTS = [
    ("ts_code", "str", "指数代码"),
    ("indx_name", "str", "指数全称"),
    ("indx_csname", "str", "指数简称"),
    ("pub_party_name", "str", "指数发布机构"),
    ("pub_date", "str", "指数发布日期"),
    ("base_date", "str", "指数基日"),
    ("bp", "float", "指数基点(点)"),
    ("adj_circle", "str", "指数成份证券调整周期"),
]


_CI_DAILY_OFFICIAL_INPUTS = [
    {"name": "ts_code", "type": "str", "required": False, "description": "行业代码"},
    {"name": "trade_date", "type": "str", "required": False, "description": "交易日期（YYYYMMDD格式，下同）"},
    {"name": "start_date", "type": "str", "required": False, "description": "开始日期"},
    {"name": "end_date", "type": "str", "required": False, "description": "结束日期"},
]

_CI_DAILY_OFFICIAL_OUTPUTS = [
    ("ts_code", "str", "指数代码"),
    ("trade_date", "str", "交易日期"),
    ("open", "float", "开盘点位"),
    ("low", "float", "最低点位"),
    ("high", "float", "最高点位"),
    ("close", "float", "收盘点位"),
    ("pre_close", "float", "昨日收盘点位"),
    ("change", "float", "涨跌点位"),
    ("pct_change", "float", "涨跌幅"),
    ("vol", "float", "成交量（万股）"),
    ("amount", "float", "成交额（万元）"),
]


class MarketInterfaceSpecService:
    SEED_VERSION = f"seed-{FULL_API_DOCS_VERSION}"

    def __init__(self, root: str | Path | None = None):
        if root is None:
            import config
            root = config.ADMIN_API_TEST_SPEC_DIR
        self.root = Path(root).resolve()
        self.releases_dir = self.root / "releases"
        self.candidates_dir = self.root / "candidates"
        self.current_file = self.root / "current.json"
        self._cache_version = ""
        self._cache_specs: list[dict[str, Any]] = []

    def ensure_seed_release(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.current_file.exists():
            current = self._read_json(self.current_file, {})
            version = str(current.get("version") or "")
            if version and (self.releases_dir / version / "effective_specs.json").exists():
                return version
        release_dir = self.releases_dir / self.SEED_VERSION
        specs = self._build_seed_specs()
        release_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(release_dir / "effective_specs.json", specs)
        _atomic_write_json(release_dir / "manifest.json", {
            "version": self.SEED_VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": "project_catalog_seed",
            "official_verified": False,
            "interface_count": len(specs),
            "specs_hash": _sha256(specs),
        })
        _atomic_write_json(self.current_file, {"version": self.SEED_VERSION})
        self._cache_version = ""
        return self.SEED_VERSION

    def current_version(self) -> str:
        self.ensure_seed_release()
        return str(self._read_json(self.current_file, {}).get("version") or self.SEED_VERSION)

    def _load_specs(self) -> list[dict[str, Any]]:
        version = self.current_version()
        if version == self._cache_version and self._cache_specs:
            return copy.deepcopy(self._cache_specs)
        path = self.releases_dir / version / "effective_specs.json"
        rows = self._read_json(path, [])
        if not isinstance(rows, list):
            raise RuntimeError(f"接口规格文件格式错误：{path}")
        self._cache_version = version
        self._cache_specs = rows
        return copy.deepcopy(rows)

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError, OSError):
            return copy.deepcopy(default)

    def list_effective_specs(
        self, *, provider: str = "", category: str = "", keyword: str = "",
        status: str = "",
    ) -> list[dict[str, Any]]:
        rows = self._load_specs()
        provider = provider.strip().lower()
        category = category.strip()
        keyword = keyword.strip().lower()
        status = status.strip().lower()
        result = []
        for row in rows:
            if provider and row.get("provider") != provider:
                continue
            if category and row.get("category") != category:
                continue
            if status and str(row.get("spec_status") or "").lower() != status:
                continue
            haystack = " ".join(str(row.get(key) or "") for key in ("api_name", "title", "category", "description", "scope")).lower()
            if keyword and keyword not in haystack:
                continue
            result.append(row)
        return sorted(
            result,
            key=lambda row: (
                str(row.get("provider") or ""),
                int(row.get("category_sort_order") or 9999),
                str(row.get("category") or "其他/未分类"),
                int(row.get("sort_order") or 0),
                str(row.get("api_name") or ""),
            ),
        )

    def get_effective_spec(self, provider: str, api_name: str) -> dict[str, Any] | None:
        key = _safe_key(provider, api_name)
        for row in self._load_specs():
            if _safe_key(row.get("provider", ""), row.get("api_name", "")) == key:
                return row
        return None

    def coverage_statistics(self) -> dict[str, Any]:
        rows = self._load_specs()
        incomplete = [row for row in rows if row.get("spec_status") == "incomplete"]
        pending = [row for row in rows if row.get("change_status") in {"official_changed", "pending_confirmation"}]
        severe = [row for row in pending if row.get("blocking_change")]
        return {
            "total": len(rows),
            "complete": len(rows) - len(incomplete),
            "warning": sum(1 for row in rows if row.get("spec_status") == "warning"),
            "incomplete": len(incomplete),
            "missing_spec": 0,
            "official_change_pending": len(pending),
            "blocking_change_pending": len(severe),
            "current_version": self.current_version(),
            "official_verified": sum(1 for row in rows if row.get("official_verified")),
        }

    def spec_issues(self, spec: dict[str, Any], *, require_official_tushare: bool = False) -> list[str]:
        issues: list[str] = []
        provider = str(spec.get("provider") or "")
        api_name = str(spec.get("api_name") or "")
        if not provider or not api_name:
            issues.append("缺少provider或api_name")
        inputs = list(spec.get("input_params") or [])
        outputs = list(spec.get("output_fields") or [])
        input_names = [str(row.get("name") or "") for row in inputs]
        output_names = [str(row.get("name") or "") for row in outputs]
        if any(not name for name in input_names):
            issues.append("存在无名称输入参数")
        if len(input_names) != len(set(input_names)):
            issues.append("输入参数名称重复")
        if not outputs and str(spec.get("output_schema_mode") or "fixed") != "dynamic":
            issues.append("缺少输出字段定义")
        if any(not name for name in output_names):
            issues.append("存在无名称输出字段")
        if len(output_names) != len(set(output_names)):
            issues.append("输出字段名称重复")
        defined = set(input_names)
        for rule in spec.get("validation_rules") or []:
            rule_type = str(rule.get("type") or "")
            if rule_type not in _VALIDATION_RULE_TYPES:
                issues.append(f"不支持的参数组合规则：{rule_type or '空类型'}")
            referenced = set(rule.get("fields") or [])
            for key in ("field", "required_field", "condition_field", "start_field", "end_field"):
                if rule.get(key):
                    referenced.add(str(rule[key]))
            missing = referenced - defined
            if missing:
                issues.append("参数组合规则引用不存在字段：" + ",".join(sorted(missing)))
        presets = list(spec.get("presets") or [])
        if not presets:
            issues.append("缺少批量测试预设")
        else:
            try:
                self._validate_params_for_spec(
                    spec,
                    self.resolve_templates(copy.deepcopy(presets[0].get("params") or {})),
                )
            except Exception as exc:
                issues.append(f"默认测试预设不合法：{exc}")
        if spec.get("blocking_change"):
            issues.append("存在阻断级官网变化待确认")
        if spec.get("spec_status") == "incomplete":
            issues.append("规格状态不完整")
        if require_official_tushare and provider == "tushare" and not spec.get("official_verified"):
            issues.append("尚未按Tushare官网完整定义确认发布")
        if provider == "kaipanla" and api_name == "morning_bidding_history":
            snapshot = next((row for row in inputs if row.get("name") == "snapshot_type"), {})
            if list(snapshot.get("enum_values") or []) != ["auction", "post_open", "close"]:
                issues.append("Kaipanla历史快照未完整覆盖auction/post_open/close")
        return issues

    def batch_eligibility(self, provider: str, api_name: str) -> tuple[bool, list[str]]:
        spec = self.get_effective_spec(provider, api_name)
        if not spec:
            return False, [f"未找到接口规格：{provider}/{api_name}"]
        issues = self.spec_issues(spec, require_official_tushare=True)
        return not issues, issues

    def validate_all_specs(self, *, require_official_tushare: bool = False) -> dict[str, Any]:
        rows = []
        for spec in self.list_effective_specs():
            issues = self.spec_issues(spec, require_official_tushare=require_official_tushare)
            rows.append({
                "provider": spec.get("provider"), "api_name": spec.get("api_name"),
                "valid": not issues, "issues": issues,
                "input_count": len(spec.get("input_params") or []),
                "output_count": len(spec.get("output_fields") or []),
                "official_verified": bool(spec.get("official_verified")),
            })
        return {
            "version": self.current_version(), "total": len(rows),
            "valid_count": sum(1 for row in rows if row["valid"]),
            "invalid_count": sum(1 for row in rows if not row["valid"]),
            "items": rows,
        }

    def validate_params(self, provider: str, api_name: str, params: dict[str, Any]) -> dict[str, Any]:
        spec = self.get_effective_spec(provider, api_name)
        if not spec:
            raise KeyError(f"未找到接口规格：{provider}/{api_name}")
        return self._validate_params_for_spec(spec, params)

    def _validate_params_for_spec(self, spec: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        params = dict(params or {})
        forbidden = {key for key in params if key.strip().lower() in _SECRET_PARAM_NAMES}
        if forbidden:
            raise ValueError("禁止提交敏感参数：" + ",".join(sorted(forbidden)))
        definitions = {row["name"]: row for row in spec.get("input_params", [])}
        unknown = sorted(key for key in params if key not in definitions)
        if unknown:
            raise ValueError("接口未定义参数：" + ",".join(unknown))
        converted: dict[str, Any] = {}
        for name, definition in definitions.items():
            value = params.get(name)
            if value in (None, ""):
                if definition.get("required"):
                    raise ValueError(f"缺少必填参数：{name}")
                continue
            converted[name] = self._convert_param(name, value, definition)
        self._validate_rules(spec.get("validation_rules", []), converted)
        return converted

    @staticmethod
    def _convert_param(name: str, value: Any, definition: dict[str, Any]) -> Any:
        normalized = str(definition.get("normalized_type") or _normalize_type(str(definition.get("official_type") or definition.get("type") or "string")))
        if normalized == "integer":
            try:
                value = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"参数{name}必须为整数") from exc
        elif normalized == "number":
            try:
                value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"参数{name}必须为数字") from exc
        elif normalized == "boolean":
            if isinstance(value, bool):
                pass
            elif str(value).strip().lower() in {"1", "true", "yes", "y", "on"}:
                value = True
            elif str(value).strip().lower() in {"0", "false", "no", "n", "off"}:
                value = False
            else:
                raise ValueError(f"参数{name}必须为布尔值")
        else:
            value = str(value).strip()
        enum_values = definition.get("enum_values") or []
        if enum_values and value not in enum_values and str(value) not in {str(item) for item in enum_values}:
            raise ValueError(f"参数{name}只允许：{','.join(map(str, enum_values))}")
        pattern = str(definition.get("pattern") or "")
        if pattern and not re.fullmatch(pattern, str(value)):
            raise ValueError(f"参数{name}格式不正确")
        max_length = definition.get("max_length")
        if max_length is not None and len(str(value)) > int(max_length):
            raise ValueError(f"参数{name}长度不能超过{max_length}")
        min_value = definition.get("min_value")
        max_value = definition.get("max_value")
        if min_value is not None and value < min_value:
            raise ValueError(f"参数{name}不能小于{min_value}")
        if max_value is not None and value > max_value:
            raise ValueError(f"参数{name}不能大于{max_value}")
        return value

    @staticmethod
    def _validate_rules(rules: list[dict[str, Any]], params: dict[str, Any]) -> None:
        def values_for(value: Any, separator: str = ",") -> list[Any]:
            if value in (None, ""):
                return []
            if isinstance(value, (list, tuple, set)):
                return [item for item in value if item not in (None, "")]
            if isinstance(value, str):
                return [item.strip() for item in value.split(separator) if item.strip()]
            return [value]

        for rule in rules:
            kind = str(rule.get("type") or "")
            fields = list(rule.get("fields") or [])
            present = [name for name in fields if params.get(name) not in (None, "")]
            message = str(rule.get("message") or "参数组合不符合要求")
            if kind == "required":
                field = rule.get("field")
                if params.get(field) in (None, ""):
                    raise ValueError(message)
            elif kind == "at_least_one" and not present:
                raise ValueError(message)
            elif kind == "exactly_one" and len(present) != 1:
                raise ValueError(message)
            elif kind == "mutually_exclusive" and len(present) > 1:
                raise ValueError(message)
            elif kind == "requires" and params.get(rule.get("field")) not in (None, ""):
                required_field = rule.get("required_field")
                if params.get(required_field) in (None, ""):
                    raise ValueError(message)
            elif kind == "required_if":
                condition = params.get(rule.get("condition_field"))
                expected = list(rule.get("condition_values") or [])
                matches = condition not in (None, "") if not expected else str(condition) in {str(item) for item in expected}
                if matches and params.get(rule.get("field")) in (None, ""):
                    raise ValueError(message)
            elif kind in {"date_range", "datetime_range"}:
                start = params.get(rule.get("start_field"))
                end = params.get(rule.get("end_field"))
                if start and end and str(start) > str(end):
                    raise ValueError(message)
            elif kind == "single_value_only":
                if len(values_for(params.get(rule.get("field")), str(rule.get("separator") or ","))) > 1:
                    raise ValueError(message)
            elif kind in {"max_items", "min_items"}:
                values = values_for(params.get(rule.get("field")), str(rule.get("separator") or ","))
                if kind == "max_items" and len(values) > int(rule.get("max_items") or 0):
                    raise ValueError(message)
                if kind == "min_items" and len(values) < int(rule.get("min_items") or 0):
                    raise ValueError(message)
            elif kind not in _VALIDATION_RULE_TYPES:
                raise ValueError(f"不支持的参数组合规则：{kind or '空类型'}")

    def resolve_templates(self, value: Any, *, today: date | None = None) -> Any:
        current = today or date.today()
        if isinstance(value, dict):
            return {key: self.resolve_templates(item, today=current) for key, item in value.items()}
        if isinstance(value, list):
            return [self.resolve_templates(item, today=current) for item in value]
        if not isinstance(value, str):
            return value
        last_trade = current
        while last_trade.weekday() >= 5:
            last_trade -= timedelta(days=1)
        quarter_month = ((current.month - 1) // 3) * 3 + 1
        previous_quarter_end = date(current.year, quarter_month, 1) - timedelta(days=1)
        mapping = {
            "${today}": current.strftime("%Y%m%d"),
            "${last_trade_date}": last_trade.strftime("%Y%m%d"),
            "${thirty_days_ago}": (current - timedelta(days=30)).strftime("%Y%m%d"),
            "${sample_stock}": "000001.SZ",
            "${recent_report_period}": previous_quarter_end.strftime("%Y%m%d"),
        }
        result = value
        for source, target in mapping.items():
            result = result.replace(source, target)
        return result

    def default_test_params(self, provider: str, api_name: str) -> dict[str, Any]:
        spec = self.get_effective_spec(provider, api_name)
        if not spec:
            raise KeyError(f"未找到接口规格：{provider}/{api_name}")
        presets = spec.get("presets") or []
        if presets:
            return self.resolve_templates(copy.deepcopy(presets[0].get("params") or {}))
        result = {}
        for row in spec.get("input_params", []):
            example = row.get("batch_value_template") or row.get("example")
            if row.get("required") and example not in (None, ""):
                result[row["name"]] = example
        return self.resolve_templates(result)

    def all_output_field_names(self, provider: str, api_name: str) -> list[str]:
        spec = self.get_effective_spec(provider, api_name)
        if not spec:
            return []
        return [str(row.get("name")) for row in spec.get("output_fields", []) if row.get("name")]

    def _candidate_publish_issues(self, spec: dict[str, Any]) -> list[str]:
        issues = self.spec_issues(spec, require_official_tushare=True)
        # A blocking official change is exactly why administrator confirmation is
        # required. It remains visible in the diff but is not a permanent block
        # once every field and the executable preset have passed validation.
        issues = [issue for issue in issues if issue != "存在阻断级官网变化待确认"]
        for warning in spec.get("parse_warnings") or []:
            issues.append(f"官网页面解析警告：{warning}")
        return list(dict.fromkeys(issues))

    def save_interface_preset(
        self, provider: str, api_name: str, params: dict[str, Any], *,
        name: str, updated_by: str, release_version: str | None = None,
    ) -> dict[str, Any]:
        key = _safe_key(provider, api_name)
        rows = self._load_specs()
        indexed = {_safe_key(row.get("provider", ""), row.get("api_name", "")): row for row in rows}
        if key not in indexed:
            raise KeyError(f"未找到接口规格：{provider}/{api_name}")
        spec = copy.deepcopy(indexed[key])
        converted = self._validate_params_for_spec(spec, self.resolve_templates(copy.deepcopy(params or {})))
        preset_name = str(name or "管理员默认参数").strip() or "管理员默认参数"
        spec["presets"] = [{"name": preset_name, "params": converted}]
        spec["preset_updated_by"] = str(updated_by or "admin")
        spec["preset_updated_at"] = datetime.now().isoformat(timespec="seconds")
        spec["spec_hash"] = self._spec_hash(spec)
        indexed[key] = spec
        output_rows = sorted(
            indexed.values(),
            key=lambda row: (
                row.get("provider", ""), row.get("category", ""),
                int(row.get("sort_order") or 0), row.get("api_name", ""),
            ),
        )
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        version = release_version or f"spec-{timestamp}-preset-{_sha256([key, converted])[:8]}"
        release_dir = self.releases_dir / version
        if release_dir.exists():
            raise ValueError(f"规格版本已存在：{version}")
        release_dir.mkdir(parents=True)
        _atomic_write_json(release_dir / "effective_specs.json", output_rows)
        manifest = {
            "version": version,
            "previous_version": self.current_version(),
            "change_type": "preset_update",
            "selected_interfaces": [key],
            "updated_by": str(updated_by or "admin"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "specs_hash": _sha256(output_rows),
        }
        _atomic_write_json(release_dir / "manifest.json", manifest)
        _atomic_write_json(self.current_file, {"version": version})
        self._cache_version = ""
        return manifest

    def update_candidate_overrides(
        self, candidate_version: str, provider: str, api_name: str, *,
        input_overrides: dict[str, dict[str, Any]],
        output_overrides: dict[str, dict[str, Any]],
        validation_rules: list[dict[str, Any]], updated_by: str,
    ) -> dict[str, Any]:
        """Apply administrator normalization rules without altering official fields.

        Official names, source types, required flags, descriptions, and field order
        remain immutable.  Administrators may only add executable platform rules
        needed for strict form validation and output interpretation.
        """
        directory = (self.candidates_dir / candidate_version).resolve()
        if directory.parent != self.candidates_dir.resolve():
            raise ValueError("候选版本路径非法")
        path = directory / "effective_specs.json"
        rows = self._read_json(path, [])
        key = _safe_key(provider, api_name)
        target = next((
            row for row in rows
            if _safe_key(row.get("provider", ""), row.get("api_name", "")) == key
        ), None)
        if target is None:
            raise KeyError(f"候选版本缺少接口：{provider}/{api_name}")
        if not isinstance(input_overrides, dict) or not isinstance(output_overrides, dict):
            raise ValueError("input_overrides和output_overrides必须为JSON对象")
        if not isinstance(validation_rules, list) or any(not isinstance(row, dict) for row in validation_rules):
            raise ValueError("validation_rules必须为JSON对象数组")

        input_rows = {str(row.get("name") or ""): row for row in target.get("input_params") or []}
        output_rows = {str(row.get("name") or ""): row for row in target.get("output_fields") or []}
        for name, overrides in input_overrides.items():
            if name not in input_rows:
                raise ValueError(f"输入参数不存在：{name}")
            if not isinstance(overrides, dict):
                raise ValueError(f"输入参数{name}的覆盖规则必须为JSON对象")
            forbidden = set(overrides) - _INPUT_OVERRIDE_KEYS
            if forbidden:
                raise ValueError("禁止修改官方字段：" + ",".join(sorted(forbidden)))
            input_rows[name].update(copy.deepcopy(overrides))
        for name, overrides in output_overrides.items():
            if name not in output_rows:
                raise ValueError(f"输出字段不存在：{name}")
            if not isinstance(overrides, dict):
                raise ValueError(f"输出字段{name}的覆盖规则必须为JSON对象")
            forbidden = set(overrides) - _OUTPUT_OVERRIDE_KEYS
            if forbidden:
                raise ValueError("禁止修改官方字段：" + ",".join(sorted(forbidden)))
            output_rows[name].update(copy.deepcopy(overrides))

        target["validation_rules"] = copy.deepcopy(validation_rules)
        target["override_updated_by"] = str(updated_by or "admin")
        target["override_updated_at"] = datetime.now().isoformat(timespec="seconds")
        # Validate structural references and executable preset after every edit.
        issues = self._candidate_publish_issues(target)
        target["publish_issues"] = issues
        target["publish_eligible"] = not issues
        target["spec_hash"] = self._spec_hash(target)
        _atomic_write_json(path, rows)
        manifest_path = directory / "manifest.json"
        manifest = self._read_json(manifest_path, {"version": candidate_version})
        manifest["publishable_count"] = sum(1 for row in rows if row.get("publish_eligible"))
        manifest["updated_at"] = datetime.now().isoformat(timespec="seconds")
        _atomic_write_json(manifest_path, manifest)
        return copy.deepcopy(target)

    def update_candidate_preset(
        self, candidate_version: str, provider: str, api_name: str,
        params: dict[str, Any], *, name: str, updated_by: str,
    ) -> dict[str, Any]:
        directory = (self.candidates_dir / candidate_version).resolve()
        if directory.parent != self.candidates_dir.resolve():
            raise ValueError("候选版本路径非法")
        path = directory / "effective_specs.json"
        rows = self._read_json(path, [])
        key = _safe_key(provider, api_name)
        target = None
        for row in rows:
            if _safe_key(row.get("provider", ""), row.get("api_name", "")) == key:
                target = row
                break
        if target is None:
            raise KeyError(f"候选版本缺少接口：{provider}/{api_name}")
        converted = self._validate_params_for_spec(
            target, self.resolve_templates(copy.deepcopy(params or {}))
        )
        target["presets"] = [{
            "name": str(name or "管理员默认参数").strip() or "管理员默认参数",
            "params": converted,
        }]
        target["preset_updated_by"] = str(updated_by or "admin")
        target["preset_updated_at"] = datetime.now().isoformat(timespec="seconds")
        target["spec_hash"] = self._spec_hash(target)
        issues = self._candidate_publish_issues(target)
        target["publish_issues"] = issues
        target["publish_eligible"] = not issues
        _atomic_write_json(path, rows)
        manifest_path = directory / "manifest.json"
        manifest = self._read_json(manifest_path, {"version": candidate_version})
        manifest["publishable_count"] = sum(1 for row in rows if row.get("publish_eligible"))
        manifest["updated_at"] = datetime.now().isoformat(timespec="seconds")
        _atomic_write_json(manifest_path, manifest)
        return copy.deepcopy(target)

    def candidate_summary(self, *, include_processed: bool = False) -> list[dict[str, Any]]:
        result = []
        if not self.candidates_dir.exists():
            return result
        for directory in sorted(self.candidates_dir.iterdir(), reverse=True):
            if not directory.is_dir():
                continue
            manifest = self._read_json(directory / "manifest.json", {})
            manifest.setdefault("version", directory.name)
            if not include_processed and manifest.get("status") in {"published", "superseded", "discarded"}:
                continue
            result.append(manifest)
        return result

    def load_candidate(self, candidate_version: str) -> dict[str, Any]:
        directory = (self.candidates_dir / candidate_version).resolve()
        if directory.parent != self.candidates_dir.resolve():
            raise ValueError("候选版本路径非法")
        specs = self._read_json(directory / "effective_specs.json", [])
        diffs = self._read_json(directory / "diffs.json", [])
        manifest = self._read_json(directory / "manifest.json", {})
        return {"version": candidate_version, "specs": specs, "diffs": diffs, "manifest": manifest}

    def publish_candidate_selection(
        self, candidate_version: str, selected: Iterable[tuple[str, str]], *,
        published_by: str, note: str, release_version: str | None = None,
    ) -> dict[str, Any]:
        selected_keys = {_safe_key(provider, api) for provider, api in selected}
        if not selected_keys:
            raise ValueError("至少选择一个接口")
        candidate = self.load_candidate(candidate_version)
        manifest = candidate.get("manifest") or {}
        if manifest.get("complete_sync") is False:
            success = int(manifest.get("success_count") or 0)
            target = int(manifest.get("target_count") or 0)
            failures = int(manifest.get("error_count") or max(0, target - success))
            raise ValueError(
                f"候选同步未完整（成功{success}/{target}，失败{failures}），禁止发布；请修复失败接口后重新同步"
            )
        candidates = {_safe_key(row.get("provider", ""), row.get("api_name", "")): row for row in candidate["specs"]}
        missing = selected_keys - candidates.keys()
        if missing:
            raise ValueError("候选版本缺少接口：" + ",".join(sorted(missing)))
        blocked_details = {
            key: self._candidate_publish_issues(candidates[key])
            for key in selected_keys
        }
        blocked_details = {
            key: issues for key, issues in blocked_details.items()
            if issues or not candidates[key].get("publish_eligible", False)
        }
        if blocked_details:
            summary = []
            for key in sorted(blocked_details):
                reasons = blocked_details[key] or list(candidates[key].get("publish_issues") or ["未通过发布检查"])
                summary.append(f"{key}（{'；'.join(reasons)}）")
            raise ValueError("以下接口未通过发布检查：" + "，".join(summary))
        current_rows = self._load_specs()
        merged = {_safe_key(row.get("provider", ""), row.get("api_name", "")): row for row in current_rows}
        for key in selected_keys:
            row = copy.deepcopy(candidates[key])
            row["change_status"] = "published"
            row["blocking_change"] = False
            row["published_from_candidate"] = candidate_version
            row["spec_hash"] = self._spec_hash(row)
            merged[key] = row
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        version = release_version or f"spec-{timestamp}-{_sha256(sorted(selected_keys))[:8]}"
        release_dir = self.releases_dir / version
        if release_dir.exists():
            raise ValueError(f"规格版本已存在：{version}")
        release_dir.mkdir(parents=True)
        rows = sorted(merged.values(), key=lambda row: (row.get("provider", ""), row.get("category", ""), int(row.get("sort_order") or 0), row.get("api_name", "")))
        _atomic_write_json(release_dir / "effective_specs.json", rows)
        manifest = {
            "version": version,
            "previous_version": self.current_version(),
            "candidate_version": candidate_version,
            "selected_count": len(selected_keys),
            "selected_interfaces": sorted(selected_keys),
            "published_by": published_by,
            "note": note,
            "published_at": datetime.now().isoformat(timespec="seconds"),
            "specs_hash": _sha256(rows),
        }
        _atomic_write_json(release_dir / "manifest.json", manifest)
        candidate_manifest_path = self.candidates_dir / candidate_version / "manifest.json"
        candidate_manifest = self._read_json(candidate_manifest_path, {"version": candidate_version})
        published_keys = set(candidate_manifest.get("published_interfaces") or []) | selected_keys
        candidate_keys = {
            _safe_key(row.get("provider", ""), row.get("api_name", ""))
            for row in candidate.get("specs") or []
        }
        candidate_manifest.update({
            "published_interfaces": sorted(published_keys),
            "published_release": version,
            "published_at": manifest["published_at"],
            "status": "published" if candidate_keys and candidate_keys <= published_keys else "partially_published",
        })
        _atomic_write_json(candidate_manifest_path, candidate_manifest)
        _atomic_write_json(self.current_file, {"version": version})
        self._cache_version = ""
        return manifest

    def _build_seed_specs(self) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        for doc in FULL_API_DOCS:
            inputs = [
                self._normalize_input(
                    row,
                    source="project_code" if doc["provider"] == "kaipanla" else "catalog_seed",
                )
                for row in doc.get("params", [])
                if not (doc.get("provider") == "tushare" and str(row.get("name") or "").strip().lower() == "fields")
            ]
            existing_names = {row["name"] for row in inputs}
            for addition in _SEED_INPUT_ADDITIONS.get(str(doc.get("api_name")), []):
                if addition["name"] not in existing_names:
                    inputs.append(self._normalize_input(addition, source="catalog_seed"))
            outputs = self._outputs_from_response(doc.get("response_example") or "", source="provider_response_mapping" if doc["provider"] == "kaipanla" else "catalog_seed")
            bootstrap_inputs = None
            bootstrap_outputs = None
            bootstrap_permission = ""
            bootstrap_limit = ""
            bootstrap_description = ""
            bootstrap_title = ""
            bootstrap_points: int | None = None
            if doc.get("provider") == "tushare" and doc.get("api_name") == "etf_basic":
                bootstrap_inputs = _ETF_BASIC_OFFICIAL_INPUTS
                bootstrap_outputs = _ETF_BASIC_OFFICIAL_OUTPUTS
                bootstrap_permission = "用户积8000积分可调取"
                bootstrap_limit = "单次请求最大返回5000条数据"
                bootstrap_points = 8000
            elif doc.get("provider") == "tushare" and doc.get("api_name") == "etf_index":
                bootstrap_inputs = _ETF_INDEX_OFFICIAL_INPUTS
                bootstrap_outputs = _ETF_INDEX_OFFICIAL_OUTPUTS
                bootstrap_permission = "用户积累8000积分可调取，具体请参阅积分获取办法"
                bootstrap_limit = "单次请求最大返回5000行数据（当前未超过2000个）"
                bootstrap_description = "获取ETF基准指数列表信息"
                bootstrap_title = "ETF基准指数列表"
                bootstrap_points = 8000
            elif doc.get("provider") == "tushare" and doc.get("api_name") == "ci_daily":
                bootstrap_inputs = _CI_DAILY_OFFICIAL_INPUTS
                bootstrap_outputs = _CI_DAILY_OFFICIAL_OUTPUTS
                bootstrap_permission = "积分：5000积分可调取，可通过指数代码和日期参数循环获取所有数据"
                bootstrap_limit = "限量：单次最大4000条，可循环提取"
                bootstrap_description = "获取中信行业指数日线行情"
                bootstrap_title = "中信行业指数行情"
                bootstrap_points = 5000
            official_bootstrap = bootstrap_inputs is not None
            if official_bootstrap:
                inputs = [self._normalize_input(row, source="tushare_official_bootstrap") for row in bootstrap_inputs]
                outputs = [
                    {
                        "name": name,
                        "official_type": official_type,
                        "normalized_type": _normalize_type(official_type),
                        "default_display": True,
                        "official_default_display": "Y",
                        "description": description,
                        "unit": "",
                        "nullable": "unknown",
                        "source": "tushare_official_bootstrap",
                        "source_order": index,
                    }
                    for index, (name, official_type, description) in enumerate(bootstrap_outputs, start=1)
                ]
            if doc["provider"] == "kaipanla" and doc["api_name"] == "morning_bidding_history":
                for row in inputs:
                    if row["name"] == "snapshot_type":
                        row.update({"enum_values": ["auction", "post_open", "close"], "widget": "select", "source": "project_code"})
                    elif row["name"] == "limit":
                        row.update({"min_value": 1, "max_value": 10000})
            preset_params = {}
            for row in inputs:
                if row.get("example") not in (None, ""):
                    preset_params[row["name"]] = row["example"]
            spec = {
                "provider": doc.get("provider"),
                "api_name": doc.get("api_name"),
                "title": bootstrap_title or doc.get("title"),
                "category": doc.get("category") or "其他/未分类",
                "category_sort_order": doc.get("category_sort_order", 9999),
                "description": bootstrap_description or doc.get("description"),
                "scope": (
                    f"tushare:points{bootstrap_points}:read"
                    if bootstrap_points is not None else doc.get("scope")
                ),
                "permission_label": (
                    f"通用接口（{bootstrap_points}积分权限）"
                    if bootstrap_points is not None else doc.get("permission_label")
                ),
                "method": doc.get("method", "GET"),
                "base_path": doc.get("base_path"),
                "official_url": doc.get("official_url"),
                "official_doc_id": _doc_id(str(doc.get("official_url") or "")),
                "input_params": inputs,
                "output_fields": outputs,
                "validation_rules": [],
                "presets": [{"name": "当前项目可运行示例", "params": preset_params}],
                "source_kind": (
                    "project_code" if doc["provider"] == "kaipanla"
                    else "tushare_official_bootstrap" if official_bootstrap
                    else "catalog_seed"
                ),
                "official_verified": doc["provider"] == "kaipanla" or official_bootstrap,
                "spec_status": "complete" if outputs else "incomplete",
                "change_status": "current",
                "blocking_change": False,
                "publish_eligible": True,
                "test_status_snapshot": doc.get("test_status"),
                "test_count_snapshot": doc.get("test_count"),
                "permission_text": bootstrap_permission if official_bootstrap else "",
                "limit_text": bootstrap_limit if official_bootstrap else "",
                "sort_order": doc.get("sort_order", 0),
            }
            spec["spec_hash"] = self._spec_hash(spec)
            specs.append(spec)
        return sorted(
            specs,
            key=lambda row: (
                row["provider"],
                int(row.get("category_sort_order") or 9999),
                row["category"],
                int(row.get("sort_order") or 0),
                row["api_name"],
            ),
        )

    @staticmethod
    def _normalize_input(row: dict[str, Any], *, source: str) -> dict[str, Any]:
        official_type = str(row.get("official_type") or row.get("type") or "string")
        normalized = _normalize_type(official_type)
        name = str(row.get("name") or "").strip()
        description = str(row.get("description") or "")
        date_like = name.endswith("date") or "日期" in description
        widget = "date" if date_like else "number" if normalized in {"integer", "number"} else "text"
        return {
            "name": name,
            "official_type": official_type,
            "normalized_type": normalized,
            "required": bool(row.get("required")) if isinstance(row.get("required"), bool) else _required(row.get("required")),
            "description": description,
            "example": row.get("example"),
            "default_value": row.get("default_value"),
            "format": "YYYYMMDD" if date_like else str(row.get("format") or ""),
            "multiple": bool(row.get("multiple", False)),
            "separator": str(row.get("separator") or ","),
            "enum_values": list(row.get("enum_values") or []),
            "min_value": row.get("min_value"),
            "max_value": row.get("max_value"),
            "max_length": row.get("max_length"),
            "pattern": str(row.get("pattern") or ""),
            "widget": str(row.get("widget") or widget),
            "batch_value_template": row.get("batch_value_template"),
            "source": source,
        }

    @staticmethod
    def _outputs_from_response(text: str, *, source: str) -> list[dict[str, Any]]:
        try:
            payload = json.loads(text)
        except (TypeError, ValueError):
            return []
        data = payload.get("data") if isinstance(payload, dict) else None
        first = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
        return [
            {
                "name": name,
                "official_type": _infer_type(value),
                "normalized_type": _infer_type(value),
                "default_display": True,
                "description": "项目响应样例字段；官方同步后替换为官网字段说明" if source == "catalog_seed" else "Kaipanla标准化输出字段",
                "unit": "",
                "nullable": value is None,
                "source": source,
                "source_order": index + 1,
            }
            for index, (name, value) in enumerate(first.items())
        ]

    @staticmethod
    def _spec_hash(spec: dict[str, Any]) -> str:
        value = {key: item for key, item in spec.items() if key != "spec_hash"}
        return _sha256(value)


_default_service: MarketInterfaceSpecService | None = None


def get_market_interface_spec_service() -> MarketInterfaceSpecService:
    global _default_service
    if _default_service is None:
        _default_service = MarketInterfaceSpecService()
        _default_service.ensure_seed_release()
    return _default_service
