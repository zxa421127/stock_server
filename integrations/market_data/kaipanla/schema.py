# -*- coding: utf-8 -*-
"""Public V2 schema for Kaipanla morning-bidding snapshots."""
from __future__ import annotations

SCHEMA_VERSION = "kaipanla_bidding.v2"
SNAPSHOT_TYPES = ("auction", "post_open", "close")

# These are upstream source positions used internally while converting the raw
# payload. They are not public business fields.
REQUIRED_RAW_NUMERIC_FIELDS = ["6", "10", "13", "14", "15"]

STANDARD_BIDDING_COLUMNS = [
    "股票代码",
    "股票名称",
    "当前价格",
    "实时涨幅",
    "竞价涨幅",
    "涨停委买额",
    "20分后涨停委买",
    "竞价匹配额",
    "竞价成交额",
    "竞价净额",
    "竞价换手",
    "主力净额",
    "主力买入",
    "主力卖出额",
    "实际流通",
    "板块",
    "行业",
    "连板",
    "连板高度",
    "ts_code",
    "name",
    "trade_date",
    "snapshot_type",
    "snapshot_time",
    "snapshot_id",
    "auction_price",
    "auction_pct",
    "realtime_pct",
    "limit_buy_amount",
    "limit_buy_amount_after_0920",
    "auction_net_amount",
    "auction_match_amount",
    "auction_amount",
    "auction_turnover",
    "main_net_amount",
    "main_buy_amount",
    "main_sell_amount",
    "float_market_value",
    "sector",
    "limit_up_days",
    "source_provider",
    "source_api",
    "data_quality",
    "schema_version",
]

PUBLIC_FIELD_DESCRIPTIONS = {
    "auction_net_amount": "开盘啦原始数组字段6，对应中文业务字段‘竞价净额’",
    "auction_match_amount": "开盘啦原始数组字段10，对应中文业务字段‘竞价匹配额’",
    "main_net_amount": "开盘啦原始数组字段13，对应中文业务字段‘主力净额’",
    "main_buy_amount": "开盘啦原始数组字段14，对应中文业务字段‘主力买入’",
    "main_sell_amount": "开盘啦原始数组字段15的绝对值，对应非负‘主力卖出额’",
    "limit_up_days": "从开盘啦主字段‘连板’解析出的板数；解析失败为空",
    "snapshot_type": "正式快照类型：auction、post_open 或 close",
}
