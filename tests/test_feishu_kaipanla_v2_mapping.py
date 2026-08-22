# -*- coding: utf-8 -*-
from integrations.feishu.bitable import build_bidding_fields_v2


def test_feishu_mapping_preserves_leading_zero_and_maps_final_v2_fields_without_zero_fabrication():
    fields=build_bidding_fields_v2({
        "股票代码":"000001","股票名称":"平安银行","板块":"银行、中特估","行业":"银行","连板":"6天4板","连板高度":4,
        "竞价匹配额":100,"竞价净额":7,"主力净额":30,"主力买入":50,"主力卖出额":20,
        "trade_date":"20260714","snapshot_time":"2026-07-14 09:26:05","snapshot_id":"20260714_092605_auction_x","snapshot_type":"auction",
        "source_provider":"kaipanla","data_quality":"complete","schema_version":"kaipanla_bidding.v2",
        "10":999,"15":-20,"main_sell_amount_signed":-20,"main_amount_relation_valid":True,"limit_step_nums":3,
    })
    assert fields["股票代码"] == "000001"
    assert fields["竞价匹配额"] == 100
    assert fields["竞价净额"] == 7
    assert fields["主力卖出额"] == 20
    assert fields["连板高度"] == 4
    assert fields["快照类型"] == "auction"
    for removed in ("原始字段10","原始字段15","主力卖出","主力资金关系校验","limit_step连板"):
        assert removed not in fields
    assert "当前价格" not in fields


def test_feishu_mapping_keeps_text_and_does_not_replace_none_with_zero():
    fields=build_bidding_fields_v2({"股票代码":"002243","板块":"芯片、元器件","连板":"首板","主力净额":None})
    assert isinstance(fields["股票代码"],str)
    assert isinstance(fields["板块"],str)
    assert isinstance(fields["连板"],str)
    assert "主力净额" not in fields
