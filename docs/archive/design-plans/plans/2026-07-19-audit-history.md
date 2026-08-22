# Audit History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add durable operation history and complete `/api/...` access history with administrator-only search, masked details, second-factor password reveal, CSV export, retention cleanup, and crash recovery.

**Architecture:** Keep existing exact daily usage counters and legacy sampled `usage_logs` unchanged, while adding two new append-only audit tables in `tokens.db`. Every API response is captured by Flask request hooks and synchronously persisted to a separate SQLite spool before a background worker inserts it into the main database; operation events use the same persistence service. Admin pages query the main audit tables, mask sensitive business values by default, and require the current administrator password before revealing or exporting full values.

**Tech Stack:** Python 3.13, Flask, Waitress, SQLite, standard-library `csv`, `hmac`, `hashlib`, `json`, `threading`, `uuid`, `pathlib`, pytest.

## Global Constraints

- Preserve the existing Flask blueprints, inline-HTML style, member data model, plan behavior, exact daily counters, rate limiting, API response formats, and Waitress startup.
- Record every `/api` and `/api/...` request, including missing/invalid tokens, authorization failures, rate limits, unknown API paths, and unhandled errors.
- Do not record ordinary `/admin/...`, `/user/...`, or `/static/...` page views; record state-changing operations from those pages.
- Record successful and failed operations, but do not add login/logout/login-failure events in this release.
- Never persist password values, password hashes, API tokens, cookies, Authorization headers, private keys, Tushare tokens, or Feishu secrets in the main database, spool database, emergency JSONL, logs, pages, or CSV files.
- Store phone/email snapshots in full in audit tables, but mask them by default in UI and masked CSV.
- Require current administrator password for sensitive reveal and full CSV export; reject these actions with HTTP 503 when the audit event cannot be durably persisted first.
- Default retention: API access 30 days, operation history 365 days; `0` means permanent.
- No admin delete controls for audit data.
- CSV maximum default 50,000 rows and formula-injection protection for values beginning with `=`, `+`, `-`, or `@`.
- No new third-party runtime dependency.
- The source archive contains no `.git` directory; replace each commit step with a checkpoint note in `docs/superpowers/plans/2026-07-19-audit-history-progress.md`.

---

## File Structure

**Create**

- `services/audit_schema.py`: idempotent main-database and spool-database schema creation.
- `services/audit_security.py`: recursive request sanitization, masking, token fingerprinting, CSV cell protection.
- `services/audit_repository.py`: inserts, queries, statistics, detail lookup, retention deletion, maintenance lease operations.
- `services/audit_spool.py`: durable enqueue, background flushing, retry/dead-letter handling, emergency JSONL fallback/recovery.
- `services/audit_service.py`: event construction, strict/non-strict persistence policy, Flask request context capture helpers.
- `services/audit_cleanup.py`: periodic retention cleanup worker.
- `routes/admin_audit_routes.py`: operation/access pages, detail JSON, reveal, masked/full CSV exports.
- `tools/db/migrate_audit_history.py`: explicit idempotent schema migration command.
- `tests/test_audit_security.py`
- `tests/test_audit_schema.py`
- `tests/test_audit_spool.py`
- `tests/test_api_access_audit.py`
- `tests/test_operation_audit.py`
- `tests/test_admin_audit_routes.py`
- `tests/test_audit_retention.py`
- `tests/test_audit_exports.py`
- `tests/test_audit_failure_modes.py`
- `docs/AUDIT_HISTORY_DEPLOYMENT.md`

**Modify**

- `config.py:213-229`: add audit configuration with defaults and zero-valid retention parsing.
- `.env.example:69-82`: add documented audit settings without secrets.
- `db_utils.py:71-96`: invoke audit schema initialization during `init_db`; keep legacy usage tables/functions.
- `app.py:8-28, 60-80, 116-190`: register audit blueprint, API hooks, and audit workers; stop workers at shutdown.
- `middleware/auth.py:1-130`: publish authentication state to the audit request context and retain legacy exact usage counter writes.
- `routes/user_routes.py:180-225`: record registration success/failure and add user password-change route if absent.
- `routes/admin_member_routes.py:8-25, 59-70, 289-655`: add audit navigation and instrument subscription/cancellation/password reset operations.
- `routes/admin_sync_routes.py:1-40`: instrument Feishu and bidding sync results.
- `routes/market_data_routes.py:100-145`: instrument cache clear as an operation while the global hook records its API access.
- `routes/admin_api_doc_routes.py:501-690`: instrument category/endpoint create/edit/delete/sync operations.
- `services/usage_log_queue.py:1-145`: preserve legacy daily counter queue; remove claims that dropped legacy detail rows are the complete audit trail.
- `routes/__init__.py`: export nothing new unless current package conventions require it.

---

### Task 1: Configuration and Idempotent Audit Schemas

**Files:**
- Create: `services/audit_schema.py`
- Modify: `config.py:213-229`
- Modify: `.env.example:69-82`
- Modify: `db_utils.py:71-96`
- Test: `tests/test_audit_schema.py`

**Interfaces:**
- Produces: `init_main_audit_schema(cursor: sqlite3.Cursor) -> None`
- Produces: `init_spool_schema(db_file: str | Path, synchronous: str = "FULL") -> None`
- Produces config names: `AUDIT_ENABLED`, `API_ACCESS_LOG_RETENTION_DAYS`, `OPERATION_LOG_RETENTION_DAYS`, `AUDIT_CLEANUP_INTERVAL_HOURS`, `AUDIT_SPOOL_DB_FILE`, `AUDIT_SPOOL_BATCH_SIZE`, `AUDIT_SPOOL_FLUSH_INTERVAL_SECONDS`, `AUDIT_SPOOL_MAX_RETRIES`, `AUDIT_SPOOL_SYNCHRONOUS`, `AUDIT_REQUEST_PARAMS_MAX_CHARS`, `AUDIT_ERROR_MESSAGE_MAX_CHARS`, `AUDIT_CSV_EXPORT_MAX_ROWS`, `AUDIT_TOKEN_HMAC_SECRET`, `AUDIT_EMERGENCY_DIR`.

- [ ] **Step 1: Write schema tests**

Create tests that initialize a temporary main database twice and assert `operation_audit_logs`, `api_access_logs`, `audit_maintenance_state`, required unique/index names, and all required columns exist. Initialize a temporary spool twice and assert `audit_spool_queue` and `audit_spool_dead_letters` exist with unique `event_id`.

- [ ] **Step 2: Run schema tests and verify failure**

Run: `python -m pytest tests/test_audit_schema.py -q`

Expected: collection or import failure because `services.audit_schema` does not exist.

- [ ] **Step 3: Implement exact schema creation**

Implement `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` statements matching the approved design. Use `event_id TEXT NOT NULL UNIQUE`, ISO local-time text timestamps, integer booleans, and JSON text columns. Spool rows contain `id`, `event_id`, `event_type`, `payload_json`, `attempt_count`, `last_attempt_at`, `next_retry_at`, `last_error`, and `created_at`; dead letters additionally contain `failed_at`.

- [ ] **Step 4: Add configuration parsing**

Add a helper that accepts zero for retention values rather than using the existing minimum-one parser. Resolve spool/emergency paths relative to `BASE_DIR`. When `AUDIT_TOKEN_HMAC_SECRET` is empty, use `SECRET_KEY` at runtime and log a warning if both are defaults.

- [ ] **Step 5: Wire schema into `init_db`**

Call `init_main_audit_schema(cursor)` before the main connection commit. Do not alter or migrate existing `usage_logs`.

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_audit_schema.py -q`

Expected: all schema tests pass.

- [ ] **Step 7: Record checkpoint**

Append `Task 1 PASS` and the test command/output summary to `docs/superpowers/plans/2026-07-19-audit-history-progress.md`.

### Task 2: Security Filtering, Masking, Fingerprinting, and CSV Safety

**Files:**
- Create: `services/audit_security.py`
- Test: `tests/test_audit_security.py`

**Interfaces:**
- Produces: `sanitize_value(value: Any, *, max_chars: int | None = None) -> Any`
- Produces: `sanitize_mapping(value: Any, *, max_chars: int | None = None) -> dict[str, Any] | list[Any] | str | int | float | bool | None`
- Produces: `sanitize_request_payload(request) -> dict[str, Any]`
- Produces: `mask_phone(value: str) -> str`
- Produces: `mask_email(value: str) -> str`
- Produces: `mask_text(value: str) -> str`
- Produces: `mask_record(record: dict[str, Any], fields: set[str] | None = None) -> dict[str, Any]`
- Produces: `token_fingerprint(token: str, secret: str) -> str`
- Produces: `safe_csv_cell(value: Any) -> str`

- [ ] **Step 1: Write failing security tests**

Cover nested dictionaries/lists, case-insensitive sensitive names, query/form values, upload metadata, maximum-character truncation marker, phone/email/text masking, deterministic HMAC fingerprint, different-secret behavior, empty-token behavior, and CSV values beginning with `= + - @`.

- [ ] **Step 2: Run and verify failure**

Run: `python -m pytest tests/test_audit_security.py -q`

Expected: import failure for `services.audit_security`.

- [ ] **Step 3: Implement recursive sanitization**

Treat a key as sensitive when its lowercase normalized form equals or contains one of the approved credential terms. Replace the value with `[REDACTED]`. Serialize unknown objects with `str`, preserve primitive values, cap string length, and cap final serialized payload length with `{"truncated": true, "preview": ...}`.

- [ ] **Step 4: Implement masks and HMAC**

Phone keeps first 3 and last 4 when length permits. Email preserves up to first 3 local-part characters and full domain. Generic text keeps first and last characters. HMAC output is lowercase SHA-256 hexadecimal; empty tokens return an empty string.

- [ ] **Step 5: Implement CSV cell safety**

Convert `None` to empty string; JSON-encode dictionaries/lists; prefix a single quote when the first non-whitespace character is one of `= + - @`.

- [ ] **Step 6: Run tests and checkpoint**

Run: `python -m pytest tests/test_audit_security.py -q`

Expected: all pass. Append `Task 2 PASS` to progress file.

### Task 3: Audit Repository Queries and Retention

**Files:**
- Create: `services/audit_repository.py`
- Test: `tests/test_audit_retention.py`
- Extend: `tests/test_audit_schema.py`

**Interfaces:**
- Consumes: `db_utils.get_conn`, schema tables from Task 1.
- Produces: `insert_operation_event(event: dict[str, Any]) -> bool`
- Produces: `insert_api_access_event(event: dict[str, Any]) -> bool`
- Produces: `insert_events_batch(events: list[tuple[str, dict[str, Any]]]) -> set[str]`
- Produces: `query_operation_logs(filters: dict[str, Any], page: int, page_size: int, *, include_sensitive: bool = False) -> dict[str, Any]`
- Produces: `query_api_access_logs(filters: dict[str, Any], page: int, page_size: int, *, include_sensitive: bool = False) -> dict[str, Any]`
- Produces: `get_operation_log(event_id: str) -> dict[str, Any] | None`
- Produces: `get_api_access_log(event_id: str) -> dict[str, Any] | None`
- Produces: `delete_expired_audit_rows(now: datetime, api_days: int, operation_days: int, batch_size: int = 5000) -> dict[str, int]`
- Produces: `acquire_maintenance_lease(task_name: str, now: datetime, lease_seconds: int) -> bool`
- Produces: `complete_maintenance_task(task_name: str, result: str, deleted_rows: int, now: datetime) -> None`

- [ ] **Step 1: Write failing repository tests**

Insert sample success/failure rows, assert duplicate `event_id` is ignored, filters are parameterized and accurate, pagination returns `items/total/page/page_size/pages`, detail lookup returns JSON-decoded data, and retention deletes only rows strictly older than each cutoff. Assert `0` retains all rows.

- [ ] **Step 2: Run and verify failure**

Run: `python -m pytest tests/test_audit_retention.py tests/test_audit_schema.py -q`

Expected: import failure for repository functions.

- [ ] **Step 3: Implement batch insertion**

Use one main-database transaction and `INSERT OR IGNORE`. Return the set of event IDs present after commit, so spool cleanup remains safe when an event was already inserted before a crash.

- [ ] **Step 4: Implement query builders**

Whitelist filter names and order clauses. Use exact matches for IDs/status/method/provider/action code and escaped `LIKE` for user/path/IP/keyword. Date boundaries are inclusive. Page size accepts only 20, 50, 100, or 200 for HTML queries; export queries use an explicit limit.

- [ ] **Step 5: Implement statistics**

Operation result includes success/failure, distinct targets, admin/user counts. Access result includes total, success/failure, distinct users, anonymous count, average duration, 401/402/403/429/5xx counts, and slowest API in the current filter.

- [ ] **Step 6: Implement retention and lease**

Delete in repeated batches of at most 5,000 rows, commit each batch, then run `PRAGMA optimize`. Lease updates must be atomic using an immediate transaction and `lease_until` comparison.

- [ ] **Step 7: Run tests and checkpoint**

Run: `python -m pytest tests/test_audit_retention.py tests/test_audit_schema.py -q`

Expected: all pass. Append `Task 3 PASS`.

### Task 4: Durable Spool, Retry, Dead Letters, and Emergency Recovery

**Files:**
- Create: `services/audit_spool.py`
- Test: `tests/test_audit_spool.py`
- Test: `tests/test_audit_failure_modes.py`

**Interfaces:**
- Consumes: `audit_schema.init_spool_schema`, `audit_repository.insert_events_batch`.
- Produces: `enqueue_event(event_type: Literal["operation", "api_access"], event: dict[str, Any], *, strict: bool = False) -> bool`
- Produces: `start_audit_spool_worker() -> None`
- Produces: `stop_audit_spool_worker(timeout: float = 8.0) -> None`
- Produces: `flush_spool_once(limit: int | None = None) -> dict[str, int]`
- Produces: `recover_emergency_files() -> dict[str, int]`
- Produces: `audit_spool_stats() -> dict[str, int]`

- [ ] **Step 1: Write spool tests**

Verify durable enqueue survives reopening, successful flush deletes queue rows, duplicate main-table inserts still delete queue rows, locked main DB causes retry metadata update, ten failures move to dead letters, invalid payload moves to dead letters, and emergency JSONL can be recovered without duplicates.

- [ ] **Step 2: Write strict/non-strict failure tests**

Patch spool writes to fail. Assert non-strict mode falls back to fsynced JSONL and returns true when that succeeds; strict mode also accepts durable emergency JSONL; both return false when spool and emergency writes fail.

- [ ] **Step 3: Run and verify failure**

Run: `python -m pytest tests/test_audit_spool.py tests/test_audit_failure_modes.py -q`

Expected: import failure for `services.audit_spool`.

- [ ] **Step 4: Implement spool connection handling**

Open a short-lived SQLite connection per enqueue/flush operation, apply configured busy timeout, WAL, and synchronous setting, and use a process lock only around schema startup and worker lifecycle.

- [ ] **Step 5: Implement retry schedule**

Use delays `[1, 5, 30, 120, 600]` seconds, repeating 600 seconds after the fifth attempt. Select due rows ordered by ID. Move rows whose next failed attempt reaches `AUDIT_SPOOL_MAX_RETRIES` into dead letters within the same spool transaction.

- [ ] **Step 6: Implement emergency JSONL**

Write one sanitized JSON object per line with `event_type`, `event`, and `written_at`; flush and `os.fsync`. Use daily files named `api_access_emergency_YYYY-MM-DD.jsonl` or `operation_emergency_YYYY-MM-DD.jsonl`. Recovery renames a file to `.processing`, enqueues each valid line, writes malformed lines to `.bad`, and deletes `.processing` only after all valid rows are durable.

- [ ] **Step 7: Implement worker lifecycle**

A daemon thread wakes every configured interval, recovers emergency files once at startup, then flushes due rows. Stop joins the thread and performs one final flush.

- [ ] **Step 8: Run tests and checkpoint**

Run: `python -m pytest tests/test_audit_spool.py tests/test_audit_failure_modes.py -q`

Expected: all pass. Append `Task 4 PASS`.

### Task 5: Event Service and Complete Flask API Capture

**Files:**
- Create: `services/audit_service.py`
- Modify: `app.py:8-28, 60-80, 116-190`
- Modify: `middleware/auth.py:1-130`
- Modify: `services/usage_log_queue.py:1-145`
- Test: `tests/test_api_access_audit.py`

**Interfaces:**
- Consumes: security and spool interfaces from Tasks 2 and 4.
- Produces: `begin_api_audit() -> None`
- Produces: `mark_api_auth_state(state: str, **context: Any) -> None`
- Produces: `finish_api_audit(response, exception: Exception | None = None) -> None`
- Produces: `record_operation(..., strict: bool = False) -> tuple[str, bool]`
- Produces: `current_request_metadata() -> dict[str, Any]`

- [ ] **Step 1: Write failing API capture tests**

Build a test app with temporary databases and routes for 200, 400, 401 missing token, 401 invalid token, 402 no subscription, 403 scope denied, 429 rate limit, 404 unknown API, 500 unhandled exception, and 502 upstream failure. Flush spool and assert exactly one `api_access_logs` row per request with the expected `auth_state`, status, path, duration, sanitized params, user snapshot, provider/api name, and no raw token.

- [ ] **Step 2: Run and verify failure**

Run: `python -m pytest tests/test_api_access_audit.py -q`

Expected: missing audit service/hook behavior.

- [ ] **Step 3: Implement request context**

`begin_api_audit` runs only for exact `/api` or prefix `/api/`. It stores event/request UUIDs, monotonic start, request timestamp, route-independent provider/api inference, sanitized payload, token fingerprint, IP/XFF/User-Agent, and default auth state `missing_token` when no token or `unresolved` when present.

- [ ] **Step 4: Update authentication middleware**

Before each early return, call `mark_api_auth_state` with exact state and error code. Distinguish missing token from invalid/disabled by adding a database helper or context loader result that reports disabled users/keys without exposing tokens. On success set user snapshots, plan code, and required scope. On rate limit set `rate_limited`.

- [ ] **Step 5: Preserve legacy usage accounting**

Keep `enqueue_usage_log` for authenticated requests because it updates exact daily counters. Set legacy success detail sample behavior unchanged; document that the new audit tables, not `usage_logs`, are the complete access history.

- [ ] **Step 6: Register Flask hooks**

Call `begin_api_audit` from the existing `before_request`. In `after_request`, finalize once and enqueue non-strictly. In the global exception handler set `internal_error` before returning the 500 response. Add a teardown fallback only when the finalization flag is false.

- [ ] **Step 7: Run tests and checkpoint**

Run: `python -m pytest tests/test_api_access_audit.py tests/test_unified_market_routes.py tests/test_plan_scopes.py tests/test_rate_limit_service.py -q`

Expected: all pass. Append `Task 5 PASS`.

### Task 6: Operation Audit for User and Membership Actions

**Files:**
- Modify: `routes/user_routes.py:180-225, 226-254`
- Modify: `routes/admin_member_routes.py:59-70, 289-655`
- Modify: `services/member_service.py:66-180, 300-675` only when a before/after snapshot cannot be obtained safely in routes.
- Test: `tests/test_operation_audit.py`

**Interfaces:**
- Consumes: `audit_service.record_operation`.
- Produces action codes exactly:
  - `user.register`
  - `user.password_change`
  - `admin.user_password_reset`
  - `admin.subscription_activate`
  - `admin.subscription_renew`
  - `admin.subscription_switch_now`
  - `admin.subscription_switch_scheduled`
  - `admin.subscription_switch_cancel`

- [ ] **Step 1: Write failing operation tests**

Exercise registration success/duplicate failure, password change success/wrong-current-password failure, admin password reset success/validation failure, open/renew/switch-now/switch-scheduled/cancel success and failure. Flush spool and assert actor/target/result/action code/before-after snapshots.

- [ ] **Step 2: Add secret-leak assertions**

Search serialized operation rows, spool rows, emergency files, and captured application logs for test passwords and password hashes; assert absent.

- [ ] **Step 3: Run and verify failure**

Run: `python -m pytest tests/test_operation_audit.py -q`

Expected: operation rows missing.

- [ ] **Step 4: Instrument user registration**

Wrap the POST path in a result-aware audit call. Capture sanitized username/phone/email, target user snapshot on success, and a safe error message on failure. Do not audit GET page views.

- [ ] **Step 5: Add password-change route**

Add `GET/POST /user/change-password`, require logged-in user session, verify current password, require matching new password confirmation and existing password policy, update via a service function, and record only `{"password_changed": true}` in request/after data. Add a link from the dashboard.

- [ ] **Step 6: Instrument admin membership actions**

Read the target user/current/scheduled subscription snapshots before mutation. Map `operation_type` from the service result to the exact action code. Record both route validation failures and service exceptions. Use `actor_name` from the administrator session/config and target phone/email snapshot.

- [ ] **Step 7: Surface audit warnings**

For critical business operations, call non-strict `record_operation`; when it returns false after both spool and emergency failure, return the successful business result with an explicit visible `审计系统异常` warning. Do not roll back completed membership/password changes.

- [ ] **Step 8: Run tests and checkpoint**

Run: `python -m pytest tests/test_operation_audit.py tests/test_subscription_actions.py -q`

Expected: all pass. Append `Task 6 PASS`.

### Task 7: Administrator Audit Pages, Detail, Reveal, and CSV

**Files:**
- Create: `routes/admin_audit_routes.py`
- Modify: `routes/admin_member_routes.py:55-70` to expose/reuse `require_admin_session`, `_admin_nav`, `_page` without circular imports, or move these helpers to a small shared module if tests show a cycle.
- Modify: `app.py:15-25, 120-130`
- Test: `tests/test_admin_audit_routes.py`
- Test: `tests/test_audit_exports.py`

**Interfaces:**
- Consumes repository query/detail APIs, security masks/CSV safety, `verify_password` semantics for administrator password via constant-time `hmac.compare_digest` against `config.ADMIN_PASSWORD`.
- Produces routes:
  - `GET /admin/operation-history`
  - `GET /admin/data-access-history`
  - `GET /admin/operation-history/detail/<event_id>`
  - `GET /admin/data-access-history/detail/<event_id>`
  - `POST /admin/audit/reveal-sensitive`
  - `GET /admin/operation-history/export.csv`
  - `GET /admin/data-access-history/export.csv`
  - `POST /admin/operation-history/export-full.csv`
  - `POST /admin/data-access-history/export-full.csv`

- [ ] **Step 1: Write permission and rendering tests**

Assert unauthenticated users redirect to `/admin/login`, ordinary user sessions cannot access, admin sessions can access, navigation includes both history pages, filters persist in forms, pagination works, and default HTML/detail JSON masks phone/email.

- [ ] **Step 2: Write reveal tests**

Wrong admin password returns 403 and writes a failed `admin.sensitive_reveal` event. Correct password returns only requested fields from one event, sets `Cache-Control: no-store`, and writes a successful reveal event before returning the full values. When strict audit persistence is patched to fail, return 503 and no full value.

- [ ] **Step 3: Write CSV tests**

Masked export uses current filters and masked phone/email; full export requires POST/password, writes a strict pre-export event, omits credential columns, protects formula cells, applies 50,000-row maximum, sets UTF-8 BOM and safe download headers, and records actual row count after completion.

- [ ] **Step 4: Run and verify failure**

Run: `python -m pytest tests/test_admin_audit_routes.py tests/test_audit_exports.py -q`

Expected: missing blueprint/routes.

- [ ] **Step 5: Implement HTML pages**

Follow the current inline `_page` style and horizontally scrollable tables. Render summary cards, filter forms, fixed page-size choices, masked rows, detail links, and separate masked/full export controls. Do not include delete controls.

- [ ] **Step 6: Implement reveal endpoint**

Accept `history_type`, `event_id`, `fields[]`, and `admin_password`. Whitelist revealable fields. Create a strict audit event containing viewer, target, requested fields, source history type/event ID, IP, and result before returning successful full values.

- [ ] **Step 7: Implement streaming-safe CSV**

Query no more than configured maximum plus one. Reject oversized exports with 400. Use `io.StringIO`, `csv.writer`, UTF-8 BOM, `Content-Disposition` with timestamped ASCII filename, `Cache-Control: no-store`, and `X-Content-Type-Options: nosniff`.

- [ ] **Step 8: Register blueprint and navigation**

Register at `/admin`; add `操作历史` and `数据访问历史` to the shared admin navigation.

- [ ] **Step 9: Run tests and checkpoint**

Run: `python -m pytest tests/test_admin_audit_routes.py tests/test_audit_exports.py tests/test_admin_api_docs_ui.py -q`

Expected: all pass. Append `Task 7 PASS`.

### Task 8: Audit Remaining State-Changing Admin/API Operations

**Files:**
- Modify: `routes/admin_sync_routes.py:1-40`
- Modify: `routes/market_data_routes.py:100-145`
- Modify: `routes/admin_api_doc_routes.py:501-690`
- Test: `tests/test_operation_audit.py`

**Interfaces:**
- Produces action codes:
  - `admin.feishu_sync`
  - `admin.bidding_sync`
  - `admin.cache_clear`
  - `admin.api_docs_sync`
  - `admin.api_doc_category_create`
  - `admin.api_doc_category_update`
  - `admin.api_doc_endpoint_create`
  - `admin.api_doc_endpoint_update`
  - `admin.api_doc_endpoint_delete`

- [ ] **Step 1: Extend failing tests**

Cover success and failure for sync endpoints, cache clear, category create/edit, endpoint create/edit/delete, and full catalog sync. Assert API access and operation events are separate for `/api/...` mutation routes.

- [ ] **Step 2: Run and verify failure**

Run: `python -m pytest tests/test_operation_audit.py -q`

Expected: new action codes absent.

- [ ] **Step 3: Instrument each mutation**

Capture sanitized inputs, before/after rows where available, exact success/error status, actor type `admin` for admin session routes and `user`/current API principal for scope-protected cache clear. Do not audit GET-only confirmation pages as operations; audit only the actual mutation call.

- [ ] **Step 4: Run tests and checkpoint**

Run: `python -m pytest tests/test_operation_audit.py tests/test_admin_api_docs_ui.py tests/test_feishu_bidding_sync_v2.py -q`

Expected: all pass. Append `Task 8 PASS`.

### Task 9: Retention Worker, Startup/Shutdown, and Migration Tool

**Files:**
- Create: `services/audit_cleanup.py`
- Create: `tools/db/__init__.py` if absent
- Create: `tools/db/migrate_audit_history.py`
- Modify: `app.py:60-80, 180-210`
- Test: `tests/test_audit_retention.py`
- Test: `tests/test_audit_failure_modes.py`

**Interfaces:**
- Produces: `start_audit_cleanup_worker() -> None`
- Produces: `stop_audit_cleanup_worker(timeout: float = 8.0) -> None`
- Produces: `run_cleanup_once(now: datetime | None = None, *, force: bool = False) -> dict[str, Any]`

- [ ] **Step 1: Extend cleanup worker tests**

Assert it skips when last completion is newer than configured interval, honors a live lease, cleans when due, handles zero retention, records deleted counts/result, and catches/logs errors without killing the web app.

- [ ] **Step 2: Run and verify failure**

Run: `python -m pytest tests/test_audit_retention.py tests/test_audit_failure_modes.py -q`

Expected: missing cleanup worker.

- [ ] **Step 3: Implement worker**

A daemon thread checks hourly. `run_cleanup_once` acquires a lease for 30 minutes, calls repository deletion with configured retentions, and records completion. The worker waits on an event so shutdown is prompt.

- [ ] **Step 4: Implement migration command**

`python -m tools.db.migrate_audit_history` initializes main/spool schemas, prints resolved database paths, table/index verification, and exits 0; exceptions print a clear error and exit 1. It never deletes or rewrites existing rows.

- [ ] **Step 5: Wire lifecycle**

After `init_db`, initialize spool and start spool/cleanup workers. During `stop_background_services`, stop audit workers before stopping the log listener.

- [ ] **Step 6: Run tests and checkpoint**

Run: `python -m pytest tests/test_audit_retention.py tests/test_audit_failure_modes.py -q`

Expected: all pass. Append `Task 9 PASS`.

### Task 10: Documentation, Full Regression, Security Scan, and Delivery Archives

**Files:**
- Create: `docs/AUDIT_HISTORY_DEPLOYMENT.md`
- Create: `env_audit_example.txt`
- Create: `README_替换与升级说明.md`
- Create: `修改文件清单.txt`
- Create: `SHA256校验清单.txt`
- Update: `.gitignore`

**Interfaces:**
- Produces archives:
  - `/mnt/data/stock_server_审计历史完整版_20260719.zip`
  - `/mnt/data/stock_server_审计历史直接替换包_20260719.zip`

- [ ] **Step 1: Write deployment documentation**

Document backup, file replacement, environment additions, migration command, test command, Waitress restart, verification requests, admin-page checks, retention behavior, spool/emergency paths, monitoring, and rollback.

- [ ] **Step 2: Update ignore rules**

Ignore `.env`, `data/tokens.db`, `data/audit_spool.db`, `data/audit_emergency/`, audit processing/bad files, logs, caches, IDE files, and virtual environments.

- [ ] **Step 3: Run focused audit tests**

Run: `python -m pytest tests/test_audit_*.py -q`

Expected: all new tests pass.

- [ ] **Step 4: Run full regression suite**

Run: `python -m pytest -q`

Expected: all existing and new tests pass with zero failures.

- [ ] **Step 5: Compile source**

Run: `python -m compileall -q app.py config.py db_utils.py middleware routes services tools`

Expected: exit code 0.

- [ ] **Step 6: Run migration on a copied database**

Copy the supplied `data/tokens.db` to a temporary verification directory, set `DB_FILE` and audit paths to that directory, run `python -m tools.db.migrate_audit_history`, then inspect tables and row counts. Never modify or package the supplied real database.

- [ ] **Step 7: Run secret-leak scan**

Search generated source, docs, test artifacts, spool/emergency fixtures, and delivery staging for actual `.env` values, `tokens.db`, token-like values from fixtures, password values, `.venv`, `.idea`, and caches. Remove every unintended match before packaging.

- [ ] **Step 8: Build full clean project archive**

Stage the modified project excluding `.env`, databases, virtual environments, IDE/cache directories, runtime logs, emergency/spool files, and test-generated artifacts. Include `.env.example`, tests, docs, migration tool, and source.

- [ ] **Step 9: Build direct replacement archive**

Stage only created/modified files at original relative paths plus replacement instructions, audit environment example, changed-file list, and SHA-256 manifest. Do not include any real database or `.env`.

- [ ] **Step 10: Verify archives**

List both ZIPs, extract each to a fresh temporary directory, verify SHA-256 manifest, run compileall on both, and run the audit tests from the full archive.

- [ ] **Step 11: Final verification report**

Write `AUDIT_HISTORY_TEST_RESULTS.md` with exact commands, pass counts, warnings, archive sizes, checksums, and any limitations. Append `Task 10 PASS` only after every command succeeds.
