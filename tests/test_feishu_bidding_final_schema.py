# -*- coding: utf-8 -*-
from integrations.feishu.bitable import BIDDING_FIELD_SPECS, FeishuBitableManager, build_bidding_fields_v2

EXPECTED = [
'股票代码','股票名称','当前价格','实时涨幅','竞价涨幅','涨停委买额','20分后涨停委买','竞价匹配额','竞价成交额','竞价净额','竞价换手','主力净额','主力买入','主力卖出额','实际流通','板块','行业','连板','连板高度','交易日期','快照时间','快照ID','快照类型','数据源','数据质量','Schema版本'
]

def test_final_field_list_and_mapping_have_no_obsolete_fields():
    assert list(BIDDING_FIELD_SPECS) == EXPECTED
    fields = build_bidding_fields_v2({
        '股票代码':'000001','股票名称':'平安银行','竞价净额':12,'主力净额':3,'主力买入':5,'主力卖出额':2,
        'industry':'银行','连板':'4天3板','limit_up_days':3,'trade_date':'20260723','snapshot_time':'2026-07-23 09:31:00','snapshot_id':'id','snapshot_type':'post_open','source_provider':'kaipanla','data_quality':'complete','schema_version':'kaipanla_bidding.v2',
        '10':99,'main_sell_amount_signed':-2,'field_validation_warning':'bad','limit_step_nums':9,
    })
    assert fields['竞价净额'] == 12
    assert fields['快照类型'] == 'post_open'
    assert fields['行业'] == '银行'
    for obsolete in ('原始字段10','主力卖出','字段校验警告','limit_step连板'):
        assert obsolete not in fields


def test_invalid_or_missing_date_never_uses_current_time():
    manager = object.__new__(FeishuBitableManager)
    assert manager._str_to_ms(None) is None
    assert manager._str_to_ms('not-a-date') is None


def test_unique_key_accepts_feishu_rich_text_values():
    manager = FeishuBitableManager.__new__(FeishuBitableManager)
    fields = {
        "快照ID": [{"text": "20260723_092605_auction_abcd"}],
        "股票代码": [{"text": "000001"}],
    }
    assert manager._bidding_unique_key(fields) == "20260723_092605_auction_abcd|000001"


def test_naive_snapshot_time_is_interpreted_as_asia_shanghai():
    manager = FeishuBitableManager.__new__(FeishuBitableManager)
    from datetime import datetime
    from zoneinfo import ZoneInfo
    expected = int(datetime(2026, 7, 23, 9, 26, 5, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000)
    assert manager._str_to_ms("2026-07-23 09:26:05") == expected
