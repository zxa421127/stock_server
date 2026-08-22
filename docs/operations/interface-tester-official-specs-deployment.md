# 市场接口测试台方案B部署与官网全量同步说明

## 1. 本补丁解决的问题

本补丁将市场接口测试台改为统一接口元数据驱动，并完成以下代码改造：

1. 测试台复用 API 文档管理中的业务类目，支持 Provider、业务类目和关键词组合筛选。
2. TuShare 官网规格同步优先读取机器可读 Markdown 文档，兼容 HTML 回退；同步结果先生成候选版本，经完整性检查和管理员确认后才发布。
3. `tushare/etf_basic` 当前活动规格已按官网固定为 6 个输入参数和 14 个输出字段。
4. 用户不能选择、删减输出字段；单接口、批量、重试和发布后验证统一请求当前已发布规格中的全部输出字段。
5. 默认保留天数改为数据库持久化管理员设置，`.env` 的 30 天仅作为首次初始化回退值。
6. 增加规格审计工具、同步 CLI、单元测试和部署检查。

## 2. 部署前备份

至少备份以下内容：

- 当前源码目录；
- `interface_specs/current.json` 和 `interface_specs/releases/`；
- 生产数据库；
- 当前 `.env`。

补丁包不包含 `.env`、Token、数据库、运行结果、日志或虚拟环境。

## 3. 覆盖文件并重启

将压缩包内文件按相同相对路径覆盖到项目根目录。不要删除服务器原有 `.env`。

本次没有新增第三方 Python 依赖。重启应用后，已有 `db_utils.init_db()` 流程会自动创建：

```text
admin_api_test_settings
```

该表用于保存 `default_retention_days` 等管理员设置。

## 4. 首次启动检查

打开：

```text
/admin/interface-tester
```

确认：

- Provider 下拉框显示接口数量；
- 新增“全部类目”下拉框；
- 左侧接口按业务类目分组；
- ETF 基本信息显示 6 个输入参数和 14 个只读输出字段；
- 页面不存在输出字段复选框；
- “默认保留”卡片可以输入 1～36500 的整数并保存；
- 保存后刷新页面，数值保持不变。

## 5. 在可访问 TuShare 官网的服务器执行全量同步

推荐通过命令行执行，避免 Web 请求被反向代理超时：

```bash
python -m tools.sync_tushare_interface_specs
```

该命令只生成候选版本，不会自动覆盖正式规格。成功退出的必要条件为：

```text
target_count = 138
success_count = 138
complete_sync = true
fetch_error_count = 0
parse_error_count = 0
coverage_percent = 100.0
```

同步返回非零退出码时，不要发布候选。先查看候选目录的：

```text
interface_specs/candidates/<candidate-version>/manifest.json
interface_specs/candidates/<candidate-version>/diffs.json
interface_specs/candidates/<candidate-version>/effective_specs.json
```

常见失败原因包括官网网络不可达、官网文档结构变化、目录接口名和页面接口名不一致、重复字段或输入/输出表解析失败。

## 6. 管理员审核和发布

在“规格变化”页中：

1. 查看全量同步覆盖率和失败接口；
2. 逐项检查阻断变化；
3. 对必选参数补充可运行的批量默认值；
4. 确认每个候选均显示“通过”；
5. 选择待发布接口并输入管理员密码；
6. 原子发布所选规格；
7. 建议立即创建真实上游验证批次。

同步和发布分离是有意设计：官网页面变化不会在无人审核时直接影响生产请求。

## 7. 发布后全量审计

执行：

```bash
python -m tools.audit_interface_specs \
  --require-official-tushare \
  --output docs/interface-spec-audit-production.json
```

全部 138 个 TuShare 接口完成同步发布后，期望：

```text
total = 140
tushare_pending_official = 0
incomplete = 0
missing_output_count = 0
forbidden_fields_input_count = 0
```

随后运行项目测试：

```bash
pytest tests/test_tushare_spec_sync_service.py \
       tests/test_sync_tushare_interface_specs_cli.py \
       tests/test_market_interface_specs.py \
       tests/test_admin_market_test_routes.py \
       tests/test_admin_market_test_service.py \
       tests/test_admin_api_test_batch_service.py \
       tests/test_admin_api_test_repository.py \
       tests/test_admin_api_test_cleanup_service.py \
       tests/test_interface_test_params.py \
       tests/test_interface_spec_audit_tool.py \
       tests/test_api_doc_service.py -q
```

## 8. 当前补丁中的启动规格说明

补丁附带的启动规格版本为：

```text
spec-20260725-official-bootstrap-v1
```

它用于确保升级后立即具备：

- 140 个接口和 12 个原业务类目；
- ETF 基本信息准确的 6 入参、14 出参；
- 所有 TuShare 规格移除用户可提交的 `fields` 输入；
- 开盘啦 2 个项目定义接口保持已确认状态。

受本次沙箱运行环境 DNS 限制，无法在打包环境中联网抓取其余 137 个 TuShare 页面。因此启动规格会把这些接口明确标记为“官网未确认”，正式批量测试会安全跳过，直到在可联网生产服务器完成第 5～7 节的同步、审核和发布。系统不会把示例响应猜测字段伪装成已官网确认规格。

## 9. 回滚

发生问题时：

1. 停止应用；
2. 恢复部署前源码备份；
3. 恢复原 `interface_specs/current.json`；
4. 必要时恢复数据库备份；
5. 重启并验证原测试台。

新增的 `admin_api_test_settings` 表可以保留，不会影响旧代码；也可以在确认完全回滚后手工删除。
