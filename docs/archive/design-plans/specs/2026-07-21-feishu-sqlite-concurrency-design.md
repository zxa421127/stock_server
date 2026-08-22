# 飞书同步与 SQLite 并发加固设计

## 背景

当前后台每 5 分钟执行一次本地→飞书发布；管理员还可能在另一个 PowerShell 进程手工执行飞书登记→本地导入。两条同步路径会与审计缓冲落库同时访问 `data/tokens.db`。现有同步函数每次都调用 `init_db()`，会重复执行订阅状态迁移等写操作；同步任务之间也没有跨进程互斥。因此在并发时可能出现 `sqlite3.OperationalError: database is locked`，且异常被压缩成 `(0, 0)`，容易误判为正常零结果。

## 目标

1. 同一时刻只允许一个飞书同步任务运行，覆盖会员发布、登记导入、单用户发布和竞价发布。
2. 周期同步和手工同步不再重复执行数据库建表/迁移；完整初始化只由应用启动流程负责。
3. 飞书登记新用户的本地写入采用短事务，并在同一事务内创建用户和 API Token。
4. SQLite 短暂锁冲突按有限退避重试；重试后仍失败时返回明确的 `database_busy` 状态。
5. 保持旧代码兼容：原有返回值仍可按二元组/三元组解包、比较，但打印时带 `status` 和 `message`。
6. 审计缓冲向主库批量落库遇到短暂锁时先做快速重试，再进入原有持久化缓冲退避机制。
7. 网络请求期间不持有 SQLite 写事务。

## 架构

### 1. 跨进程同步锁

新增 `services/process_lock.py`，使用标准库实现跨平台文件锁：

- Windows 使用 `msvcrt.locking`；
- Linux/macOS 使用 `fcntl.flock`；
- 同时增加进程内 `threading.Lock`，避免同一进程不同线程绕过平台文件锁；
- 文件句柄在整个同步任务期间保持打开，进程退出时操作系统自动释放锁；
- 锁文件默认位于 `data/feishu_sync.lock`；
- 获取失败立即返回 `busy`，不排队等待几十秒。

会员全量发布、单用户发布、飞书登记导入和竞价发布共用同一把锁。

### 2. 运行期数据库就绪检查

同步函数不再调用 `init_db()`。新增只读检查 `_ensure_runtime_db_ready()`：

- 检查 `users`、`api_keys`、`subscriptions`、`plans` 等必要表是否存在；
- 不执行 `CREATE`、`ALTER`、`UPDATE`；
- 数据库尚未初始化时返回 `schema_not_ready`，提示先启动服务或显式运行初始化。

应用 `create_app()` 仍在启动时执行一次 `init_db()`，保持现有部署方式不变。

### 3. SQLite 重试工具

在 `db_utils.py` 中增加：

- `is_database_busy_error(exc)`；
- `close_thread_connection()`，用于回滚并关闭当前线程连接；
- `run_db_write_with_retry(operation, attempts, delays)`，每次失败后回滚、关闭旧连接并重试。

默认快速重试延迟为 `0.2、0.8、2.0、5.0` 秒；只对 `locked`、`busy` 类错误重试，其他异常立即抛出。

### 4. 飞书登记导入事务边界

创建新用户时使用一个短事务完成：

```text
BEGIN IMMEDIATE
→ INSERT users
→ INSERT api_keys
→ COMMIT
```

提交完成后才调用飞书 API 回写记录。这样不会出现用户已创建但 Token 尚未创建的中间状态，也不会在网络请求期间持有主库写锁。

### 5. 向后兼容的结果对象

新增 `SyncResult(tuple)`：

- 二元或三元计数保持原始长度，旧测试和旧调用可继续解包；
- 与普通 tuple 比较仍然成立；
- 增加 `status`、`message`、`success` 属性；
- `print(result)` 输出如：

```text
SyncResult(counts=(0, 0), status='database_busy', message='SQLite 数据库正被其他任务写入，请稍后重试')
```

状态包括：`ok`、`busy`、`database_busy`、`schema_not_ready`、`skipped`、`empty`、`error`。

### 6. 审计缓冲

`insert_events_batch()` 使用同一快速数据库重试工具。若短暂锁在几秒内释放，审计事件直接写入主库；若仍失败，再由现有 `audit_spool_queue` 的 1/5/30/120/600 秒退避重试接管。审计事件仍先落独立缓冲库，不降低可靠性。

## 错误处理

- 同步锁被占用：不启动第二个同步，返回 `busy`，记录 WARNING，不输出异常堆栈。
- 数据库短暂锁：有限重试；成功后正常完成。
- 数据库持续锁：返回 `database_busy`，日志明确区分于正常零记录。
- 表未初始化：返回 `schema_not_ready`。
- 飞书 API 或其他异常：返回 `error` 并保留异常堆栈。
- 所有数据库异常路径必须 rollback；重试前关闭线程连接。

## 测试要求

1. 跨进程锁/进程内锁只能允许一个持有者。
2. 同步函数不再调用 `init_db()`。
3. 旧二元组和三元组解包、相等比较保持兼容。
4. 锁被占用时返回 `busy`，且不执行飞书调用。
5. SQLite 前两次 locked、第三次成功时同步能够完成。
6. 持续 locked 时返回 `database_busy`，不能伪装成普通 `(0,0)`。
7. 新用户和 Token 在同一事务创建；飞书回写发生在提交之后。
8. 审计批量落库遇到短暂锁会重试并成功。
9. 原有飞书、审计、API 文档和全项目测试无回归。
