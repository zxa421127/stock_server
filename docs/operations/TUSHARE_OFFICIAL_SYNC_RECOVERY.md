# TuShare 官网规格全量校准与故障恢复

## 目的

将项目中的 138 个 TuShare 接口逐个与官网文档校准。官网检查只生成变化提醒；正式规格必须由管理员审核候选后发布。任何 `complete_sync=false` 的候选均禁止发布。

## 本次修复的同步缺陷

1. 兼容 TuShare 机器 Markdown 将整张参数表压缩在单行的格式。
2. 机器 Markdown 可下载但解析失败时，自动回退公开 HTML 文档。
3. 允许官网明确存在、但数据行为空的输入参数表，避免误判为解析失败。
4. 权限积分同步时同时更新 `permission_text`、`permission_label` 和授权 `scope`。
5. 部分同步候选禁止发布，避免 113/138 之类的候选覆盖正式规格。
6. 页面直接显示失败接口摘要，并将不完整候选标红、禁用发布按钮。

## 部署后执行

在项目根目录、项目虚拟环境中执行：

```bash
python -m tools.db.migrate
python -m tools.sync_full_api_docs
```

重启 Web 和 TuShare 规格监控 Worker 后，执行首次全量检查：

```bash
python -m tools.sync_tushare_interface_specs > tushare-scan.json
```

命令返回码：

- `0`：138 个 TuShare 文档全部检查成功；
- `2`：存在抓取或解析失败。查看 `tushare-scan.json` 的 `failures`。

失败时可以先检查 DNS、HTTPS、代理、防火墙和官网限流，再通过管理页面重新检查，或逐个重试：

```bash
python -m tools.sync_tushare_interface_specs --api etf_index
python -m tools.sync_tushare_interface_specs --api 失败接口英文名
```

## 管理页面操作

1. 打开“市场接口测试台 → 规格变化”。
2. 确认最近扫描为 `成功 138/138、失败 0`。
3. 选择全部待同步提醒并生成候选。
4. 候选必须显示 `complete_sync=true`；不完整候选禁止发布。
5. 审核字段差异，输入管理员密码并通过当前客户端证书后发布。
6. 确认发布后二次官网核验通过。
7. 重新同步 API 文档数据库：

```bash
python -m tools.sync_full_api_docs
```

## 严格验收

```bash
python -m tools.audit_interface_specs \
  --require-official-tushare \
  --output docs/operations/tushare-production-audit.json
```

生产验收必须满足：

```text
total = 140
tushare_pending_official = 0
incomplete = 0
missing_input_count = 0
missing_output_count = 0
catalog_seed_count = 0
sample_description_count = 0
forbidden_fields_input_count = 0
```

如果任意一项不为 0，不应宣称 140 个接口已经完成官网校准。

## ETF 基准指数接口

项目使用的正式接口文档地址为：

```text
https://tushare.pro/document/2?doc_id=386
```

`document/1?doc_id=13` 是平台积分说明，不是 `etf_index` 接口规格页。

`etf_index` 的正式契约为 3 个输入、8 个输出，权限 8000 积分，单次最多 5000 行。
