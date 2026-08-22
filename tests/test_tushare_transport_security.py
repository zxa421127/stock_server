from __future__ import annotations

import pytest

from integrations.market_data.tushare.client import validate_tushare_endpoint


def test_production_rejects_plain_http_relay():
    with pytest.raises(RuntimeError, match="HTTPS"):
        validate_tushare_endpoint(
            "http://relay.example.com/dataapi", production=True, allowed_hosts=["relay.example.com"]
        )


def test_relay_hostname_must_be_allowlisted():
    with pytest.raises(RuntimeError, match="允许列表"):
        validate_tushare_endpoint(
            "https://evil.example/dataapi", production=True, allowed_hosts=["relay.example.com"]
        )


def test_url_credentials_are_rejected():
    with pytest.raises(RuntimeError, match="用户名或密码"):
        validate_tushare_endpoint(
            "https://user:pass@relay.example.com/dataapi",
            production=True,
            allowed_hosts=["relay.example.com"],
        )


def test_production_accepts_https_allowlisted_relay():
    parsed = validate_tushare_endpoint(
        "https://relay.example.com/dataapi", production=True, allowed_hosts=["relay.example.com"]
    )
    assert parsed.hostname == "relay.example.com"


def test_empty_url_keeps_official_sdk_mode():
    assert validate_tushare_endpoint("", production=True, allowed_hosts=[]) is None
