# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from integrations.market_data.kaipanla.adapter import normalize_kaipanla_bidding, parse_limit_up_days
from integrations.market_data.kaipanla.schema import SCHEMA_VERSION, STANDARD_BIDDING_COLUMNS


OBSOLETE_FIELDS = {
    "10", "13", "14", "15",
    "主力卖出", "main_sell_amount_signed",
    "main_amount_relation_valid", "field_validation_warning",
    "limit_step_nums", "limit_up_days_source", "limit_up_days_conflict",
    "kpl_list_status", "kpl_list_limit_up_days",
    "auction_match_amount_definition_status",
}


def test_public_schema_keeps_v2_but_removes_obsolete_fields():
    assert SCHEMA_VERSION == "kaipanla_bidding.v2"
    assert OBSOLETE_FIELDS.isdisjoint(STANDARD_BIDDING_COLUMNS)
    assert {"snapshot_type", "auction_net_amount", "main_sell_amount"}.issubset(STANDARD_BIDDING_COLUMNS)


def test_field6_is_auction_net_amount_and_main_net_is_independent():
    raw = pd.DataFrame([{
        "0": "000001",
        "1": "平安银行",
        "6": 123,
        "10": 456,
        "13": 30,
        "14": 50,
        "15": -20,
        "16": "4天3板",
    }])
    row = normalize_kaipanla_bidding(
        raw,
        trade_date="20260723",
        snapshot_time="2026-07-23 09:26:05",
        snapshot_type="auction",
    ).iloc[0].to_dict()

    assert row["auction_net_amount"] == 123
    assert row["竞价净额"] == 123
    assert row["auction_match_amount"] == 456
    assert row["main_net_amount"] == 30
    assert row["main_buy_amount"] == 50
    assert row["main_sell_amount"] == 20
    assert row["主力卖出额"] == 20
    assert row["连板"] == "4天3板"
    assert row["limit_up_days"] == 3
    assert row["snapshot_type"] == "auction"
    assert OBSOLETE_FIELDS.isdisjoint(row)


def test_missing_or_invalid_numeric_values_remain_none_not_zero(caplog):
    raw = pd.DataFrame([{
        "0": "000001",
        "6": "not-a-number",
        "10": None,
        "13": None,
        "14": "",
        "15": "bad",
        "16": "无法解析",
    }])
    row = normalize_kaipanla_bidding(raw, trade_date="20260723").iloc[0].to_dict()

    assert row["auction_net_amount"] is None
    assert row["auction_match_amount"] is None
    assert row["main_net_amount"] is None
    assert row["main_buy_amount"] is None
    assert row["main_sell_amount"] is None
    assert row["limit_up_days"] is None
    assert "字段数值转换失败" in caplog.text


def test_limit_up_days_parsing_uses_kaipanla_text_rules():
    assert parse_limit_up_days("首板") == 1
    assert parse_limit_up_days("2连板") == 2
    assert parse_limit_up_days("4天3板") == 3
    assert parse_limit_up_days("9天7板") == 7
    assert parse_limit_up_days("未知") is None
