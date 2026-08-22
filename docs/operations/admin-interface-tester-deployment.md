# 管理员市场接口测试台部署与使用说明

## 1. 功能范围

管理员后台新增“市场接口测试台”，路径：

```text
/admin/interface-tester
```

仅管理员 Session 可以访问。POST 操作沿用项目全局 CSRF 校验；管理员 IP 白名单启用时也继续生效。

第一版包含：

- 单接口动态参数测试；
- 一键测试当前全部市场接口；
- 选择部分接口测试；
- 启动、取消、仅重测失败接口；
- Tushare 官方规格候选同步、差异提示、人工选择发布；
- 发布后默认立即验证本次已发布接口；
- 完整结果归档、分页查看及批次 ZIP 下载；
- 默认 30 天保留，重要批次可锁定永久保留；
- 过期结果自动清理和磁盘空间保护。

接口数量来自 Provider 目录，不在页面中写死。当前种子目录包含 138 个 Tushare 接口及 2 个 Kaipanla 接口。

## 2. 数据库升级

本功能使用现有 SQLite 数据库，并由 `db_utils.init_db()` 自动创建：

```text
admin_api_test_batches
admin_api_test_items
admin_api_test_events
```

部署前仍建议备份生产数据库。无需删除或重建已有表。

## 3. 配置

复制 `.env.example` 中以下配置到生产 `.env`，按服务器磁盘和调用额度调整：

```env
ADMIN_API_TEST_RESULT_DIR=data/admin_api_test_results
ADMIN_API_TEST_SPEC_DIR=interface_specs
ADMIN_API_TEST_RETENTION_DAYS=30
ADMIN_API_TEST_CLEANUP_ENABLED=true
ADMIN_API_TEST_CLEANUP_HOUR=3
ADMIN_API_TEST_MAX_CONCURRENT_BATCHES=1
ADMIN_API_TEST_MAX_CONCURRENT_ITEMS=2
ADMIN_API_TEST_MAX_RESULT_BYTES=1073741824
ADMIN_API_TEST_PREVIEW_PAGE_SIZE=100
ADMIN_API_TEST_MAX_PREVIEW_PAGE_SIZE=500
ADMIN_API_TEST_DISK_WARNING_PERCENT=80
ADMIN_API_TEST_DISK_CRITICAL_PERCENT=90
ADMIN_API_TEST_OFFICIAL_SYNC_TIMEOUT_SECONDS=30
ADMIN_API_TEST_OFFICIAL_SYNC_DELAY_MS=150
ADMIN_API_TEST_IN_PROCESS_WORKER=true
```

`ADMIN_API_TEST_MAX_RESULT_BYTES` 是单个接口完整响应的安全上限。超过上限会明确标记为 `result_too_large`，不会静默截断为“成功”。

## 4. Worker 部署方式

### 4.1 单进程 Waitress

使用：

```env
ADMIN_API_TEST_IN_PROCESS_WORKER=true
```

运行：

```bat
.venv\Scripts\python.exe run_waitress.py
```

Web 进程会启动一个持久化批量 Worker 和一个每日清理 Worker。

### 4.2 多进程 Gunicorn 或多个 Web 实例

每个 Web 进程使用：

```env
ADMIN_API_TEST_IN_PROCESS_WORKER=false
```

另起且只起一个独立进程：

```bash
python tools/admin_api_test_worker.py
```

Windows 可运行：

```bat
scripts/windows/run_admin_api_test_worker.bat
```

此模式下，Web 页面创建的任务只写入 SQLite 队列；独立 Worker 每秒轮询并执行持久化任务，避免多个 Web 进程重复执行同一批次。

生产服务账号必须对 `ADMIN_API_TEST_RESULT_DIR` 和 `ADMIN_API_TEST_SPEC_DIR` 具有读写权限，因为结果归档、候选规格和正式版本均使用原子文件写入。

## 5. Tushare 规格工作流

种子规格用于让管理员查看目录并进行单接口诊断，但正式批量基线对 Tushare 有严格门槛：

1. 执行官网规格同步；
2. 页面显示官网变化和候选版本；
3. 管理员查看输入参数、输出字段、约束及差异；
4. 勾选一个、多个、当前筛选结果全部或全不选；
5. 通过完整性检查和试运行后原子发布；
6. 默认立即创建仅验证本次发布接口的批量任务。

未人工确认发布的 Tushare 规格，在正式批量任务中标记为：

```text
spec_change_pending
```

它属于“规格待确认而跳过”，不是普通上游失败。管理员仍可在单接口页面进行诊断测试。

CLI 同步候选规格：

```bat
.venv\Scripts\python.exe tools\sync_tushare_interface_specs.py
```

严格检查正式规格：

```bat
.venv\Scripts\python.exe tools\validate_interface_specs.py --require-official-tushare
```

官网同步只生成候选版本，不会自动覆盖当前正式规格。候选接口的默认测试参数必须通过候选输入定义、必填项和组合规则检查，才能勾选发布。管理员可在候选表格中使用“修改并保存”完善批量默认参数，并使用“编辑参数约束/字段解释”补充规范化类型、日期格式、枚举、多值、范围、正则、单位、空值口径和参数组合规则。官网字段名、官网类型、必填性、说明及顺序保持只读，平台补充规则不会改写官方原始快照。

## 6. 结果存储

每个接口结果目录包含：

```text
request.json
result.json.gz
schema_report.json
result.csv.gz（二维数据时）
```

`result.json.gz` 保存完整平台响应，包括全部 `data`、`source`、`freshness`、`snapshot`、`quality`、`count` 和错误信息。页面只分页读取，后台文件不按预览行数截断。

每个批次还生成：

```text
manifest.json
```

批次下载接口会按需生成完整 ZIP。

严禁在请求参数或结果归档中保存服务器 Token、管理员密码、Session Cookie 或 CSRF Token；服务端会拒绝敏感参数名。

## 7. 保留与清理

- 普通任务在完成后默认保留 30 天；
- 管理员可修改单批次保留天数；
- 锁定批次永久保留，不参与自动清理；
- 解锁后从解锁时间重新计算到期日；
- 排队、运行和正在取消的任务不会清理；
- 删除失败时保留数据库索引并显示 `delete_failed`；
- 锁定批次必须先解锁，之后输入管理员密码才能永久删除。

磁盘使用达到警告阈值时页面提示；达到临界阈值时禁止启动新的大批量任务，但仍允许查看、下载和清理历史结果。

## 8. 管理员验收步骤

1. 登录管理员后台并打开 `/admin/interface-tester`；
2. 确认目录数量、规格完整率及官方确认状态；
3. 先选一个低成本接口执行真实上游测试；
4. 检查参数、返回数据表、字段解析和原始 JSON；
5. 同步并人工发布 Tushare 官方规格；
6. 启动全部接口批量测试；
7. 测试取消和失败重测；
8. 检查完整结果下载、锁定、修改保留期及解锁；
9. 在测试环境验证过期清理；
10. 确认生产结果目录具有充足磁盘空间和备份策略。

## 9. 测试命令

```bat
.venv\Scripts\python.exe -m pytest -q tests
```

本补丁的自动化测试使用 Mock/隔离数据库，不会主动连接真实 Tushare、Kaipanla 或飞书。生产验收必须由管理员使用真实服务器配置执行。
