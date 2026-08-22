from __future__ import annotations

import pytest

import services.market_query_security as security


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    security.reset_query_security_state()
    monkeypatch.setattr(security, "get_redis", lambda: None)
    monkeypatch.setattr(security.config, "REDIS_REQUIRED", False, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_MAX_PARAMS", 4, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_MAX_FIELDS", 3, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_MAX_PARAM_KEY_LENGTH", 32, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_MAX_PARAM_VALUE_LENGTH", 128, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_DEFAULT_MAX_DATE_SPAN_DAYS", 30, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_INTRADAY_MAX_DATE_SPAN_DAYS", 7, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_FINANCIAL_MAX_DATE_SPAN_DAYS", 3650, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_DATE_SPAN_OVERRIDES", {}, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_MAX_CONCURRENT_PER_USER", 1, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_MAX_CONCURRENT_PER_TOKEN", 1, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_MAX_CONCURRENT_GLOBAL", 2, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_USER", 2, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_TOKEN", 2, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_USER", 4, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_TOKEN", 4, raising=False)
    monkeypatch.setattr(security.config, "MARKET_QUERY_CONCURRENCY_RETRY_AFTER_SECONDS", 2, raising=False)
    yield
    security.reset_query_security_state()


def test_rejects_excessive_parameter_count():
    with pytest.raises(security.QuerySecurityError) as exc:
        security.validate_market_query("tushare", "daily", {str(i): i for i in range(5)}, {})
    assert exc.value.reason == "parameter_count"


def test_rejects_symbol_count_from_active_plan():
    plan = {"max_symbols_per_request": 2}
    with pytest.raises(security.QuerySecurityError) as exc:
        security.validate_market_query(
            "tushare", "daily", {"ts_code": "000001.SZ,000002.SZ,000003.SZ"}, plan
        )
    assert exc.value.reason == "symbols"


def test_rejects_too_many_requested_fields():
    with pytest.raises(security.QuerySecurityError) as exc:
        security.validate_market_query("tushare", "daily", {"fields": "a,b,c,d"}, {})
    assert exc.value.reason == "fields"


def test_rejects_excessive_date_span_before_upstream_call():
    with pytest.raises(security.QuerySecurityError) as exc:
        security.validate_market_query(
            "tushare", "daily", {"start_date": "20260101", "end_date": "20260215"}, {}
        )
    assert exc.value.reason == "date_span"
    assert "分段查询" in str(exc.value)


def test_financial_interfaces_receive_longer_date_policy():
    params = {"start_date": "20200101", "end_date": "20260101"}
    assert security.validate_market_query("tushare", "income", params, {}) == params


def test_refresh_interval_is_enforced_per_token(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(security.time, "time", lambda: now[0])
    plan = {"min_refresh_interval_sec": 10}
    security.enforce_refresh_interval(7, 11, "tushare", "daily", plan)
    with pytest.raises(security.QuerySecurityError) as exc:
        security.enforce_refresh_interval(7, 11, "tushare", "daily", plan)
    assert exc.value.reason == "refresh_interval"
    now[0] += 10
    security.enforce_refresh_interval(7, 11, "tushare", "daily", plan)


def test_concurrency_lease_releases_even_when_request_raises():
    with pytest.raises(RuntimeError):
        with security.request_lease(7, 11):
            raise RuntimeError("upstream failed")
    with security.request_lease(7, 11):
        pass


def test_concurrency_limit_rejects_second_active_lease():
    with security.request_lease(7, 11):
        with pytest.raises(security.QuerySecurityError) as exc:
            with security.request_lease(7, 11):
                pass
    assert exc.value.reason == "concurrency"

def test_plan_aware_concurrency_limits_keep_admin_on_legacy_fallback():
    assert security.concurrency_limits_for_plan({"plan_type": "general"})[:3] == (2, 2, 2)
    assert security.concurrency_limits_for_plan({"plan_type": "special"})[:3] == (4, 4, 2)
    # Admin does not inherit Special's wider token limit.
    assert security.concurrency_limits_for_plan({"plan_type": "admin"})[:3] == (1, 1, 2)


def test_general_plan_allows_two_active_leases_and_rejects_third():
    plan = {"plan_type": "general"}
    with security.request_lease(70, 110, plan):
        with security.request_lease(70, 110, plan):
            with pytest.raises(security.QuerySecurityError) as exc:
                with security.request_lease(70, 110, plan):
                    pass
    assert exc.value.reason == "concurrency"
    assert exc.value.status_code == 429
    assert exc.value.retry_after == 2


def test_special_plan_allows_four_active_leases_and_rejects_fifth(monkeypatch):
    plan = {"plan_type": "special"}
    monkeypatch.setattr(security.config, "MARKET_QUERY_MAX_CONCURRENT_GLOBAL", 5, raising=False)
    with security.request_lease(71, 111, plan):
        with security.request_lease(71, 111, plan):
            with security.request_lease(71, 111, plan):
                with security.request_lease(71, 111, plan):
                    with pytest.raises(security.QuerySecurityError) as exc:
                        with security.request_lease(71, 111, plan):
                            pass
    assert exc.value.reason == "concurrency"
    assert exc.value.retry_after == 2

