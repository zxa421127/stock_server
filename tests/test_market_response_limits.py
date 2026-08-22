from __future__ import annotations

import pytest

from routes.market_data_routes import ResponseLimitExceeded, enforce_response_limits


def test_response_limit_rejects_too_many_rows():
    with pytest.raises(ResponseLimitExceeded) as exc:
        enforce_response_limits([{"x": 1}, {"x": 2}], max_rows=1, max_bytes=1000)
    assert exc.value.reason == "rows"


def test_response_limit_rejects_too_many_bytes():
    with pytest.raises(ResponseLimitExceeded) as exc:
        enforce_response_limits([{"x": "a" * 100}], max_rows=10, max_bytes=20)
    assert exc.value.reason == "bytes"


def test_response_limit_accepts_small_payload():
    enforce_response_limits([{"x": 1}], max_rows=10, max_bytes=1000)


def test_dataframe_row_limit_is_checked_before_json_serialization(monkeypatch):
    import pandas as pd
    from routes.market_data_routes import enforce_dataframe_limits

    frame = pd.DataFrame([{"x": 1}, {"x": 2}])
    monkeypatch.setattr(pd.DataFrame, "to_json", lambda self, *a, **k: (_ for _ in ()).throw(AssertionError("serialized")))
    with pytest.raises(ResponseLimitExceeded) as exc:
        enforce_dataframe_limits(frame, max_rows=1, max_bytes=10_000)
    assert exc.value.reason == "rows"


def test_dataframe_deep_memory_limit_is_checked_before_serialization():
    import pandas as pd
    from routes.market_data_routes import enforce_dataframe_limits

    frame = pd.DataFrame([{"x": "a" * 1000}])
    with pytest.raises(ResponseLimitExceeded) as exc:
        enforce_dataframe_limits(frame, max_rows=10, max_bytes=100)
    assert exc.value.reason == "dataframe_bytes"

def test_full_market_row_limit_overrides_are_interface_specific(monkeypatch):
    import routes.market_data_routes as routes

    monkeypatch.setattr(routes.config, "API_MAX_RESPONSE_ROWS", 5000)
    monkeypatch.setattr(
        routes.config,
        "API_MAX_RESPONSE_ROWS_OVERRIDES",
        {
            "tushare.stock_basic": 10000,
            "tushare.daily": 10000,
            "tushare.daily_basic": 10000,
            "tushare.stk_limit": 10000,
            "tushare.bak_daily": 10000,
        },
    )

    assert routes.response_row_limit_for("tushare", "stock_basic") == 10000
    assert routes.response_row_limit_for("tushare", "daily") == 10000
    assert routes.response_row_limit_for("tushare", "daily_basic") == 10000
    assert routes.response_row_limit_for("tushare", "stk_limit") == 10000
    assert routes.response_row_limit_for("tushare", "bak_daily") == 10000
    assert routes.response_row_limit_for("kaipanla", "stock_basic") == 5000
    assert routes.response_row_limit_for("tushare", "income") == 5000

def test_unscoped_row_override_cannot_leak_across_providers(monkeypatch):
    import routes.market_data_routes as routes

    monkeypatch.setattr(routes.config, "API_MAX_RESPONSE_ROWS", 5000)
    monkeypatch.setattr(
        routes.config,
        "API_MAX_RESPONSE_ROWS_OVERRIDES",
        {"stock_basic": 10000},
    )
    assert routes.response_row_limit_for("tushare", "stock_basic") == 5000
    assert routes.response_row_limit_for("kaipanla", "stock_basic") == 5000


def test_query_response_holds_lease_through_serialization(monkeypatch):
    from contextlib import contextmanager

    import pandas as pd
    from flask import Flask, g

    import routes.market_data_routes as routes
    from services.market_data_service import MarketDataResult

    app = Flask(__name__)
    state = {"active": False, "plan_type": None}

    @contextmanager
    def fake_lease(user_id, token_id, plan=None):
        assert user_id == 7
        assert token_id == 11
        state["plan_type"] = (plan or {}).get("plan_type")
        state["active"] = True
        try:
            yield
        finally:
            state["active"] = False

    real_safe_records = routes._safe_records
    real_jsonify = routes.jsonify

    def guarded_safe_records(df):
        assert state["active"] is True
        return real_safe_records(df)

    def guarded_jsonify(*args, **kwargs):
        assert state["active"] is True
        return real_jsonify(*args, **kwargs)

    monkeypatch.setattr(routes, "request_lease", fake_lease)
    monkeypatch.setattr(routes, "enforce_refresh_interval", lambda *a, **k: None)
    monkeypatch.setattr(routes, "_safe_records", guarded_safe_records)
    monkeypatch.setattr(routes, "jsonify", guarded_jsonify)
    monkeypatch.setattr(
        routes,
        "query_market_data",
        lambda *a, **k: MarketDataResult(
            provider="tushare",
            data_type="daily",
            data=pd.DataFrame([{"x": 1}]),
        ),
    )

    with app.test_request_context("/?trade_date=20260814"):
        g.current_user = {"id": 7, "api_key_id": 11}
        g.current_plan = {"plan_type": "general", "max_symbols_per_request": 100}
        response = routes._query_response("tushare", "daily")

    assert response.status_code == 200
    assert state["active"] is False
    assert state["plan_type"] == "general"


def test_concurrency_429_returns_retry_after_header(monkeypatch):
    from contextlib import contextmanager

    from flask import Flask, g

    import routes.market_data_routes as routes
    from services.market_query_security import QuerySecurityError

    app = Flask(__name__)

    @contextmanager
    def rejected_lease(user_id, token_id, plan=None):
        raise QuerySecurityError(
            "并发请求已达上限",
            reason="concurrency",
            status_code=429,
            retry_after=3,
        )
        yield

    monkeypatch.setattr(routes, "request_lease", rejected_lease)
    monkeypatch.setattr(routes, "enforce_refresh_interval", lambda *a, **k: None)

    with app.test_request_context("/?trade_date=20260814"):
        g.current_user = {"id": 7, "api_key_id": 11}
        g.current_plan = {"plan_type": "general", "max_symbols_per_request": 100}
        response, status = routes._query_response("tushare", "daily")

    assert status == 429
    assert response.headers["Retry-After"] == "3"
    assert response.get_json()["error_code"] == "concurrency"


def test_full_market_route_accepts_5539_rows(monkeypatch):
    from contextlib import nullcontext

    import pandas as pd
    from flask import Flask, g

    import routes.market_data_routes as routes
    from services.market_data_service import MarketDataResult

    app = Flask(__name__)
    monkeypatch.setattr(routes.config, "API_MAX_RESPONSE_ROWS", 5000)
    monkeypatch.setattr(
        routes.config,
        "API_MAX_RESPONSE_ROWS_OVERRIDES",
        {
            "tushare.stock_basic": 10000,
            "tushare.daily": 10000,
            "tushare.daily_basic": 10000,
            "tushare.stk_limit": 10000,
            "tushare.bak_daily": 10000,
        },
    )
    monkeypatch.setattr(routes, "request_lease", lambda *a, **k: nullcontext())
    monkeypatch.setattr(routes, "enforce_refresh_interval", lambda *a, **k: None)
    monkeypatch.setattr(
        routes,
        "query_market_data",
        lambda *a, **k: MarketDataResult(
            provider="tushare",
            data_type="stock_basic",
            data=pd.DataFrame({"x": range(5539)}),
        ),
    )

    with app.test_request_context("/?list_status=L"):
        g.current_user = {"id": 7, "api_key_id": 11}
        g.current_plan = {"plan_type": "general", "max_symbols_per_request": 100}
        response = routes._query_response("tushare", "stock_basic")

    assert response.status_code == 200
    assert response.get_json()["count"] == 5539


def test_non_whitelisted_route_rejects_5539_rows(monkeypatch):
    from contextlib import nullcontext

    import pandas as pd
    from flask import Flask, g

    import routes.market_data_routes as routes
    from services.market_data_service import MarketDataResult

    app = Flask(__name__)
    monkeypatch.setattr(routes.config, "API_MAX_RESPONSE_ROWS", 5000)
    monkeypatch.setattr(
        routes.config,
        "API_MAX_RESPONSE_ROWS_OVERRIDES",
        {
            "tushare.stock_basic": 10000,
            "tushare.daily": 10000,
            "tushare.daily_basic": 10000,
            "tushare.stk_limit": 10000,
            "tushare.bak_daily": 10000,
        },
    )
    monkeypatch.setattr(routes, "request_lease", lambda *a, **k: nullcontext())
    monkeypatch.setattr(routes, "enforce_refresh_interval", lambda *a, **k: None)
    monkeypatch.setattr(
        routes,
        "query_market_data",
        lambda *a, **k: MarketDataResult(
            provider="tushare",
            data_type="income",
            data=pd.DataFrame({"x": range(5539)}),
        ),
    )

    with app.test_request_context("/?ann_date=20260814"):
        g.current_user = {"id": 7, "api_key_id": 11}
        g.current_plan = {"plan_type": "general", "max_symbols_per_request": 100}
        response, status = routes._query_response("tushare", "income")

    assert status == 413
    payload = response.get_json()
    assert payload["limit"]["reason"] == "rows"
    assert payload["limit"]["maximum"] == 5000
    assert "分段查询" in payload["msg"]


def test_full_market_route_still_rejects_10001_rows(monkeypatch):
    from contextlib import nullcontext

    import pandas as pd
    from flask import Flask, g

    import routes.market_data_routes as routes
    from services.market_data_service import MarketDataResult

    app = Flask(__name__)
    monkeypatch.setattr(routes.config, "API_MAX_RESPONSE_ROWS", 5000)
    monkeypatch.setattr(
        routes.config,
        "API_MAX_RESPONSE_ROWS_OVERRIDES",
        {
            "tushare.stock_basic": 10000,
            "tushare.daily": 10000,
            "tushare.daily_basic": 10000,
            "tushare.stk_limit": 10000,
            "tushare.bak_daily": 10000,
        },
    )
    monkeypatch.setattr(routes, "request_lease", lambda *a, **k: nullcontext())
    monkeypatch.setattr(routes, "enforce_refresh_interval", lambda *a, **k: None)
    monkeypatch.setattr(
        routes,
        "query_market_data",
        lambda *a, **k: MarketDataResult(
            provider="tushare",
            data_type="stock_basic",
            data=pd.DataFrame({"x": range(10001)}),
        ),
    )

    with app.test_request_context("/?list_status=L"):
        g.current_user = {"id": 7, "api_key_id": 11}
        g.current_plan = {"plan_type": "general", "max_symbols_per_request": 100}
        response, status = routes._query_response("tushare", "stock_basic")

    assert status == 413
    assert response.get_json()["limit"]["maximum"] == 10000

