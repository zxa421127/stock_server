# TuShare 官网规格监控与全量校准部署说明

## 目标

本补丁把原先“从项目请求/响应样例推断规格”的机制改为：

1. 当前正式规格只由已发布版本提供；
2. 系统每周三、周日北京时间 02:30 扫描 TuShare 官网；
3. 扫描只写入官网快照和变化提醒，不自动覆盖正式规格；
4. 管理员在“市场接口测试台 → 规格变化”中选择提醒并重新同步；
5. 同步生成候选版本，管理员审核、输入密码后发布；
6. 发布后立即重新抓取官网并逐项核验；
7. 核验通过后提醒状态变为 `verified`。

## 本补丁已直接校准的接口

`ci_daily` 已按文档 308 固定为：

- 输入：`ts_code`、`trade_date`、`start_date`、`end_date`；
- 输出：`ts_code`、`trade_date`、`open`、`low`、`high`、`close`、`pre_close`、`change`、`pct_change`、`vol`、`amount`；
- 数值字段官网类型统一为 `float`，平台规范化类型为 `number`；
- 权限说明：5000 积分；
- 限量：单次最大 4000 条。

## 数据库变化

应用启动调用 `init_db()` 时自动创建：

- `tushare_spec_scan_runs`
- `tushare_spec_snapshots`
- `tushare_spec_change_alerts`
- `tushare_spec_monitor_leases`

不需要手工执行 SQL，不修改已有业务表。

## 环境变量

```env
TUSHARE_SPEC_MONITOR_ENABLED=True
TUSHARE_SPEC_MONITOR_IN_PROCESS=True
TUSHARE_SPEC_MONITOR_TIMEZONE=Asia/Shanghai
TUSHARE_SPEC_MONITOR_WEEKDAYS=wed,sun
TUSHARE_SPEC_MONITOR_HOUR=2
TUSHARE_SPEC_MONITOR_MINUTE=30
TUSHARE_SPEC_MONITOR_LEASE_SECONDS=21600
```

单进程部署可以保留 `TUSHARE_SPEC_MONITOR_IN_PROCESS=True`。

Gunicorn、uWSGI 或多 Web 进程部署建议设置：

```env
TUSHARE_SPEC_MONITOR_IN_PROCESS=False
```

并单独运行：

```bash
python -m tools.tushare_spec_monitor_worker
```

数据库租约会阻止多个进程同时扫描。

## 首次全量校准步骤

当前代码包内置 `etf_basic` 与 `ci_daily` 的官方规格。其余 TuShare 接口需要部署到可访问 TuShare 官网的服务器后执行首次扫描。

1. 覆盖代码并重启服务；
2. 打开“市场接口测试台 → 规格变化”；
3. 点击“立即检查官网”；
4. 确认扫描结果为 `成功 138/138、失败 0`；
5. 点击“全选待同步”；
6. 点击“同步所选变化”；
7. 在候选规格中核对差异，选择全部可发布接口；
8. 输入管理员密码发布；
9. 查看发布后二次官网核验结果；
10. 执行严格审计：

```bash
python -m tools.audit_interface_specs \
  --require-official-tushare \
  --output docs/interface-spec-audit-production.json
```

最终应满足：

```text
tushare_pending_official = 0
catalog_seed_count = 0
sample_description_count = 0
incomplete = 0
missing_output_count = 0
forbidden_fields_input_count = 0
```

任何接口抓取或解析失败时，不允许发布“全量校准完成”。

## 命令行操作

只检查官网并生成提醒：

```bash
python -m tools.tushare_spec_monitor scan
```

只检查一个接口：

```bash
python -m tools.tushare_spec_monitor scan --api ci_daily
```

查看待处理提醒：

```bash
python -m tools.tushare_spec_monitor status
```

根据提醒生成候选：

```bash
python -m tools.tushare_spec_monitor sync-alerts --alert-id 1 --alert-id 2
```

旧命令：

```bash
python -m tools.sync_tushare_interface_specs
```

现在也只执行官网检查并生成提醒，不再绕过提醒流程直接生成候选。

## 差异比较范围

系统检查：

- 接口标题、描述、权限/积分、限量；
- 官方文档 ID 和公开地址；
- 输入参数新增、删除、顺序、类型、必选、描述；
- 输出字段新增、删除、顺序、类型、默认显示、描述。

原始文档哈希与语义规格哈希分开保存。语义哈希不包含抓取时间，也不因机器 Markdown 地址与公开 HTML 地址不同而变化。

## 回滚

1. 停止 Web 和监控 Worker；
2. 恢复覆盖前代码；
3. 将 `interface_specs/current.json` 恢复为原版本；
4. 重启服务。

新增监控表可保留，不影响旧代码。需要彻底删除时应先备份数据库，再删除四张 `tushare_spec_*` 表。
