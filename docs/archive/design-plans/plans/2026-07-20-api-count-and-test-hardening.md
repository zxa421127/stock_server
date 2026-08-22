# API Count and Test Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Delete two obsolete API documents, centralize all API-document counts, improve acceptance-test dates, redact Feishu Token logs, and enable Kaipanla snapshot configuration.

**Architecture:** Keep the generated catalog as the source of truth and derive its count with `len(FULL_API_DOCS)`. Put database cleanup and statistics in `services/api_doc_service.py`; presentation layers consume that API. Keep date selection in `tools/interface_tester.py` and keep logging redaction in `services/feishu_sync_service.py`.

**Tech Stack:** Python 3.13, Flask, SQLite, pytest/unittest, Waitress.

## Global Constraints

- Delete only the two exact obsolete paths approved by the user.
- Do not include the real `.env`, real databases, logs, `.venv`, `.idea`, or credentials in delivery packages.
- Preserve all 138 Tushare and 2 Kaipanla generated documents.
- Use test-first changes and run the full existing suite before packaging.
- No Git repository exists in the source ZIP; record file hashes instead of commits.

---

### Task 1: Catalog count and obsolete-document cleanup

**Files:**
- Modify: `services/api_doc_catalog.py`
- Modify: `services/api_doc_service.py`
- Test: `tests/test_api_doc_service.py`

**Interfaces:**
- Produces: `FULL_API_DOCS_TOTAL == len(FULL_API_DOCS)`
- Produces: `cleanup_obsolete_api_docs(cur) -> dict[str, int]`
- Produces: `get_api_doc_statistics() -> dict[str, int | str]`

- [x] Write tests that insert the two obsolete records and another custom record, run synchronization, and assert only the two approved records are removed.
- [x] Run the targeted tests and confirm failure because the cleanup/statistics functions do not exist.
- [x] Implement dynamic catalog total, exact-path cleanup, empty-category cleanup, and centralized statistics.
- [x] Run targeted tests and confirm pass.

### Task 2: Admin and user page dynamic counts

**Files:**
- Modify: `routes/admin_api_doc_routes.py`
- Modify: `routes/user_routes.py`
- Modify: `tools/sync_full_api_docs.py`
- Test: `tests/test_admin_api_docs_ui.py`
- Test: `tests/test_full_api_docs.py`

**Interfaces:**
- Consumes: `get_api_doc_statistics()`

- [x] Add failing assertions that UI/tool output has no 139 hardcode and renders centralized counts.
- [x] Run targeted tests and confirm expected failure.
- [x] Replace local counters and hardcoded descriptions with centralized values and dynamic wording.
- [x] Run targeted tests and confirm pass.

### Task 3: Completed-trading-day acceptance parameters

**Files:**
- Modify: `tools/interface_tester.py`
- Test: `tests/test_interface_test_params.py`

**Interfaces:**
- Produces: `get_last_completed_weekday(now=None) -> date`
- Produces: `_test_dates(now=None) -> dict[str, str]`

- [x] Add failing tests for Monday-before-close, Monday-after-close, weekend, minute ranges, and real-time API parameters.
- [x] Run targeted tests and confirm failure.
- [x] Implement Shanghai-time completed-day selection and route daily/minute samples through it.
- [x] Run targeted tests and confirm pass.

### Task 4: Feishu Token log redaction

**Files:**
- Modify: `services/feishu_sync_service.py`
- Test: `tests/test_feishu_subscription_fields.py`

**Interfaces:**
- Produces: `_token_log_fingerprint(token: str) -> str`

- [x] Add a failing log-capture test asserting the source Token and its prefix are absent and a fingerprint is present.
- [x] Run the targeted test and confirm failure.
- [x] Implement HMAC fingerprint logging and replace the Token preview field.
- [x] Run targeted tests and confirm pass.

### Task 5: Snapshot configuration and documentation

**Files:**
- Modify: `.env.example`
- Create: `env_需要追加配置.txt`
- Create: `README_本次修改说明.md`

**Interfaces:**
- `.env.example` documents `KAIPANLA_SNAPSHOT_ENABLED=true` and all scheduler settings.

- [x] Add configuration validation test or static assertion to an existing snapshot-startup test.
- [x] Update examples and write merge instructions without copying secrets.
- [x] Run snapshot configuration tests.

### Task 6: Database migration verification and packaging

**Files:**
- Create: `修改文件清单.txt`
- Create: `SHA256校验清单.txt`
- Create: delivery ZIP archives under `/mnt/data`

**Interfaces:**
- Produces complete and replacement ZIP packages.

- [x] Install dependencies in an isolated Linux virtual environment and run baseline/full tests.
- [x] Run `compileall`.
- [x] Copy `tokens.db`, run document sync against the copy, and verify exactly 140 documents and no obsolete paths.
- [x] Build a replacement archive containing only modified/new files and instructions.
- [x] Build a sanitized full-source archive excluding secrets, databases, virtual environments, IDE/cache files, and logs.
- [x] Verify both ZIPs and all SHA-256 entries.
