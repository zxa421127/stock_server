# -*- coding: utf-8 -*-
"""Administrator image CAPTCHA issuance, rendering, and one-time verification."""
from __future__ import annotations

from io import BytesIO
import hashlib
import hmac
import math
import secrets
import time
from typing import MutableMapping, Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config

SESSION_KEY = "_admin_captcha_v1"
CAPTCHA_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"


def _session(session_obj: MutableMapping[str, Any] | None):
    if session_obj is not None:
        return session_obj
    from flask import session
    return session


def _secret_bytes() -> bytes:
    secret = str(getattr(config, "SECRET_KEY", "") or "")
    if len(secret) < 16:
        secret = "development-captcha-secret-please-change"
    return hashlib.sha256(("admin-captcha:" + secret).encode("utf-8")).digest()


def _digest(nonce: str, code: str) -> str:
    return hmac.new(_secret_bytes(), f"{nonce}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def issue_admin_captcha(
    session_obj: MutableMapping[str, Any] | None = None,
    *,
    length: int | None = None,
    now: float | None = None,
) -> str:
    """Issue a new CAPTCHA and replace any previous challenge in the session.

    Only a keyed digest is stored. The plaintext code is returned solely to the
    image-rendering route and must never be logged.
    """
    target = _session(session_obj)
    size = max(4, min(8, int(length or getattr(config, "ADMIN_CAPTCHA_LENGTH", 5))))
    code = "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(size))
    nonce = secrets.token_urlsafe(18)
    target[SESSION_KEY] = {
        "nonce": nonce,
        "digest": _digest(nonce, code),
        "issued_at": float(time.time() if now is None else now),
    }
    try:
        target.modified = True
    except Exception:
        pass
    return code


def verify_admin_captcha(
    session_obj: MutableMapping[str, Any] | None,
    supplied: str | None,
    *,
    now: float | None = None,
    ttl_seconds: int | None = None,
) -> bool:
    """Consume and verify a CAPTCHA challenge.

    The challenge is removed before verification, so every login attempt needs
    a freshly rendered image regardless of success or failure.
    """
    target = _session(session_obj)
    state = target.pop(SESSION_KEY, None)
    try:
        target.modified = True
    except Exception:
        pass
    if not isinstance(state, dict):
        return False
    nonce = str(state.get("nonce") or "")
    expected = str(state.get("digest") or "")
    try:
        issued_at = float(state.get("issued_at") or 0)
    except (TypeError, ValueError):
        return False
    current = float(time.time() if now is None else now)
    ttl = max(30, min(1800, int(ttl_seconds or getattr(config, "ADMIN_CAPTCHA_TTL_SECONDS", 300))))
    if not nonce or not expected or issued_at <= 0 or current < issued_at - 5 or current - issued_at > ttl:
        return False
    value = str(supplied or "").strip()
    if not value:
        return False
    return hmac.compare_digest(_digest(nonce, value), expected)


def _font(size: int):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/consolab.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_admin_captcha_png(
    code: str,
    *,
    width: int | None = None,
    height: int | None = None,
) -> bytes:
    """Render the supplied challenge as a noisy PNG without external assets."""
    width = max(120, min(320, int(width or getattr(config, "ADMIN_CAPTCHA_WIDTH", 180))))
    height = max(42, min(120, int(height or getattr(config, "ADMIN_CAPTCHA_HEIGHT", 58))))
    image = Image.new("RGB", (width, height), (247, 249, 252))
    draw = ImageDraw.Draw(image)

    # Fine noise points.
    for _ in range(max(120, width * height // 35)):
        x = secrets.randbelow(width)
        y = secrets.randbelow(height)
        shade = 110 + secrets.randbelow(110)
        draw.point((x, y), fill=(shade, shade, min(255, shade + secrets.randbelow(30))))

    # Interference lines.
    for _ in range(5):
        color = (50 + secrets.randbelow(150), 50 + secrets.randbelow(150), 50 + secrets.randbelow(150))
        points = []
        phase = secrets.randbelow(100) / 15.0
        amplitude = 3 + secrets.randbelow(max(4, height // 5))
        baseline = 8 + secrets.randbelow(max(1, height - 16))
        for x in range(-5, width + 6, 6):
            y = baseline + int(amplitude * math.sin(x / 13.0 + phase))
            points.append((x, max(0, min(height - 1, y))))
        draw.line(points, fill=color, width=1 + secrets.randbelow(2))

    font_size = max(24, int(height * 0.62))
    font = _font(font_size)
    char_width = width / max(1, len(code))
    for index, char in enumerate(code):
        tile = Image.new("RGBA", (int(char_width * 1.5), height), (255, 255, 255, 0))
        tile_draw = ImageDraw.Draw(tile)
        color = (15 + secrets.randbelow(90), 25 + secrets.randbelow(90), 45 + secrets.randbelow(100), 255)
        tile_draw.text((char_width * 0.15, -2 + secrets.randbelow(8)), char, font=font, fill=color)
        angle = -18 + secrets.randbelow(37)
        tile = tile.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)
        x = int(index * char_width - char_width * 0.08 + secrets.randbelow(max(1, int(char_width * 0.18))))
        image.paste(tile, (x, 0), tile)

    image = image.filter(ImageFilter.SMOOTH)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
