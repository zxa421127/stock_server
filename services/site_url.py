# -*- coding: utf-8 -*-
"""Cross-domain web URL helpers for the public and administrator sites.

Stock Server deliberately separates browser traffic into two hosts:
- public host: ``api.*`` / ``test-api.*`` / ``local-api.*`` for ``/user`` pages;
- admin host: ``admin-api.*`` / ``test-admin-api.*`` / ``local-admin-api.*`` for ``/admin`` pages.

The administrator host is already an environment identity setting.  These
helpers derive the matching public host from that existing setting so page
links do not hard-code test/production domains and cannot accidentally keep
using the current host for a cross-domain link.
"""
from __future__ import annotations

from urllib.parse import urlsplit

import config


def _admin_host() -> str:
    """Return the configured administrator host without scheme/path noise."""
    raw = str(
        getattr(config, "ADMIN_CLIENT_CERT_ADMIN_HOST", "")
        or getattr(config, "EXPECTED_ADMIN_HOST", "")
        or ""
    ).strip()
    if not raw:
        return ""
    candidate = raw if "://" in raw else f"//{raw}"
    parsed = urlsplit(candidate)
    return str(parsed.hostname or "").strip().lower()


def public_host_from_admin_host(admin_host: str) -> str:
    """Derive the paired public host from the configured administrator host.

    Examples:
    - admin-api.example.com -> api.example.com
    - test-admin-api.example.com -> test-api.example.com
    - local-admin-api.example.com -> local-api.example.com
    """
    host = str(admin_host or "").strip().lower().rstrip(".")
    if not host:
        return ""
    if host.startswith("admin-api."):
        return "api." + host[len("admin-api."):]
    marker = "-admin-api."
    if marker in host:
        return host.replace(marker, "-api.", 1)
    return ""


def public_url(path: str) -> str:
    """Return a public-site URL for a path, falling back to a relative path.

    Production/test/local HTTPS deployments automatically use the domain paired
    with ``ADMIN_CLIENT_CERT_ADMIN_HOST``.  Direct local Gate-1 development can
    leave the admin host empty and keep same-origin relative links.
    """
    normalized_path = "/" + str(path or "").lstrip("/")
    public_host = public_host_from_admin_host(_admin_host())
    if not public_host:
        return normalized_path
    return f"https://{public_host}{normalized_path}"


def admin_url(path: str) -> str:
    """Return an administrator-site URL for a path, or a relative fallback."""
    normalized_path = "/" + str(path or "").lstrip("/")
    admin_host = _admin_host()
    if not admin_host:
        return normalized_path
    return f"https://{admin_host}{normalized_path}"
