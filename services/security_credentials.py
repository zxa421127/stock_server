# -*- coding: utf-8 -*-
"""Password and TOTP primitives used by production administrator authentication."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time


DEFAULT_PBKDF2_ITERATIONS = 600_000


def hash_secret(value: str, *, iterations: int = DEFAULT_PBKDF2_ITERATIONS) -> str:
    """Return a salted PBKDF2-SHA256 representation suitable for env storage."""
    iterations = max(1000, int(iterations))
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", (value or "").encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(derived).decode("ascii"),
    )


def verify_secret(value: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        scheme, iteration_text, salt_b64, digest_b64 = str(encoded).split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iteration_text)
        if iterations < 1000 or iterations > 10_000_000:
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"), validate=True)
        expected = base64.b64decode(digest_b64.encode("ascii"), validate=True)
        actual = hashlib.pbkdf2_hmac("sha256", (value or "").encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError, UnicodeError):
        return False


def _decode_base32(secret: str) -> bytes:
    normalized = "".join(str(secret or "").split()).upper()
    if not normalized:
        raise ValueError("TOTP secret is empty")
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    return base64.b32decode(normalized + padding, casefold=True)


def is_valid_totp_secret(secret: str | None, *, minimum_bytes: int = 10) -> bool:
    """Return whether *secret* is a usable RFC 6238 Base32 key."""
    try:
        return len(_decode_base32(str(secret or ""))) >= max(1, int(minimum_bytes))
    except (ValueError, TypeError, base64.binascii.Error):
        return False


def _totp_at_counter(secret: str, counter: int, *, digits: int = 6) -> str:
    key = _decode_base32(secret)
    digest = hmac.new(key, struct.pack(">Q", int(counter)), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{binary % (10 ** digits):0{digits}d}"


def verify_totp(
    secret: str | None,
    code: str | None,
    *,
    at_time: float | None = None,
    period: int = 30,
    digits: int = 6,
    valid_window: int = 1,
) -> bool:
    """Verify an RFC 6238-compatible SHA1 TOTP with a small clock-skew window."""
    supplied = "".join(str(code or "").split())
    if not secret or len(supplied) != digits or not supplied.isdigit():
        return False
    timestamp = time.time() if at_time is None else float(at_time)
    counter = int(timestamp // max(1, int(period)))
    try:
        for delta in range(-max(0, int(valid_window)), max(0, int(valid_window)) + 1):
            if hmac.compare_digest(_totp_at_counter(secret, counter + delta, digits=digits), supplied):
                return True
    except (ValueError, TypeError):
        return False
    return False
