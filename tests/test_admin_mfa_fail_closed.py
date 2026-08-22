from __future__ import annotations

import time

import config
from services import admin_auth
from services.security_credentials import _totp_at_counter


def test_legacy_totp_helpers_remain_available_for_rollback(monkeypatch):
    secret = "JBSWY3DPEHPK3PXP"
    monkeypatch.setattr(config, "ADMIN_REQUIRE_MFA", True)
    monkeypatch.setattr(config, "ADMIN_TOTP_SECRET", secret)
    code = _totp_at_counter(secret, int(time.time() // 30))
    assert admin_auth.admin_mfa_configured()
    assert admin_auth.verify_admin_mfa(code)


def test_legacy_totp_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_REQUIRE_MFA", False)
    monkeypatch.setattr(config, "ADMIN_TOTP_SECRET", "")
    assert admin_auth.verify_admin_mfa("")
