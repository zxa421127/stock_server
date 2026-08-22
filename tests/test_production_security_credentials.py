from __future__ import annotations

import base64
import hashlib
import hmac
import struct

from services.security_credentials import hash_secret, verify_secret, verify_totp
from services.api_token_security import hash_api_token, token_display


def _totp(secret: str, counter: int, digits: int = 6) -> str:
    padding = "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode((secret + padding).upper())
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return f"{value:0{digits}d}"


def test_secret_hash_round_trip_and_rejects_wrong_value():
    encoded = hash_secret("correct horse battery staple", iterations=10_000)
    assert encoded.startswith("pbkdf2_sha256$")
    assert verify_secret("correct horse battery staple", encoded)
    assert not verify_secret("wrong", encoded)


def test_totp_accepts_current_window_and_rejects_wrong_code():
    secret = "JBSWY3DPEHPK3PXP"
    now = 1_720_000_000
    code = _totp(secret, now // 30)
    assert verify_totp(secret, code, at_time=now)
    assert not verify_totp(secret, "000000", at_time=now)


def test_api_token_hash_is_keyed_and_display_is_masked():
    token = "SK_STOCK_API_20260725120000_ABCDEFGHIJKLMNOPQRSTUVWX"
    digest1 = hash_api_token(token, "a" * 32)
    digest2 = hash_api_token(token, "b" * 32)
    assert digest1 != digest2
    display = token_display(token)
    assert token not in display
    assert display.startswith("SK_STOCK_API_")
    assert display.endswith("UVWX")
