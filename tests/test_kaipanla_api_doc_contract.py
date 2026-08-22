# -*- coding: utf-8 -*-
from services.api_doc_catalog import FULL_API_DOCS


def _doc(name: str) -> dict:
    return next(item for item in FULL_API_DOCS if item.get("provider") == "kaipanla" and item.get("api_name") == name)


def test_history_doc_describes_three_snapshot_types_and_ids():
    doc = _doc("morning_bidding_history")
    params = {item["name"]: item for item in doc["params"]}
    assert params["snapshot_type"]["example"] == "auction"
    assert "auction、post_open 或 close" in params["snapshot_type"]["description"]
    assert "snapshot_type=auction" in doc["request_example"]
    assert "snapshot_type=close" in doc["request_example"]
    assert "15:01:00" in doc["description"]
    assert "close不存在时返回404" in doc["description"]
    assert "_092605_auction_" in doc["response_example"]
    assert '"snapshot_type": "auction"' in doc["response_example"]


def test_live_doc_uses_final_v2_business_fields_only():
    text = _doc("morning_bidding")["response_example"]
    assert '"auction_net_amount"' in text
    assert '"auction_match_amount"' in text
    assert '"main_net_amount"' in text
    assert '"main_buy_amount"' in text
    assert '"main_sell_amount"' in text
    for removed in ("auction_buy_amount", "auction_sell_amount", "main_sell_amount_signed", "main_amount_relation_valid"):
        assert removed not in text
