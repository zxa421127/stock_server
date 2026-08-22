# Tushare Official Spec Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace sample-derived Tushare interface metadata with official definitions, detect official changes every Wednesday and Sunday at 02:30 Asia/Shanghai, notify administrators, and publish selected updates through the existing candidate-release workflow with post-publish verification.

**Architecture:** Separate official document fetch/parse, semantic comparison, scheduled monitoring, alert persistence, candidate generation, publication, and post-publication verification. Runtime interface testing continues to read only versioned local releases; scheduled monitoring never overwrites production specs automatically.

**Tech Stack:** Python 3, Flask, SQLite, requests, JSON versioned specifications, browser JavaScript in `templates/admin/interface_tester.html`, pytest/unittest.

## Global Constraints

- Scan schedule: Wednesday and Sunday at 02:30 in `Asia/Shanghai`.
- Scheduled scans only create/update alerts; they never publish production specifications automatically.
- Administrator action re-fetches the selected official documents before candidate creation.
- Publication requires the existing administrator confirmation flow and is followed by an immediate official re-check.
- Official field names, official types, required/default flags, descriptions, order, permission, and limit text must be preserved.
- No production Tushare specification may continue to use sample descriptions or unsupported `unknown` types after a successful complete synchronization.
- Existing release switching and rollback behavior remains intact.

---

### Task 1: Stabilize official document parsing and semantic fingerprints
- [ ] Add fixtures for `ci_daily` and official Markdown table variants.
- [ ] Add failing tests for 4 inputs, 11 outputs, official type/order/description, permission and limit parsing.
- [ ] Implement deterministic `raw_content_hash` and `semantic_spec_hash` excluding fetch timestamps.
- [ ] Extend spec diffs to interface metadata, order, default display, permission and limit changes.

### Task 2: Persist scan runs, snapshots and change alerts
- [ ] Add SQLite migration helpers and repository operations.
- [ ] Add tests for run lifecycle, snapshot upsert, alert deduplication and status transitions.
- [ ] Expose scan status and pending alerts through service interfaces.

### Task 3: Implement monitor and scheduler
- [ ] Add monitor service that checks all official specs without changing the active release.
- [ ] Add process-safe database lease to prevent duplicate scans.
- [ ] Add Wednesday/Sunday 02:30 Asia/Shanghai scheduler and manual scan command.
- [ ] Add tests for no-change, metadata change, parse failure and duplicate-run prevention.

### Task 4: Administrator alert, candidate and publication workflow
- [ ] Add scan status and alerts endpoints.
- [ ] Add administrator action to re-fetch selected interfaces and create a candidate.
- [ ] Extend publication to bind alerts to release and run post-publish official verification.
- [ ] Add route and service tests.

### Task 5: Update interface tester UI
- [ ] Show last/next scan, success/failure totals and pending change count.
- [ ] Show detailed per-interface change notices and statuses.
- [ ] Add manual check and selected synchronization controls.
- [ ] Keep candidate review and publish confirmation; show post-publish verification state.

### Task 6: Full official synchronization and auditing tools
- [ ] Extend CLI to support complete synchronization, monitor-only scan, candidate generation and verification.
- [ ] Add audit checks for `catalog_seed`, sample descriptions and unsupported unknown types.
- [ ] Generate `ci_daily` official bootstrap correction in the bundled release.
- [ ] Produce deployment, migration, schedule and rollback documentation.

### Task 7: Verification and packaging
- [ ] Run targeted red-green tests.
- [ ] Run all interface specification and administrator tester regressions.
- [ ] Compile changed Python files and validate browser JavaScript syntax.
- [ ] Scan package for secrets and excluded runtime files.
- [ ] Package only changed/new files with manifest and SHA256 sums.
