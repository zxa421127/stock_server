# Stock Server Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Remediate all confirmed security findings while preserving current Flask routes and excluding all device-fingerprinting techniques.

**Architecture:** Add focused validation, CAPTCHA, contact-verification, session-revocation, query-policy, and bounded-cache services. Integrate them at route/service boundaries so unsafe requests are rejected before password hashing, database writes, upstream calls, DataFrame serialization, or cache insertion.

**Tech Stack:** Python 3.11+, Flask, SQLite, Redis, Pandas, pytest, SMTP, HMAC-SHA256, requests.

## Global Constraints

- Do not implement device, browser, canvas, hardware, or other fingerprinting.
- Production registration and shared security limits fail closed when Redis is unavailable.
- Registration requires at least one actually verified email or phone contact.
- Email uses SMTP; SMS uses a generic signed webhook and is optional.
- No plaintext verification code, API token, password, or production secret may be stored.
- Preserve existing public market-data route paths and response shape except sanitized error fields.
- Source and production archives must exclude `.env`, SQLite databases, `.venv`, IDE metadata, logs, caches, keys, and certificates.

---

### Task 1: Security configuration and input validation

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Create: `services/user_input_security.py`
- Test: `tests/test_user_input_security.py`

**Interfaces:**
- Produces: `normalize_registration_input(...) -> RegistrationInput`, `validate_login_input(account, password)`, `validate_password_reset_input(account, contact)`.

- [x] Write tests for username, email, phone, password, control-character, and length boundaries.
- [x] Run the focused tests and verify failure because the validation service does not exist.
- [x] Implement immutable normalized input objects and configuration values.
- [x] Run focused tests and the existing password security tests.

### Task 2: Generic attempt limiting and CAPTCHA

**Files:**
- Modify: `services/web_security.py`
- Create: `services/captcha_service.py`
- Modify: `services/admin_captcha.py`
- Test: `tests/test_registration_security_controls.py`

**Interfaces:**
- Produces: `AttemptLimiter.check_and_record(key) -> bool`, `generate_captcha(namespace)`, `verify_captcha(namespace, answer, consume=True)`.

- [x] Test that successful and failed registration attempts both consume per-IP and global quotas.
- [x] Test CAPTCHA expiry, namespace isolation, digest-only storage, and one-time use.
- [x] Implement Redis atomic counters with local fallback and production fail-closed behavior.
- [x] Adapt administrator CAPTCHA through the shared service without changing admin behavior.

### Task 3: Contact verification and two-step registration

**Files:**
- Create: `services/contact_verification.py`
- Create: `services/notification_delivery.py`
- Modify: `routes/user_routes.py`
- Modify: `services/member_service.py`
- Modify: `db_utils.py`
- Modify: `tools/db/migrate.py`
- Test: `tests/test_contact_verification.py`
- Test: `tests/test_secure_registration_flow.py`

**Interfaces:**
- Produces: `create_contact_challenge(...)`, `verify_contact_challenge(...)`, `send_email_code(...)`, `send_sms_code(...)`, `register_verified_user(...)`.

- [x] Add migration tests for verification columns and challenge table.
- [x] Add delivery tests for SMTP and signed SMS webhook.
- [x] Add route tests proving no user/API key exists before contact verification.
- [x] Implement challenge HMAC, TTL, resend delay, attempt limits, and one-time use.
- [x] Implement two-step registration and audit events.

### Task 4: Session revocation and password lifecycle

**Files:**
- Modify: `db_utils.py`
- Modify: `services/member_service.py`
- Modify: `routes/user_routes.py`
- Modify: `routes/admin_member_routes.py`
- Test: `tests/test_user_session_revocation.py`

**Interfaces:**
- Produces: `bump_user_session_version(user_id)`, `establish_user_session(user)`, `session_matches_user(user)`.

- [x] Test old-session rejection after self-change, administrator reset, and account disable.
- [x] Implement session columns and version checks.
- [x] Preserve the current browser session after self-service password change by writing the new version.
- [x] Clear all user sessions after administrator reset or disable.

### Task 5: Legacy token revocation and production checks

**Files:**
- Modify: `tools/db/migrate_legacy_tokens.py`
- Modify: `services/production_readiness.py`
- Create: `tools/security/revoke_legacy_api_tokens.py`
- Test: `tests/test_legacy_token_revocation.py`

**Interfaces:**
- Produces: `revoke_legacy_tokens(conn) -> int`, `count_active_legacy_tokens(conn) -> int`.

- [x] Test that legacy tokens are revoked and never promoted to active `api_keys`.
- [x] Test production readiness failure when active legacy tokens remain.
- [x] Implement idempotent revocation and dry-run CLI output.

### Task 6: Query policy, plan enforcement, and concurrency

**Files:**
- Create: `services/market_query_security.py`
- Modify: `middleware/auth.py`
- Modify: `routes/market_data_routes.py`
- Modify: `services/market_data_service.py`
- Modify: `services/rate_limit_service.py`
- Test: `tests/test_market_query_security.py`

**Interfaces:**
- Produces: `validate_market_query(provider, data_type, params, plan) -> dict`, `request_lease(user_id, token_id)`, `enforce_refresh_interval(...)`.

- [x] Test parameter, symbol, field, date-range, refresh-interval, and concurrency limits.
- [x] Implement provider-neutral validation before `provider.query`.
- [x] Enforce `max_symbols_per_request` and `min_refresh_interval_sec` from the active plan.
- [x] Release concurrency leases in `finally` paths.

### Task 7: Pre-serialization and cache byte limits

**Files:**
- Modify: `routes/market_data_routes.py`
- Modify: `services/market_data_cache.py`
- Test: `tests/test_market_response_limits.py`
- Test: `tests/test_market_data_cache_memory_limits.py`

**Interfaces:**
- Produces: `enforce_dataframe_limits(df, max_rows, max_bytes)`, byte-aware `TTLDataFrameCache`.

- [x] Test rejection before `DataFrame.to_json` for excessive rows or deep memory.
- [x] Test local cache item/total-byte eviction and Redis payload limits.
- [x] Implement limits and expose byte statistics.

### Task 8: Tushare HTTPS/allowlist and sanitized upstream errors

**Files:**
- Modify: `config.py`
- Modify: `integrations/tushare_client.py`
- Modify: `services/production_readiness.py`
- Modify: `routes/market_data_routes.py`
- Test: `tests/test_tushare_transport_security.py`
- Test: `tests/test_market_error_sanitization.py`

**Interfaces:**
- Produces: `validate_tushare_endpoint(url, production, allowed_hosts)`, stable `upstream_unavailable` response with `event_id`.

- [x] Test production HTTP rejection, hostname allowlist, credentials-in-URL rejection, and sanitized output.
- [x] Implement runtime and startup validation.
- [x] Log detailed errors with the same event ID without exposing them publicly.

### Task 9: Release hardening, dependency locking, and runbook

**Files:**
- Modify: `tools/release/build_production_package.py`
- Modify: `tools/security/scan_release_secrets.py`
- Modify: `.github/workflows/security.yml`
- Create: `docs/SECURITY_REMEDIATION.md`
- Create: `requirements.lock`
- Test: `tests/test_release_package_hardening.py`

**Interfaces:**
- Produces: deterministic clean archives and `SHA256SUMS.txt`.

- [x] Test exclusion of runtime and secret files and detection of credential patterns.
- [x] Harden whitelist packaging and write SHA-256 manifest.
- [x] Generate a pinned lock file from the clean environment without embedding local paths.
- [x] Document mandatory external credential rotation and deployment sequence.

### Task 10: Full verification and packaging

**Files:**
- Create: `SECURITY_FIX_CHANGELOG.md`
- Create: `TEST_REPORT.txt`

- [x] Run all security-focused tests.
- [x] Run the complete pytest suite and record any unrelated pre-existing failures accurately.
- [x] Run compile checks, release secret scanner, and production-package builder.
- [x] Inspect both archives and verify absence of `.env`, databases, `.venv`, IDE files, logs, keys, and certificates.
- [x] Generate SHA-256 hashes for deliverables.
