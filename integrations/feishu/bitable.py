# -*- coding: utf-8 -*-
"""
integrations/feishu/bitable.py

飞书多维表格管理工具：
1. 会员表：把本地权威会员信息发布到飞书，并支持受控登记回写。
2. 竞价表：支持把开盘啦早盘竞价数据写入飞书多维表格。
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Optional

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import (
    AppTableField,
    AppTableFieldProperty,
    AppTableRecord,
    CreateAppTableFieldRequest,
    CreateAppTableRecordRequest,
    ListAppTableFieldRequest,
    ListAppTableRecordRequest,
    UpdateAppTableRecordRequest,
)

import config



@dataclass(frozen=True, slots=True)
class BiddingFieldSpec:
    name: str
    type: int
    accepted_types: tuple[int, ...] = ()
    date_formatter: str | None = None

    def accepts(self, actual_type: Any) -> bool:
        try:
            value = int(actual_type)
        except (TypeError, ValueError):
            return False
        return value in (self.accepted_types or (self.type,))


# Feishu Bitable field type codes used here: 1=text, 2=number, 3=single select,
# 5=date/datetime, 7=checkbox. Existing compatible select fields are retained.
def _field(name: str, type_code: int, *accepted: int, date_formatter: str | None = None) -> BiddingFieldSpec:
    return BiddingFieldSpec(name, type_code, (type_code, *accepted), date_formatter)


BIDDING_FIELD_SPECS: dict[str, BiddingFieldSpec] = {
    "股票代码": _field("股票代码", 1),
    "股票名称": _field("股票名称", 1),
    "当前价格": _field("当前价格", 2),
    "实时涨幅": _field("实时涨幅", 2),
    "竞价涨幅": _field("竞价涨幅", 2),
    "涨停委买额": _field("涨停委买额", 2),
    "20分后涨停委买": _field("20分后涨停委买", 2),
    "竞价匹配额": _field("竞价匹配额", 2),
    "竞价成交额": _field("竞价成交额", 2),
    "竞价净额": _field("竞价净额", 2),
    "竞价换手": _field("竞价换手", 2),
    "主力净额": _field("主力净额", 2),
    "主力买入": _field("主力买入", 2),
    "主力卖出额": _field("主力卖出额", 2),
    "实际流通": _field("实际流通", 2),
    "板块": _field("板块", 1),
    "行业": _field("行业", 1),
    "连板": _field("连板", 1),
    "连板高度": _field("连板高度", 2),
    "交易日期": _field("交易日期", 1),
    "快照时间": _field("快照时间", 5, date_formatter="yyyy-MM-dd HH:mm"),
    "快照ID": _field("快照ID", 1),
    "快照类型": _field("快照类型", 1, 3),
    "数据源": _field("数据源", 1, 3),
    "数据质量": _field("数据质量", 1, 3),
    "Schema版本": _field("Schema版本", 1),
}


def _present(value: Any) -> bool:
    if value is None or value == "":
        return False
    try:
        import pandas as pd
        return not bool(pd.isna(value))
    except Exception:
        return True


def build_bidding_fields_v2(bidding_data: dict) -> dict:
    """Build the final v2 Feishu payload without fabricating missing values."""
    mappings = {
        "股票代码": (("股票代码", "symbol"), str),
        "股票名称": (("股票名称", "name"), str),
        "当前价格": (("当前价格", "auction_price"), None),
        "实时涨幅": (("实时涨幅", "realtime_pct"), None),
        "竞价涨幅": (("竞价涨幅", "auction_pct"), None),
        "涨停委买额": (("涨停委买额", "limit_buy_amount"), None),
        "20分后涨停委买": (("20分后涨停委买", "limit_buy_amount_after_0920"), None),
        "竞价匹配额": (("竞价匹配额", "auction_match_amount"), None),
        "竞价成交额": (("竞价成交额", "auction_amount"), None),
        "竞价净额": (("竞价净额", "auction_net_amount"), None),
        "竞价换手": (("竞价换手", "auction_turnover"), None),
        "主力净额": (("主力净额", "main_net_amount"), None),
        "主力买入": (("主力买入", "main_buy_amount"), None),
        "主力卖出额": (("主力卖出额", "main_sell_amount"), None),
        "实际流通": (("实际流通", "float_market_value"), None),
        "板块": (("板块", "sector"), str),
        "行业": (("行业", "industry"), str),
        "连板": (("连板", "limit_up_text"), str),
        "连板高度": (("连板高度", "limit_up_days"), None),
        "交易日期": (("trade_date", "交易日期"), str),
        "快照时间": (("snapshot_time", "快照时间"), str),
        "快照ID": (("snapshot_id", "快照ID"), str),
        "快照类型": (("snapshot_type", "快照类型"), str),
        "数据源": (("source_provider", "数据源"), str),
        "数据质量": (("data_quality", "数据质量"), str),
        "Schema版本": (("schema_version", "Schema版本"), str),
    }
    result = {}
    for feishu_name, (source_names, converter) in mappings.items():
        value = next((bidding_data.get(name) for name in source_names if _present(bidding_data.get(name))), None)
        if not _present(value):
            continue
        if converter is str:
            value = str(value)
        result[feishu_name] = value
    return result


class FeishuBitableManager:
    """飞书多维表格管理器。"""

    def __init__(self):
        self.app_id = config.FEISHU_APP_ID
        self.app_secret = config.FEISHU_APP_SECRET

        # 会员 / Token 表
        self.app_token = config.FEISHU_BTABLE_APP_TOKEN
        self.table_id = config.FEISHU_BTABLE_TABLE_ID

        # 开盘啦竞价表
        self.bidding_app_token = config.FEISHU_BIDDING_APP_TOKEN
        self.bidding_table_id = config.FEISHU_BIDDING_TABLE_ID

        self._bidding_schema_checked = False
        self.client = (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .build()
        )

    def _str_to_ms(self, time_value: Any) -> int | None:
        """Convert a valid date/timestamp to milliseconds; invalid input stays empty."""
        if time_value is None or str(time_value).strip() in {"", "None"}:
            return None
        if isinstance(time_value, (int, float)):
            value = float(time_value)
            return int(value * 1000) if value < 1e12 else int(value)
        text = str(time_value).strip()
        try:
            value = float(text)
            return int(value * 1000) if value < 1e12 else int(value)
        except (TypeError, ValueError):
            pass
        for fmt in (
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
        ):
            try:
                parsed = datetime.strptime(text, fmt).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
                return int(parsed.timestamp() * 1000)
            except ValueError:
                continue
        logging.error("[飞书] 日期转换失败，字段保持为空: %s", text)
        return None

    def list_fields(
        self,
        app_token: Optional[str] = None,
        table_id: Optional[str] = None,
        page_size: int = 100,
    ) -> dict[str, dict[str, Any]]:
        """Read real field definitions from a Bitable table."""
        app_token = app_token or self.bidding_app_token
        table_id = table_id or self.bidding_table_id
        if not app_token or not table_id:
            raise RuntimeError("飞书竞价表 app_token/table_id 未配置")
        fields: dict[str, dict[str, Any]] = {}
        page_token = None
        while True:
            builder = (
                ListAppTableFieldRequest.builder()
                .app_token(app_token)
                .table_id(table_id)
                .page_size(page_size)
            )
            if page_token:
                builder = builder.page_token(page_token)
            response = self.client.bitable.v1.app_table_field.list(builder.build())
            if not response.success():
                raise RuntimeError(f"读取飞书竞价表字段失败：{response.msg}")
            for item in (getattr(response.data, "items", None) or []):
                name = str(getattr(item, "field_name", "") or "").strip()
                if name:
                    fields[name] = {
                        "field_id": getattr(item, "field_id", None),
                        "field_name": name,
                        "type": getattr(item, "type", None),
                        "ui_type": getattr(item, "ui_type", None),
                    }
            if not response.data or not getattr(response.data, "has_more", False):
                break
            page_token = getattr(response.data, "page_token", None)
        return fields

    def create_field(
        self,
        spec: BiddingFieldSpec,
        app_token: Optional[str] = None,
        table_id: Optional[str] = None,
    ) -> bool:
        """Create one missing field; existing fields are never changed or deleted."""
        app_token = app_token or self.bidding_app_token
        table_id = table_id or self.bidding_table_id
        builder = AppTableField.builder().field_name(spec.name).type(spec.type)
        if spec.date_formatter:
            prop = AppTableFieldProperty.builder().date_formatter(spec.date_formatter).build()
            builder = builder.property(prop)
        request = (
            CreateAppTableFieldRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .request_body(builder.build())
            .build()
        )
        response = self.client.bitable.v1.app_table_field.create(request)
        if not response.success():
            logging.error("[飞书竞价] 创建字段失败 %s: %s", spec.name, response.msg)
            return False
        return True

    def check_bidding_schema(self, *, create_missing: bool = False) -> dict[str, Any]:
        """Validate the real table schema and optionally add only missing compatible fields."""
        existing = self.list_fields(app_token=self.bidding_app_token, table_id=self.bidding_table_id)
        missing: list[str] = []
        created: list[str] = []
        mismatches: list[dict[str, Any]] = []
        errors: list[str] = []
        for name, spec in BIDDING_FIELD_SPECS.items():
            current = existing.get(name)
            if current is None:
                missing.append(name)
                if create_missing:
                    try:
                        if self.create_field(spec, app_token=self.bidding_app_token, table_id=self.bidding_table_id):
                            created.append(name)
                        else:
                            errors.append(f"创建字段失败：{name}")
                    except Exception as exc:
                        errors.append(f"创建字段异常：{name}: {exc}")
                continue
            if not spec.accepts(current.get("type")):
                mismatches.append({
                    "field_name": name,
                    "actual_type": current.get("type"),
                    "expected_types": list(spec.accepted_types or (spec.type,)),
                    "field_id": current.get("field_id"),
                })
        unresolved = [name for name in missing if name not in created]
        return {
            "ok": not unresolved and not mismatches and not errors,
            "existing_count": len(existing),
            "missing": missing,
            "created": created,
            "unresolved_missing": unresolved,
            "type_mismatches": mismatches,
            "errors": errors,
        }

    def ensure_bidding_schema(self, *, create_missing: bool = True) -> dict[str, Any]:
        if self._bidding_schema_checked:
            return {"ok": True, "cached": True}
        report = self.check_bidding_schema(create_missing=create_missing)
        if not report.get("ok"):
            names = [item.get("field_name") for item in report.get("type_mismatches", [])]
            details = []
            if report.get("unresolved_missing"):
                details.append("缺失字段=" + ",".join(report["unresolved_missing"]))
            if names:
                details.append("类型不兼容=" + ",".join(str(x) for x in names))
            if report.get("errors"):
                details.append("错误=" + ";".join(report["errors"]))
            raise RuntimeError("飞书竞价表字段检查未通过：" + "；".join(details))
        self._bidding_schema_checked = True
        return report

    def list_all_records(
        self,
        app_token: Optional[str] = None,
        table_id: Optional[str] = None,
        page_size: int = 500,
    ):
        """获取指定多维表中的所有记录。默认读取会员表。"""
        records = []
        page_token = None
        app_token = app_token or self.app_token
        table_id = table_id or self.table_id

        try:
            while True:
                builder = (
                    ListAppTableRecordRequest.builder()
                    .app_token(app_token)
                    .table_id(table_id)
                    .page_size(page_size)
                )
                if page_token:
                    builder = builder.page_token(page_token)
                request = builder.build()

                response = self.client.bitable.v1.app_table_record.list(request)
                if not response.success():
                    logging.error("[飞书] 获取记录失败: %s", response.msg)
                    break

                if response.data and response.data.items:
                    for item in response.data.items:
                        records.append((item.record_id, item.fields or {}))

                if not response.data or not response.data.has_more:
                    break
                page_token = response.data.page_token

        except Exception as e:
            logging.exception("[飞书] 获取记录异常: %s", e)

        return records

    def find_record_by_token(self, token: str):
        """兼容旧工具的只读查询；正式会员upsert不再按Token匹配。"""
        token = str(token or "").strip()
        if not token:
            return None
        for record_id, fields in self.list_all_records():
            if str(fields.get("授权码") or "").strip() == token:
                return record_id, fields
        return None

    def find_record_by_user_id(self, user_id):
        """在会员表中根据“用户ID”查找记录，返回 (record_id, fields) 或 None。"""
        user_id_text = str(user_id or "").strip()
        if not user_id_text:
            return None
        for record_id, fields in self.list_all_records():
            if str(fields.get("用户ID") or "").strip() == user_id_text:
                return record_id, fields
        return None

    def add_record(self, fields: dict, app_token: Optional[str] = None, table_id: Optional[str] = None) -> bool:
        """新增一条飞书记录。"""
        app_token = app_token or self.app_token
        table_id = table_id or self.table_id
        try:
            request = (
                CreateAppTableRecordRequest.builder()
                .app_token(app_token)
                .table_id(table_id)
                .request_body(AppTableRecord.builder().fields(fields).build())
                .build()
            )
            response = self.client.bitable.v1.app_table_record.create(request)
            if not response.success():
                logging.error("[飞书] 新增记录失败: %s", response.msg)
                return False
            return True
        except Exception as e:
            logging.exception("[飞书] 新增记录异常: %s", e)
            return False

    def update_record(
        self,
        record_id: str,
        fields: dict,
        app_token: Optional[str] = None,
        table_id: Optional[str] = None,
    ) -> bool:
        """更新一条飞书记录。"""
        app_token = app_token or self.app_token
        table_id = table_id or self.table_id
        try:
            request = (
                UpdateAppTableRecordRequest.builder()
                .app_token(app_token)
                .table_id(table_id)
                .record_id(record_id)
                .request_body(AppTableRecord.builder().fields(fields).build())
                .build()
            )
            response = self.client.bitable.v1.app_table_record.update(request)
            if not response.success():
                logging.error("[飞书] 更新记录失败: %s", response.msg)
                return False
            return True
        except Exception as e:
            logging.exception("[飞书] 更新记录异常: %s", e)
            return False

    def upsert_member_record(self, fields: dict, user_id=None) -> str:
        """
        更新/新增会员记录。

        会员表只按“用户ID”匹配。API Token 不再参与飞书记录匹配，
        避免完整凭证暴露在多维表格中，也避免 Token 轮换后错误关联。

        返回：added / updated / failed
        """
        user_id_text = str(user_id or "").strip()
        if not user_id_text:
            logging.error("[飞书] upsert会员记录失败：缺少用户ID")
            return "failed"

        existing = self.find_record_by_user_id(user_id_text)
        if existing:
            record_id, _old = existing
            return "updated" if self.update_record(record_id, fields) else "failed"

        return "added" if self.add_record(fields) else "failed"

    # ========== 竞价数据相关方法 ==========
    @staticmethod
    def _field_text(value: Any) -> str:
        """Extract text from plain values or Feishu rich-text cell payloads."""
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("name") or item.get("value")
                    if text is not None:
                        parts.append(str(text))
                elif item is not None:
                    parts.append(str(item))
            return "".join(parts).strip()
        if isinstance(value, dict):
            for key in ("text", "name", "value"):
                if value.get(key) is not None:
                    return str(value[key]).strip()
        return str(value or "").strip()

    @classmethod
    def _bidding_unique_key(cls, fields: dict) -> str | None:
        snapshot_id = cls._field_text(fields.get("快照ID"))
        stock_code = cls._field_text(fields.get("股票代码"))
        return f"{snapshot_id}|{stock_code}" if snapshot_id and stock_code else None

    def _prepare_bidding_fields(self, bidding_data: dict) -> dict:
        fields = build_bidding_fields_v2(bidding_data)
        if "快照时间" in fields:
            value = self._str_to_ms(fields["快照时间"])
            if value is None:
                fields.pop("快照时间", None)
            else:
                fields["快照时间"] = value
        return fields

    def add_bidding_record(self, bidding_data: dict) -> bool:
        """Add one validated Kaipanla snapshot row."""
        try:
            fields = self._prepare_bidding_fields(bidding_data)
            if self._bidding_unique_key(fields) is None:
                logging.error("[飞书竞价] 缺少快照ID或股票代码，拒绝写入")
                return False
            return self.add_record(fields, self.bidding_app_token, self.bidding_table_id)
        except Exception as exc:
            logging.exception("[飞书竞价] 新增记录异常: %s", exc)
            return False

    def batch_add_bidding_records(self, data_list: list[dict]) -> tuple[int, int]:
        """Idempotently upsert rows after loading the Bitable index once."""
        existing = {}
        for record_id, fields in self.list_all_records(self.bidding_app_token, self.bidding_table_id):
            key = self._bidding_unique_key(fields)
            if key:
                existing[key] = record_id
        success_count = 0
        fail_count = 0
        for item in data_list:
            fields = self._prepare_bidding_fields(item)
            key = self._bidding_unique_key(fields)
            if key is None:
                fail_count += 1
                continue
            record_id = existing.get(key)
            if record_id:
                ok = self.update_record(record_id, fields, self.bidding_app_token, self.bidding_table_id)
            else:
                ok = self.add_record(fields, self.bidding_app_token, self.bidding_table_id)
                if ok:
                    existing[key] = "created"
            if ok:
                success_count += 1
            else:
                fail_count += 1
        return success_count, fail_count


_bitable_manager = None


def get_bitable_manager():
    global _bitable_manager
    if _bitable_manager is None:
        _bitable_manager = FeishuBitableManager()
    return _bitable_manager

