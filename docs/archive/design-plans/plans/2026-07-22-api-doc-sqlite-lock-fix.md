# API Documentation SQLite Lock Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Eliminate the leaked SQLite write transaction that makes `/user/api-docs`, `/admin/api-docs`, admin authentication, and Feishu synchronization fail with `database is locked`.

**Architecture:** Keep generated-document synchronization explicit and transactional. Ordinary document reads first perform a read-only version/count check and skip synchronization when the catalog is current. Every synchronization exit commits on success and rolls back on failure, while Flask request teardown closes the request thread's database connection as a final safety boundary.

**Tech Stack:** Python 3.13, Flask, SQLite WAL, unittest/pytest.

## Global Constraints

- Preserve all administrator-created custom API documents.
- Preserve direct `sync_full_api_docs(force=False)` cleanup behavior for the two approved obsolete paths.
- Do not delete SQLite WAL/SHM files or modify user data.
- Do not add third-party dependencies.

---

### Task 1: Reproduce and prevent leaked write transactions

**Files:**
- Modify: `tests/test_api_doc_service.py`
- Modify: `services/api_doc_service.py`

**Interfaces:**
- Consumes: `sync_full_api_docs(force: bool = False) -> dict[str, Any]`
- Produces: successful synchronization always leaves `get_conn().in_transaction == False`; exceptions roll back the current transaction.

- [x] **Step 1: Add failing tests**

Add tests that install the current catalog, run an idempotent non-force synchronization, assert the thread-local connection is not in a transaction, and verify a second SQLite connection can immediately write.

- [x] **Step 2: Run tests and confirm failure**

Run: `python -m pytest tests/test_api_doc_service.py -q`
Expected: the new transaction-release assertion fails on the current implementation.

- [x] **Step 3: Implement transactional synchronization**

Wrap `sync_full_api_docs()` in `try/except`, commit every successful return path including the no-change path, and roll back before re-raising any exception.

- [x] **Step 4: Run tests and confirm success**

Run: `python -m pytest tests/test_api_doc_service.py -q`
Expected: all tests pass.

### Task 2: Make ordinary API-document reads read-only when current

**Files:**
- Modify: `tests/test_api_doc_service.py`
- Modify: `services/api_doc_service.py`

**Interfaces:**
- Consumes: `full_api_docs_status() -> dict[str, Any]`
- Produces: `ensure_default_api_docs() -> None` calls `sync_full_api_docs()` only when installed version/count differs from the expected catalog.

- [x] **Step 1: Add failing test**

Add a test that installs the current catalog, patches `sync_full_api_docs`, calls `ensure_default_api_docs()`, and asserts synchronization was not invoked.

- [x] **Step 2: Run test and confirm failure**

Run: `python -m pytest tests/test_api_doc_service.py -q`
Expected: patched synchronization is called by the current implementation.

- [x] **Step 3: Implement read-only status check**

Make `full_api_docs_status()` query `sqlite_master` before reading the optional metadata table instead of creating it. Make `ensure_default_api_docs()` return immediately when version and generated count are current.

- [x] **Step 4: Run tests and confirm success**

Run: `python -m pytest tests/test_api_doc_service.py -q`
Expected: all API document service tests pass.

### Task 3: Close request-thread database connections

**Files:**
- Modify: `app.py`
- Test: existing UI and route tests

**Interfaces:**
- Consumes: `db_utils.close_thread_connection() -> None`
- Produces: every Flask application-context teardown rolls back and closes that thread's SQLite connection.

- [x] **Step 1: Register teardown cleanup**

Import `close_thread_connection` and register `@app.teardown_appcontext` to call it unconditionally.

- [x] **Step 2: Run API-document UI tests**

Run: `python -m pytest tests/test_user_api_docs_ui.py tests/test_admin_api_docs_ui.py tests/test_full_api_docs.py -q`
Expected: all tests pass.

### Task 4: Full verification and replacement package

**Files:**
- Create: `REPLACE_INSTRUCTIONS_API_DOC_LOCK_FIX.md`
- Package: modified files preserving project-relative paths

**Interfaces:**
- Produces: a ZIP that can be extracted over the existing project after backup and service shutdown.

- [x] **Step 1: Run related regression suite**

Run: `python -m pytest tests/test_api_doc_service.py tests/test_full_api_docs.py tests/test_user_api_docs_ui.py tests/test_admin_api_docs_ui.py tests/test_admin_state_change_audit.py tests/test_feishu_member_sync_safety.py -q`
Expected: all selected tests pass.

- [x] **Step 2: Compile modified Python files**

Run: `python -m py_compile services/api_doc_service.py app.py tests/test_api_doc_service.py`
Expected: exit code 0.

- [x] **Step 3: Package files**

Include `services/api_doc_service.py`, `app.py`, `tests/test_api_doc_service.py`, the plan, and replacement instructions under their original relative paths.
