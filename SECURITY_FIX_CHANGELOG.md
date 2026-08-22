# Security fix changelog

## Scope

This release remediates the confirmed findings from the static audit of the supplied stock-server archive. Device, browser, canvas and hardware fingerprinting are explicitly not implemented.

## Registration and contact verification

- Every registration attempt consumes both per-IP and global quotas; successful registration no longer clears counters.
- Added namespaced, one-time, digest-only CAPTCHA challenges.
- Added two-step registration. No user or API key is created before a contact challenge is verified.
- Added SMTP email verification and an optional HTTPS HMAC-signed SMS webhook.
- Added challenge TTL, resend cooldown, maximum attempts, one-time consumption and delivery-failure tracking.
- Added strict username, password, email, phone, login and password-reset length/format validation.

## Accounts, sessions and tokens

- Added `session_version` and `password_changed_at` lifecycle fields.
- Password changes, administrator resets and account disable operations invalidate old sessions.
- Self-service password change retains only the current refreshed session.
- New API tokens use cryptographically random `token_urlsafe` material and remain digest-only at rest.
- Legacy plaintext `api_tokens` are revoked rather than promoted into the new token table.
- Production startup rejects databases that still contain active legacy tokens.

## API resource protection

- Added pre-upstream parameter count, key/value size, field count, symbol count and date-span validation.
- Enforced active-plan `max_symbols_per_request` and `min_refresh_interval_sec` values.
- Added per-user, per-token and global concurrency leases with bounded Redis TTL and safe local fallback.
- Added pre-serialization DataFrame row and deep-memory limits.
- Added byte-aware local LRU cache budgets, maximum cache rows and bounded Redis compression/decompression.

## Upstream transport and error handling

- Production custom Tushare relays now require HTTPS and an exact hostname allowlist.
- Relay URLs containing credentials or fragments are rejected.
- Redirects are disabled, connect/read timeouts are separated and response bodies are bounded.
- Public upstream failures return a stable safe message and event ID; detailed errors remain server-side.

## Release and production safety

- Expanded production readiness checks for verified registration channels, SMTP/SMS configuration and Tushare relay security.
- Hardened allowlist packaging and secret scanning for `.env`, databases, virtual environments, logs, IDE files, keys and certificates.
- Production archives contain `RELEASE_MANIFEST.json` and `SHA256SUMS.txt`.
- Added exact direct dependency pins and CI installation/audit from `requirements.lock`.
- Added a credential-rotation and deployment runbook.
