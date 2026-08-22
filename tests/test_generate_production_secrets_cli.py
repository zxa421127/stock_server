from __future__ import annotations

import sys

from tools.security import generate_production_secrets


def test_cli_prompts_for_password_instead_of_requiring_command_line_secret(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["generate_production_secrets"])
    prompts = iter(["A-very-strong-admin-password-123", "A-very-strong-admin-password-123"])
    monkeypatch.setattr(generate_production_secrets.getpass, "getpass", lambda prompt: next(prompts))

    assert generate_production_secrets.main() == 0
    output = capsys.readouterr().out
    assert "ADMIN_PASSWORD_HASH=pbkdf2_sha256$" in output
    assert "CONTACT_VERIFICATION_HMAC_SECRET=" in output
    assert "SMS_VERIFY_WEBHOOK_SECRET=" in output
    assert "A-very-strong-admin-password-123" not in output


def test_cli_can_read_password_from_named_environment_variable(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_production_secrets", "--admin-password-env", "STOCK_TEST_ADMIN_PASSWORD"],
    )
    monkeypatch.setenv("STOCK_TEST_ADMIN_PASSWORD", "Another-strong-admin-password-456")

    assert generate_production_secrets.main() == 0
    output = capsys.readouterr().out
    assert "ADMIN_PASSWORD_HASH=pbkdf2_sha256$" in output
    assert "Another-strong-admin-password-456" not in output
