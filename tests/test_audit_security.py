from __future__ import annotations

from services.audit_security import (
    mask_email,
    mask_phone,
    mask_record,
    mask_sensitive_structure,
    mask_text,
    safe_csv_cell,
    sanitize_error_message,
    sanitize_mapping,
    token_fingerprint,
)


def test_sanitize_mapping_redacts_nested_credentials_case_insensitively():
    raw = {
        "username": "alice",
        "Password": "plain-secret",
        "nested": {
            "X-API-Token": "token-secret",
            "items": [{"authorization": "Bearer secret"}, {"value": 3}],
        },
        "cookieJar": "session-cookie",
    }
    cleaned = sanitize_mapping(raw)
    assert cleaned["username"] == "alice"
    assert cleaned["Password"] == "[REDACTED]"
    assert cleaned["nested"]["X-API-Token"] == "[REDACTED]"
    assert cleaned["nested"]["items"][0]["authorization"] == "[REDACTED]"
    assert cleaned["nested"]["items"][1]["value"] == 3
    assert cleaned["cookieJar"] == "[REDACTED]"
    serialized = str(cleaned)
    assert "plain-secret" not in serialized
    assert "token-secret" not in serialized
    assert "Bearer secret" not in serialized


def test_sanitize_mapping_truncates_oversized_payload():
    cleaned = sanitize_mapping({"note": "x" * 200}, max_chars=60)
    assert cleaned["truncated"] is True
    assert len(cleaned["preview"]) <= 60


def test_mask_helpers_preserve_edges():
    assert mask_phone("13812345678") == "138****5678"
    assert mask_phone("1234") == "1**4"
    assert mask_email("susan.adamu@example.com") == "sus***@example.com"
    assert mask_email("a@b.com") == "a***@b.com"
    assert mask_text("张三") == "张*"
    assert mask_text("苏珊阿达姆") == "苏***姆"


def test_mask_record_masks_only_sensitive_business_fields():
    row = {"phone": "13812345678", "target_email": "a@example.com", "client_ip": "1.2.3.4"}
    masked = mask_record(row)
    assert masked["phone"] == "138****5678"
    assert masked["target_email"] == "a***@example.com"
    assert masked["client_ip"] == "1.2.3.4"


def test_token_fingerprint_is_deterministic_hmac_and_never_contains_token():
    first = token_fingerprint("raw-token", "server-secret")
    second = token_fingerprint("raw-token", "server-secret")
    other = token_fingerprint("raw-token", "other-secret")
    assert first == second
    assert first != other
    assert len(first) == 64
    assert "raw-token" not in first
    assert token_fingerprint("", "server-secret") == ""


def test_safe_csv_cell_blocks_formula_injection_and_serializes_structures():
    assert safe_csv_cell("=SUM(A1:A2)") == "'=SUM(A1:A2)"
    assert safe_csv_cell(" +cmd") == "' +cmd"
    assert safe_csv_cell("normal") == "normal"
    assert safe_csv_cell(None) == ""
    assert safe_csv_cell({"a": 1}) == '{"a": 1}'


def test_mask_sensitive_structure_masks_nested_phone_email_but_keeps_ip():
    value = {
        "target": {"phone": "13812345678", "email": "alice@example.com"},
        "rows": [{"mobile_phone": "13912345678", "contact_email": "b@example.com"}],
        "client_ip": "1.2.3.4",
    }
    masked = mask_sensitive_structure(value)
    assert masked["target"]["phone"] == "138****5678"
    assert masked["target"]["email"] == "ali***@example.com"
    assert masked["rows"][0]["mobile_phone"] == "139****5678"
    assert masked["rows"][0]["contact_email"] == "b***@example.com"
    assert masked["client_ip"] == "1.2.3.4"


def test_sanitize_error_message_redacts_labeled_credentials_and_bearer_tokens():
    text = "request failed password=plain-secret X-API-Token: raw-token Authorization: Bearer abc.def.ghi"
    cleaned = sanitize_error_message(text, max_chars=500)
    assert "plain-secret" not in cleaned
    assert "raw-token" not in cleaned
    assert "abc.def.ghi" not in cleaned
    assert cleaned.count("[REDACTED]") >= 3


def test_sanitize_mapping_redacts_credentials_embedded_in_string_values():
    cleaned = sanitize_mapping({"note": "call failed X-API-Token: raw-embedded-token Authorization: Bearer abc.xyz"})
    assert "raw-embedded-token" not in cleaned["note"]
    assert "abc.xyz" not in cleaned["note"]
    assert "[REDACTED]" in cleaned["note"]
