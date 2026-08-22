from __future__ import annotations

import pandas as pd
from flask import Flask, g

from services.market_data_service import MarketDataResult
import routes.market_data_routes as routes


def test_upstream_error_response_does_not_expose_detail_or_token(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test"
    leaked = "RuntimeError: relay failed token=VERY_SECRET_TOKEN at 10.0.0.9"
    monkeypatch.setattr(
        routes,
        "query_market_data",
        lambda *a, **k: MarketDataResult(
            provider="tushare", data_type="daily", data=pd.DataFrame(), error=leaked,
            meta={"http_status": 502},
        ),
    )
    monkeypatch.setattr(routes, "validate_market_query", lambda p, d, params, plan: params)
    monkeypatch.setattr(routes, "enforce_refresh_interval", lambda *a, **k: None)

    class Lease:
        def __enter__(self): return self
        def __exit__(self, *args): return False
    monkeypatch.setattr(routes, "request_lease", lambda *a, **k: Lease())

    with app.test_request_context("/api/v1/market/tushare/daily"):
        g.current_plan = {"plan_type": "admin"}
        g.current_user = {"id": 1, "api_key_id": 2}
        response, status = routes._query_response("tushare", "daily")
        payload = response.get_json()

    assert status == 502
    assert payload["error_code"] == "upstream_unavailable"
    assert payload["msg"] == "上游数据服务暂时不可用"
    assert payload["event_id"]
    assert "VERY_SECRET_TOKEN" not in str(payload)
    assert "10.0.0.9" not in str(payload)
def _invoke_market_query_exception(monkeypatch, exc, *, stage):
    app = Flask(__name__)
    with app.test_request_context("/"):
        g.current_plan = {}
        g.current_user = {}

        def _raise(*args, **kwargs):
            raise exc

        if stage == "pagination":
            monkeypatch.setattr(
                routes,
                "_extract_pagination_controls",
                _raise,
            )
        elif stage == "validation":
            monkeypatch.setattr(
                routes,
                "_extract_pagination_controls",
                lambda *args, **kwargs: {},
            )
            monkeypatch.setattr(
                routes,
                "validate_market_query",
                _raise,
            )
        else:
            raise AssertionError(f"unsupported stage: {stage}")

        response, status = routes._query_response(
            "synthetic",
            "daily",
        )
        return response.get_json(), status


def test_controlled_public_validation_message_is_preserved(monkeypatch):
    payload, status = _invoke_market_query_exception(
        monkeypatch,
        routes.PublicValidationError("cursor不能为空"),
        stage="pagination",
    )

    assert status == 400
    assert payload["success"] is False
    assert payload["code"] == 400
    assert payload["items"] == []
    assert payload["msg"] == "cursor不能为空"


def test_controlled_pagination_helper_uses_public_validation_exception():
    try:
        routes._decode_pagination_cursor("")
    except routes.PublicValidationError as exc:
        assert str(exc) == "cursor不能为空"
    else:
        raise AssertionError(
            "_decode_pagination_cursor did not raise PublicValidationError"
        )


def test_generic_keyerror_message_is_not_reflected(monkeypatch):
    secret = "INTERNAL_KEY_NAME_SHOULD_NOT_LEAK"
    payload, status = _invoke_market_query_exception(
        monkeypatch,
        KeyError(secret),
        stage="validation",
    )

    assert status == 404
    assert payload["success"] is False
    assert payload["code"] == 404
    assert payload["items"] == []
    assert payload["msg"] == "请求资源不存在"
    assert secret not in payload["msg"]


def test_generic_valueerror_message_is_not_reflected(monkeypatch):
    secret = "INTERNAL_VALUE_DETAIL_SHOULD_NOT_LEAK"
    payload, status = _invoke_market_query_exception(
        monkeypatch,
        ValueError(secret),
        stage="validation",
    )

    assert status == 400
    assert payload["success"] is False
    assert payload["code"] == 400
    assert payload["items"] == []
    assert payload["msg"] == "请求参数无效"
    assert secret not in payload["msg"]
