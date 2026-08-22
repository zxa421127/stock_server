# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from integrations.kaipanla.morning_bidding import _map_bidding_fields
from integrations.market_data.kaipanla.adapter import normalize_kaipanla_bidding, parse_limit_up_days
from integrations.market_data.kaipanla.schema import SCHEMA_VERSION, STANDARD_BIDDING_COLUMNS


def sample_raw(overrides=None):
    row = {0:"600895",1:"张江高科",2:35.15,3:3.47,4:1180010068,5:10.01,6:116352228,7:0.76,8:225834380,9:20927200,10:225834384,11:"光刻机、创投",12:27898674312,13:238939100,14:1318790483,15:-1079851383,16:"4连板"}
    row.update(overrides or {})
    return pd.DataFrame([row])


def normalize(df=None, **kwargs):
    snapshot_type = kwargs.pop("snapshot_type", "auction")
    return normalize_kaipanla_bidding(
        df if df is not None else sample_raw(), trade_date="20260714",
        snapshot_type=snapshot_type, snapshot_time="2026-07-14 09:26:05",
        snapshot_id="20260714_092605_auction_abcdef123456", **kwargs,
    )


def test_live_mapper_keeps_raw_evidence_internal_and_uses_new_aliases():
    row = _map_bidding_fields(sample_raw()).iloc[0]
    assert row["10"] == row["竞价匹配额"]
    assert row["13"] == row["主力净额"]
    assert row["14"] == row["主力买入"]
    assert row["15"] == row["主力卖出额原始值"]
    assert row["6"] == row["竞价净额"]
    assert "竞价竞额" not in row.index


def test_public_normalized_output_is_exact_final_schema_without_raw_fields():
    frame = normalize()
    assert list(frame.columns) == STANDARD_BIDDING_COLUMNS
    row = frame.iloc[0]
    assert row["auction_net_amount"] == 116352228
    assert row["auction_match_amount"] == 225834384
    assert row["auction_amount"] == 225834380
    assert row["main_net_amount"] == 238939100
    assert row["main_buy_amount"] == 1318790483
    assert row["main_sell_amount"] == 1079851383
    assert row["auction_net_amount"] != row["main_net_amount"]
    for removed in ("10","13","14","15","主力卖出","main_sell_amount_signed","main_amount_relation_valid","field_validation_warning"):
        assert removed not in frame.columns


def test_invalid_main_relation_is_logged_internally_but_values_are_not_fabricated_or_hidden(caplog):
    row = normalize(sample_raw({13:1,14:10,15:-3})).iloc[0]
    assert row["main_net_amount"] == 1
    assert row["main_buy_amount"] == 10
    assert row["main_sell_amount"] == 3
    assert "主力资金关系校验失败" in caplog.text


def test_missing_and_invalid_numeric_values_remain_empty(caplog):
    row = normalize(sample_raw({6:None,10:"bad",13:"",14:0,15:None})).iloc[0]
    assert pd.isna(row["auction_net_amount"])
    assert pd.isna(row["auction_match_amount"])
    assert pd.isna(row["main_net_amount"])
    assert row["main_buy_amount"] == 0
    assert pd.isna(row["main_sell_amount"])
    assert "数值转换失败" in caplog.text


def test_kaipanla_name_wins_and_historical_fallback_uses_bak_name():
    stock = pd.DataFrame([{"ts_code":"600895.SH","symbol":"600895","name":"现名","industry":"房地产"}])
    bak = pd.DataFrame([{"ts_code":"600895.SH","name":"历史名","industry":"历史行业"}])
    direct = normalize(stock_basic_df=stock,bak_basic_df=bak,historical=True).iloc[0]
    fallback = normalize(sample_raw({1:None}),stock_basic_df=stock,bak_basic_df=bak,historical=True).iloc[0]
    assert direct["name"] == "张江高科"
    assert fallback["name"] == "历史名"
    assert fallback["行业"] == "房地产"


def test_sector_is_never_filled_from_tushare_industry():
    stock = pd.DataFrame([{"ts_code":"600895.SH","symbol":"600895","name":"张江高科","industry":"房地产"}])
    row = normalize(sample_raw({11:None}),stock_basic_df=stock,historical=True).iloc[0]
    assert pd.isna(row["sector"])
    assert row["行业"] == "房地产"


def test_limit_height_uses_only_kaipanla_main_text():
    for text, height in (("首板",1),("2连板",2),("4天3板",3),("9天7板",7),("未知",None)):
        assert parse_limit_up_days(text) == height
    row = normalize(sample_raw({16:"9天7板"})).iloc[0]
    assert row["连板"] == "9天7板"
    assert row["limit_up_days"] == 7
    for removed in ("limit_step_nums","limit_up_days_source","kpl_list_status","kpl_list_limit_up_days"):
        assert removed not in row.index


def test_schema_provenance_and_snapshot_type_are_present():
    row = normalize(snapshot_type="post_open").iloc[0]
    assert SCHEMA_VERSION == "kaipanla_bidding.v2"
    assert row["schema_version"] == SCHEMA_VERSION
    assert row["snapshot_type"] == "post_open"
    assert row["source_provider"] == "kaipanla"
    assert row["data_quality"] == "complete"


def test_tushare_partial_rows_keep_unavailable_fields_null():
    raw = pd.DataFrame([{"ts_code":"600895.SH","name":"张江高科","price":35.15,"pre_close":32.0,"amount":225834380,"trade_date":"20260714"}])
    row = normalize_kaipanla_bidding(raw,trade_date="20260714",source_provider="tushare",source_api="stk_auction_o",data_quality="partial").iloc[0]
    assert row["auction_amount"] == 225834380
    assert pd.isna(row["auction_match_amount"])
    assert pd.isna(row["main_net_amount"])
