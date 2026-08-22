# Admin Feishu Registration Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a secure administrator web entry on the member-list page for manually importing Feishu member registrations whose user ID is empty.

**Architecture:** Keep the existing `sync_feishu_to_local()` safety boundary and process lock. Add a POST-only route to the existing admin member blueprint, protect it with the administrator session and CSRF token, render an immediate result page, and record a sanitized administrator operation audit. Do not change the one-way local-to-Feishu bidding synchronization path.

**Tech Stack:** Python, Flask, SQLite, pytest, existing Feishu sync and audit services.

## Global Constraints

- Existing local member data, Token values, subscriptions, and permissions remain authoritative.
- Feishu import only invokes the existing safe `sync_feishu_to_local()` function.
- The operation must never display or audit complete API Token values.
- Bidding synchronization remains local SQLite snapshot to Feishu only.

---

### Task 1: Add failing route and UI tests

**Files:**
- Create: `tests/test_admin_feishu_registration_import.py`
- Modify: none

- [ ] Verify the member-list page contains a POST form, CSRF token, confirmation prompt, and import button.
- [ ] Verify unauthenticated requests redirect to administrator login.
- [ ] Verify invalid CSRF requests do not invoke synchronization and are audited as failures.
- [ ] Verify successful imports show added/linked counts and write a sanitized success audit.
- [ ] Verify busy and internal error statuses return safe result pages and failure audits.

### Task 2: Implement the administrator import entry

**Files:**
- Modify: `routes/admin_member_routes.py`

- [ ] Add administrator CSRF helper functions using the existing session token.
- [ ] Add a lazy wrapper around `sync_feishu_to_local()` for testability.
- [ ] Add the import form to `/admin/members/list`.
- [ ] Add `POST /admin/members/import-feishu-registrations`.
- [ ] Map sync statuses to safe HTTP responses and result-page messages.
- [ ] Record `admin.feishu_registration_import` audits without sensitive fields.

### Task 3: Verify regressions and package replacements

**Files:**
- Create: `REPLACE_INSTRUCTIONS_ADMIN_FEISHU_IMPORT.md`
- Create: `TEST_RESULTS_ADMIN_FEISHU_IMPORT.md`

- [ ] Run the dedicated new tests.
- [ ] Run member, sync, audit, API-document, and bidding tests.
- [ ] Compile modified Python files.
- [ ] Package only modified production files, tests, and instructions; exclude `.env`, databases, logs, and virtual environments.
