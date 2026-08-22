# 飞书同步与 SQLite 并发加固 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除飞书同步任务之间及其与审计落库之间的 SQLite 写锁冲突，并让失败状态可辨识且向后兼容。

**Architecture:** 使用标准库跨进程文件锁串行化所有飞书同步任务；把数据库初始化限定在应用启动阶段；使用短事务和有限退避重试处理 SQLite 短暂写锁。返回值采用 tuple 子类，在不破坏旧解包逻辑的情况下携带明确状态。

**Tech Stack:** Python 3.11+、SQLite/WAL、Flask、pytest、Windows `msvcrt` / POSIX `fcntl`。

## Global Constraints

- 不新增第三方依赖。
- Windows PowerShell/Waitress 必须可用。
- 保持 `sync_feishu_to_local()` 二计数和 `sync_local_to_feishu()` 三计数解包兼容。
- 本地数据库仍是会员、Token、套餐与权限的唯一权威源。
- 飞书网络请求期间不得持有 SQLite 写事务。
- 竞价表仍保持本地快照→飞书单向同步。

---

### Task 1: 跨进程同步锁与结果对象

**Files:**
- Create: `services/process_lock.py`
- Create: `services/sync_result.py`
- Test: `tests/test_feishu_sync_concurrency.py`

**Interfaces:**
- Produces: `process_lock(path, timeout=0.0) -> context manager[bool]`
- Produces: `SyncResult(counts, status='ok', message='')`

- [ ] 写失败测试，验证同一进程第二个锁获取失败、`SyncResult` 可解包且与普通 tuple 相等。
- [ ] 运行 `pytest tests/test_feishu_sync_concurrency.py -v`，确认失败。
- [ ] 实现跨平台文件锁和 tuple 兼容结果对象。
- [ ] 重跑测试并确认通过。

### Task 2: SQLite 写重试基础设施

**Files:**
- Modify: `db_utils.py`
- Test: `tests/test_sqlite_write_retry.py`

**Interfaces:**
- Produces: `is_database_busy_error(exc) -> bool`
- Produces: `close_thread_connection() -> None`
- Produces: `run_db_write_with_retry(operation, *, attempts=4, delays=(0.2,0.8,2.0,5.0))`

- [ ] 写失败测试，模拟两次 `database is locked` 后成功，以及非锁异常不重试。
- [ ] 运行目标测试并确认失败。
- [ ] 实现连接回滚/关闭和有限退避重试。
- [ ] 运行目标测试并确认通过。

### Task 3: 飞书同步串行化和运行期只读就绪检查

**Files:**
- Modify: `config.py`
- Modify: `services/feishu_sync_service.py`
- Test: `tests/test_feishu_sync_concurrency.py`
- Test: `tests/test_feishu_member_sync_safety.py`

**Interfaces:**
- Consumes: `process_lock`, `SyncResult`, `run_db_write_with_retry`
- Produces: `_ensure_runtime_db_ready() -> None`
- Produces: `_create_feishu_user_atomic(...) -> int`

- [ ] 写失败测试，验证同步函数不调用 `init_db()`、锁占用返回 `busy`、持续数据库锁返回 `database_busy`。
- [ ] 写失败测试，验证用户与 Token 同一事务提交且回写发生在提交后。
- [ ] 运行目标测试确认失败。
- [ ] 移除同步函数中的 `init_db()`，增加只读表检查。
- [ ] 给单用户、会员全量、登记导入、竞价同步统一加锁。
- [ ] 用短事务原子创建用户和 Token，并在数据库锁时使用有限重试。
- [ ] 将 tuple 返回替换为兼容的 `SyncResult`。
- [ ] 运行目标测试确认通过。

### Task 4: 审计主库写入快速重试

**Files:**
- Modify: `services/audit_repository.py`
- Modify: `services/audit_spool.py`
- Test: `tests/test_audit_spool.py`
- Test: `tests/test_sqlite_write_retry.py`

**Interfaces:**
- Consumes: `run_db_write_with_retry`

- [ ] 写失败测试，模拟审计批量写入首次 locked、第二次成功。
- [ ] 运行目标测试确认失败。
- [ ] 将审计批量事务包装进快速重试，并降低短暂锁的重复堆栈噪声。
- [ ] 运行审计测试确认通过。

### Task 5: 文档、编译和完整回归

**Files:**
- Create: `README_飞书SQLite并发加固说明.md`
- Create: `PATCH_MANIFEST_飞书SQLite并发加固.md`

- [ ] 更新部署、验证、回滚和手工测试命令。
- [ ] 运行 `python -m compileall` 检查修改文件。
- [ ] 运行飞书与审计专项测试。
- [ ] 运行完整 pytest 测试套件。
- [ ] 生成直接替换 ZIP、SHA256 和文件级校验清单。
- [ ] 在全新项目副本中覆盖补丁并再次运行完整测试。
