# 管理员市场接口测试台设计规格

**日期：** 2026-07-24  
**适用源码：** `stock_server(36)`  
**功能名称：** 管理员市场接口测试台  
**目标用户：** 已登录管理员  
**当前接口基线：** 138 个 Tushare 接口 + 2 个 Kaipanla 接口；运行时以 Provider 目录为准，不写死总数

## 1. 目标

在管理员后台新增一个完整的市场接口测试中心，使管理员能够：

1. 从当前系统支持的全部市场接口中选择任意接口；
2. 严格按照 Tushare 官网或 Kaipanla 项目接口定义查看并填写全部输入参数；
3. 选择全部或部分输出字段；
4. 执行真实上游测试或正常业务链路测试；
5. 查看完整返回数据、字段解释、Schema 对比、缓存与日期回退信息；
6. 一键批量测试当前全部可测试接口；
7. 启动、取消批量任务，并只重测失败接口；
8. 完整保存每次测试的全部请求、响应、字段检查报告和任务历史；
9. 配置结果保留天数，默认 30 天，并允许锁定重要批次永久保留；
10. 检测 Tushare 官网接口定义变化，在网页端明显提示，由管理员人工确认后发布；
11. 支持管理员自由勾选一个、多个、全部可发布接口，或全不选；
12. 规格发布成功后，默认立即创建并运行“仅验证本次已发布接口”的验证任务，同时允许管理员改为稍后手工运行。

## 2. 非目标

第一版不包含：

- 暂停和继续批量任务；
- 浏览器直接访问 Tushare 或暴露服务器 Tushare Token；
- 运行时依赖 Tushare 官网页面才能打开测试台；
- 自动把官网变化直接覆盖线上正式规格；
- 将完整大结果直接写入 SQLite 的单个 JSON 字段；
- 强制终止正在执行的 Python 线程；
- 自动删除被锁定的永久保留批次；
- 默认并发执行大量上游请求。

## 3. 权威来源

### 3.1 Tushare

Tushare 接口规格以官方文档为权威来源，包括：

- 接口英文名；
- 中文名称；
- 接口说明；
- 权限、积分和调用限制说明；
- 全部输入参数；
- 全部输出参数；
- 参数类型；
- 必填性；
- 默认显示字段；
- 官方示例；
- 官方文档标识及页面地址。

官网原始内容与平台规范化规则必须分层保存，平台不得篡改官方原文。

### 3.2 Kaipanla

Kaipanla 接口规格以项目实际实现为权威来源，重点包括：

- Provider 的 catalog；
- client 请求参数；
- adapter 字段映射；
- schema 字段定义；
- bidding service 的历史快照规则；
- 当前三时点快照：`auction`、`post_open`、`close`。

Kaipanla 规格来源标记为 `project_code` 和 `provider_response_mapping`，不得标记为 Tushare 官方来源。

## 4. 总体架构

系统分为六个清晰子系统：

1. **接口规格中心**：管理官方原始规格、平台 Override、候选规格、正式有效规格和版本；
2. **单接口测试服务**：参数校验、Provider 调用、结果持久化和字段分析；
3. **批量任务服务**：任务创建、后台执行、安全取消和失败重测；
4. **结果存储服务**：完整文件归档、分页读取、下载、校验和清理；
5. **规格变化与发布中心**：官网同步、差异检测、人工确认、批量发布、回滚及发布后验证；
6. **管理员网页**：接口目录、动态表单、运行结果、批次任务、规格变化和存储管理。

推荐调用关系：

```text
管理员页面
  ├─ 接口规格中心
  ├─ 单接口测试服务
  │    └─ 现有 query_market_data()
  │          └─ ProviderRegistry
  │                ├─ TushareProvider
  │                └─ KaipanlaProvider
  ├─ 批量任务服务
  │    └─ 单接口测试服务
  ├─ 结果存储服务
  └─ 规格变化与发布中心
       ├─ 官网规格同步工具
       ├─ 规格差异服务
       └─ 发布后验证任务
```

## 5. 页面信息架构

新增后台导航项：

```text
市场接口测试台
```

建议主入口：

```text
GET /admin/interface-tester
```

页面包含五个一级页签：

1. 单接口测试；
2. 批量测试；
3. 测试历史；
4. 规格变化中心；
5. 存储与保留策略。

### 5.1 单接口测试页

布局：

- 左侧：Provider、分类、状态和关键词筛选后的接口目录；
- 中间：接口说明、完整输入参数动态表单、参数规则、预设和输出字段选择；
- 右侧或下方：执行设置和结果；
- 结果页签：执行结论、数据表格、字段解析、原始 JSON、下载。

### 5.2 批量测试页

显示：

- 接口总数；
- 可执行接口数；
- 因规格严重变化而跳过的接口数；
- 每类结果统计；
- 当前执行接口；
- 完成进度；
- 启动、取消、失败接口重测按钮；
- 批量结果下载入口。

### 5.3 规格变化中心

顶部明显显示官网变化横幅：

```text
检测到 Tushare 官网接口定义发生变化
涉及接口：N 个
严重变化：N 个
非阻断变化：N 个
当前正式规格：...
候选规格：...
```

支持：

- 单个接口查看；
- 多条件筛选；
- 单选；
- 多选；
- 全选当前页；
- 全选当前筛选结果中的全部可发布接口；
- 清空选择；
- 全不选；
- 发布所选接口。

表头复选框使用未选择、部分选择、全部选择三态。

## 6. 接口规格数据模型

### 6.1 官方原始规格层

建议目录：

```text
interface_specs/source/tushare/<api_name>.json
interface_specs/source/kaipanla/<api_name>.json
```

保存官网或源码中的原始定义，不加入平台推断。

每个接口至少包含：

```json
{
  "provider": "tushare",
  "api_name": "daily",
  "official_doc_id": 27,
  "official_title": "A股日线行情",
  "official_description": "...",
  "permission_text": "...",
  "limit_text": "...",
  "inputs": [],
  "outputs": [],
  "source_fetched_at": "2026-07-24T00:00:00+08:00",
  "source_hash": "sha256"
}
```

### 6.2 平台 Override 层

建议目录：

```text
interface_specs/overrides/tushare/<api_name>.yaml
interface_specs/overrides/kaipanla/<api_name>.yaml
```

保存平台为了生成表单、执行校验和批量测试而补充的：

- 规范化类型；
- 控件类型；
- 枚举值；
- 日期格式；
- 多值规则；
- 参数组合规则；
- 可运行预设；
- 动态模板变量；
- 输出单位和可空说明；
- 特殊字段校验规则。

### 6.3 候选规格层

官网同步后生成不可直接生效的候选版本：

```text
interface_specs/candidates/<candidate_version>/...
```

候选规格包含原始抓取结果、差异报告、解析警告、完整性状态和试运行状态。

### 6.4 正式有效规格层

发布后生成不可变正式版本：

```text
interface_specs/releases/<spec_version>/effective_specs.json
interface_specs/releases/<spec_version>/manifest.json
```

运行时读取一个原子切换的当前版本指针：

```text
interface_specs/current.json
```

历史版本不得覆盖或修改。

## 7. 输入参数完整覆盖

每一个官网输入参数都必须进入规格并能在网页填写。至少记录：

```json
{
  "name": "start_date",
  "official_type": "str",
  "normalized_type": "date",
  "required": false,
  "description": "开始日期",
  "format": "YYYYMMDD",
  "example": "20260701",
  "default_value": null,
  "multiple": false,
  "separator": null,
  "enum_values": [],
  "min_value": null,
  "max_value": null,
  "max_length": null,
  "widget": "date_picker",
  "source_order": 3,
  "source": "tushare_official"
}
```

支持的规范化参数类型：

- `string`；
- `integer`；
- `number`；
- `boolean`；
- `date`；
- `datetime`；
- `enum`；
- `stock_code`；
- `multiple_codes`；
- `json`。

支持的参数规则：

- `required`；
- `at_least_one`；
- `exactly_one`；
- `mutually_exclusive`；
- `requires`；
- `required_if`；
- `date_range`；
- `datetime_range`；
- `enum`；
- `pattern`；
- `single_value_only`；
- `multiple_values_allowed`；
- `max_items`；
- `min_value`；
- `max_value`；
- `max_length`。

浏览器端和后端均执行规则，后端结果为最终权威。

## 8. 输出参数完整覆盖

每一个官网输出字段都必须进入规格并能在页面选择和解释。至少记录：

```json
{
  "name": "close",
  "official_type": "float",
  "normalized_type": "number",
  "default_display": true,
  "description": "收盘价",
  "unit": null,
  "nullable": "unknown",
  "aliases": [],
  "deprecated": false,
  "source_order": 6
}
```

当官网类型为 `None` 或未定义时，保存为：

```json
{
  "official_type": "None",
  "normalized_type": "unknown"
}
```

实际返回类型可以作为提醒，但不得擅自回写成官网类型。

### 8.1 Tushare `fields`

`fields`不混入业务输入参数表，而是在“输出字段选择”区域处理：

- 使用官网默认字段；
- 选择全部官方字段；
- 清空选择；
- 自定义选择。

批量测试的默认预设必须选择全部官方输出字段，以验证完整返回能力。

## 9. 参数预设

每个可批量测试接口至少有一组合法预设。预设由系统内置并允许管理员在后台修改和保存。

支持动态模板：

```text
${today}
${last_trade_date}
${previous_trade_date}
${thirty_days_ago}
${latest_report_period}
${sample_stock}
${sample_index}
${sample_fund}
${sample_future}
```

批量任务启动前解析模板并执行完整后端校验。无法解析或违反规则的接口不得调用上游，结果标记为 `invalid_params`。

## 10. 单接口测试模式

### 10.1 真实上游模式

默认模式：

```text
bypass_cache = true
```

目的：验证服务器与真实 Provider、权限、参数和返回数据。

### 10.2 正常业务链路模式

```text
bypass_cache = false
```

目的：验证缓存命中、陈旧缓存、最近交易日回退及平台标准返回结构。

页面必须明确显示本次结果：

- 来自上游或缓存；
- 是否回退；
- 实际数据日期；
- Provider 耗时；
- 完整行数和字段数。

## 11. 后端路由

新增 Blueprint：

```text
routes/admin_market_test_routes.py
```

主要路由：

```text
GET  /admin/interface-tester
GET  /admin/interface-tester/catalog.json
GET  /admin/interface-tester/spec/<provider>/<api_name>.json
POST /admin/interface-tester/run
GET  /admin/interface-tester/runs/<run_id>
GET  /admin/interface-tester/runs/<run_id>/rows
GET  /admin/interface-tester/runs/<run_id>/download/<format>

POST /admin/interface-tester/batches
GET  /admin/interface-tester/batches
GET  /admin/interface-tester/batches/<batch_id>
POST /admin/interface-tester/batches/<batch_id>/cancel
POST /admin/interface-tester/batches/<batch_id>/retry-failures
POST /admin/interface-tester/batches/<batch_id>/lock
POST /admin/interface-tester/batches/<batch_id>/unlock
POST /admin/interface-tester/batches/<batch_id>/retention
POST /admin/interface-tester/batches/<batch_id>/delete
GET  /admin/interface-tester/batches/<batch_id>/download

GET  /admin/interface-tester/spec-changes
GET  /admin/interface-tester/spec-changes/<provider>/<api_name>
POST /admin/interface-tester/spec-releases/preflight
POST /admin/interface-tester/spec-releases/publish
POST /admin/interface-tester/spec-releases/<release_id>/rollback
```

所有写操作必须使用 POST、管理员 Session、CSRF、IP 白名单和操作审计。

## 12. 批量任务设计

批量测试通过后台任务执行，不在一个 HTTP 请求中同步等待全部接口。

### 12.1 批次状态

```text
queued
running
cancelling
cancelled
completed
completed_with_failures
failed
```

### 12.2 单项状态

```text
pending
running
success_data
success_empty
success_fallback
permission_denied
scope_denied
invalid_params
unsupported
timeout
upstream_error
schema_mismatch
spec_change_pending
result_too_large
cancelled
internal_error
```

### 12.3 取消

采用安全取消：

1. 设置 `cancel_requested=true`；
2. 不再启动新的接口；
3. 当前请求允许完成或达到超时；
4. 尚未执行的项目标记为 `cancelled`；
5. 保留已经生成的全部结果。

### 12.4 失败重测

重测创建新子批次：

```text
BATCH-...-R1
BATCH-...-R2
```

默认重测：

- `permission_denied`；
- `scope_denied`；
- `invalid_params`；
- `unsupported`；
- `timeout`；
- `upstream_error`；
- `schema_mismatch`；
- `result_too_large`；
- `internal_error`。

不覆盖原批次和原文件。

## 13. 任务持久化

新增 SQLite 表：

### 13.1 `admin_api_test_batches`

保存：

- 批次ID；
- 父批次ID；
- 任务类型；
- 状态；
- 接口总数与分类统计；
- 创建、开始、完成时间；
- 取消请求；
- 规格版本和 Hash；
- 结果总大小；
- 保留天数；
- 到期时间；
- 锁定状态和原因；
- 清理状态。

### 13.2 `admin_api_test_items`

保存：

- 批次ID；
- Provider；
- 接口名；
- 执行顺序；
- 参数摘要；
- 状态；
- HTTP与业务状态；
- 行数和字段数；
- 耗时；
- 缓存与回退摘要；
- 错误分类；
- 完整结果路径、格式、压缩方式、大小和 SHA-256；
- 规格版本和接口规格 Hash。

### 13.3 `admin_api_test_events`

保存：

- 任务创建；
- 状态变化；
- 取消；
- 重测；
- 锁定、解锁；
- 保留策略变化；
- 清理；
- 系统异常。

### 13.4 规格相关表

建议新增：

- `market_interface_spec_versions`；
- `market_interface_spec_changes`；
- `market_interface_spec_releases`；
- `market_interface_spec_release_items`。

数据库只存索引、摘要、状态和文件指针，不存全部大结果正文。

## 14. 完整结果存储

完整结果保存在文件系统：

```text
data/admin_api_test_results/YYYY/MM/DD/<batch_id>/<provider>/<api_name>/
```

每个接口目录至少包括：

```text
request.json
result.json.gz
schema_report.json
metadata.json
```

可转换为二维表时，可按需生成：

```text
result.csv.gz
```

### 14.1 `result.json.gz`

必须保存平台标准完整响应，包括全部 `data`：

- `success`；
- `code`；
- `provider`；
- `data_type`；
- `source`；
- `freshness`；
- `snapshot`；
- `quality`；
- `count`；
- 全部 `data`；
- `msg`；
- 错误元数据。

失败结果也完整保存。

### 14.2 敏感数据排除

严禁归档：

- Tushare Token；
- API Token；
- 管理员密码；
- Session Cookie；
- CSRF Token；
- `.env`内容。

### 14.3 大结果保护

配置单接口结果安全上限；达到上限时不得静默截断。状态标记为 `result_too_large`，保存诊断信息并提示管理员调整参数或配置。

## 15. 页面读取完整结果

后台保存全部数据，但浏览器分页展示：

```text
GET /admin/interface-tester/runs/<run_id>/rows?page=1&page_size=100
```

支持：

- 总行数；
- 分页；
- 字段选择；
- 横向滚动；
- 空值统计；
- 字段搜索；
- 完整 JSON.gz 下载；
- CSV.gz 下载；
- 单批次 ZIP 下载；
- 汇总 CSV；
- 失败接口报告。

## 16. 结果解释与 Schema 校验

每个结果生成 `schema_report.json`，至少包含：

- 官方输出字段；
- 本次请求字段；
- 实际返回字段；
- 缺少的已请求字段；
- 未定义新增字段；
- 类型差异；
- 每列空值数；
- 每列实际类型；
- 结果判定。

字段缺失只有在“本次明确请求该字段但未返回”时才判异常。未选择的字段不判失败。

## 17. 规格完整性检查

新增工具：

```text
tools/validate_interface_specs.py
```

必须检查：

1. Provider目录中的每个接口都有规格；
2. 规格中的接口都在Provider目录；
3. 全部官网输入参数已收录；
4. 全部官网输出参数已收录；
5. 参数和字段名称不重复；
6. 组合规则只引用存在的参数；
7. 每个接口至少有一组合法批量预设；
8. 批量预设可解析并通过规则；
9. 全部输出字段可以生成 `fields`；
10. Kaipanla规格与实际 Schema 一致；
11. 正式版本 manifest 和 Hash 有效。

状态：

```text
complete
warning
incomplete
official_changed
```

只有 `complete` 和非阻断 `warning` 可进入正式批量测试。

## 18. Tushare 官网同步和变化检测

同步工具建议：

```text
tools/sync_tushare_interface_specs.py
```

同步流程：

1. 读取当前 Provider 中138个Tushare接口；
2. 获取各自官方文档页面；
3. 解析完整输入参数和输出参数；
4. 保存原始快照和来源 Hash；
5. 生成候选规格；
6. 与当前正式规格逐字段比较；
7. 生成变化等级和差异报告；
8. 不自动发布。

变化等级：

### 非阻断

- 文案、标点、排版变化；
- 新增可选输入参数；
- 新增输出字段。

### 阻断

- 必填性变化；
- 参数类型变化；
- 参数删除；
- 参数改名；
- 输出字段删除或改名；
- 接口下线；
- 官网页面解析失败；
- 规格完整性失败。

阻断变化的接口在批量任务中标记为 `spec_change_pending`，不作为普通调用失败。

## 19. 人工确认和自由选择发布

管理员可以选择：

- 某一个接口；
- 任意多个接口；
- 当前页全部可发布接口；
- 当前筛选结果全部可发布接口；
- 清空选择；
- 全不选。

翻页和筛选后保留已选择集合。

不可发布接口的复选框禁用，并显示具体原因。

### 19.1 发布预检查

发布前重新检查：

- 候选版本未被并发修改；
- 官方输入和输出覆盖完整；
- Override规则有效；
- 批量预设合法；
- 试运行已完成；
- Hash一致；
- 无阻断错误。

### 19.2 选择中含不可发布项

页面提供：

- 返回修改；
- 取消发布；
- 管理员主动移除未通过项目后重新预检查。

系统不得自动跳过失败项目后继续发布。

### 19.3 原子发布

一次发布单中的所选接口整体原子切换：

- 全部成功；或
- 全部保持旧正式版本。

不得出现同一发布单部分接口已切换、部分未切换。

### 19.4 二次确认

发布要求：

- 管理员Session；
- IP白名单；
- CSRF；
- 管理员密码二次确认；
- 发布说明；
- 明确显示接口数量的确认按钮。

## 20. 发布后自动验证

批量发布成功后显示两个选项：

```text
立即运行验证
稍后手工运行
```

默认选中“立即运行验证”。

立即验证时：

1. 创建一个只包含本次发布接口的新批量验证任务；
2. 使用新正式规格和对应批量预设；
3. 默认执行真实上游模式；
4. 完整保存所有响应；
5. 在发布单详情页显示验证进度和结果；
6. 验证失败不自动回滚，但显示红色警告并提供回滚入口。

## 21. 规格发布与回滚

每次发布生成：

- 发布单号；
- 发布前版本；
- 发布后版本；
- 所选接口；
- 每个接口旧、新 Hash；
- 变化摘要；
- 管理员；
- 发布时间；
- 发布说明；
- 自动验证任务ID。

支持：

- 回滚整个发布单；
- 选择一个或多个接口回滚。

任何回滚都生成新的正式版本，不修改历史版本。

## 22. 结果保留策略

默认配置：

```env
ADMIN_API_TEST_RETENTION_DAYS=30
ADMIN_API_TEST_CLEANUP_ENABLED=true
ADMIN_API_TEST_CLEANUP_HOUR=3
```

规则：

- 单接口和批量测试默认保留30天；
- 到期时间从完成时间计算；
- 管理员可修改单批次保留天数；
- 管理员可锁定为永久保留；
- 锁定批次不参与自动清理；
- 解锁后从解锁时间按批次保留天数重新计算；
- `queued`、`running`、`cancelling` 不清理；
- 清理失败保留索引并标记 `delete_failed`。

建议支持：

```text
7、30、90、180、365天、自定义、永久
```

## 23. 删除与清理安全

清理流程：

1. 批次标记 `deleting`；
2. 写开始事件；
3. 解析并校验目录必须位于配置结果根目录；
4. 校验目录名与批次ID一致；
5. 删除完整结果目录；
6. 确认目录不存在；
7. 更新明细和批次状态；
8. 写完成审计。

锁定批次手工删除要求：

1. 先解除锁定；
2. 输入管理员密码；
3. 再确认永久删除。

## 24. 磁盘保护

建议配置：

```env
ADMIN_API_TEST_DISK_WARNING_PERCENT=80
ADMIN_API_TEST_DISK_CRITICAL_PERCENT=90
ADMIN_API_TEST_MAX_CONCURRENT_BATCHES=1
ADMIN_API_TEST_MAX_CONCURRENT_ITEMS=2
```

达到80%显示警告；达到90%禁止启动新的完整批量测试，但允许查看、下载、清理和删除。任何情况下都不得自动删除锁定批次。

## 25. 安全要求

1. 所有接口必须在 Provider 白名单和正式规格中；
2. 不允许管理员提交任意未知 `api_name`；
3. 不显示或接收 Tushare Token；
4. 所有写路由使用 POST；
5. 依赖现有管理员 Session、CSRF和IP白名单；
6. 单管理员每分钟调用次数受限；
7. 单个管理员同时最多运行一个真实上游单接口请求；
8. 批量并发默认2，允许配置；
9. 所有参数长度和数组数量有限制；
10. 所有文件下载必须验证归属和允许根目录；
11. 所有高风险操作写操作审计；
12. 发布、回滚、删除锁定批次要求管理员密码二次确认。

## 26. 操作审计

建议动作代码：

```text
admin.market_interface_test.run
admin.market_interface_test.batch_create
admin.market_interface_test.batch_cancel
admin.market_interface_test.retry_failures
admin.market_interface_test.lock
admin.market_interface_test.unlock
admin.market_interface_test.retention_change
admin.market_interface_test.delete
admin.market_interface_spec.sync
admin.market_interface_spec.publish
admin.market_interface_spec.rollback
```

审计参数必须脱敏，不记录Token、密码、Session和CSRF。

## 27. 推荐源码结构

新增：

```text
routes/admin_market_test_routes.py
services/admin_market_test_service.py
services/admin_market_batch_service.py
services/admin_market_test_repository.py
services/admin_market_result_storage.py
services/admin_market_test_cleanup_service.py
services/market_interface_spec_service.py
services/market_interface_spec_diff.py
services/market_interface_spec_release.py
services/market_interface_spec_sync.py
interface_specs/source/...
interface_specs/overrides/...
tools/sync_tushare_interface_specs.py
tools/validate_interface_specs.py
```

修改：

```text
app.py
config.py
.env.example
db_utils.py
routes/admin_api_doc_routes.py 或共享管理员导航组件
```

第一版应继续遵循现有项目内联HTML风格，避免在同一功能中额外引入前端框架。为减少重复，建议提取共享管理员导航和基础页面样式，但不做无关页面重构。

## 28. 测试策略

### 28.1 规格测试

- 目录和规格一一对应；
- 全输入、全输出覆盖；
- 规则引用有效；
- 全字段 `fields` 可生成；
- 预设可运行；
- Kaipanla三快照枚举完整。

### 28.2 单接口服务测试

- 参数类型转换；
- 组合规则；
- 上游与缓存模式；
- 成功、空数据、回退、权限不足、超时；
- 全结果文件完整性；
- 敏感字段排除；
- Schema报告。

### 28.3 批量任务测试

- 创建和启动；
- 状态转换；
- 安全取消；
- 失败重测子批次；
- 服务重启恢复；
- 并发上限；
- 规格阻断跳过；
- 汇总统计。

### 28.4 发布测试

- 官网变化分类；
- 任意选择集合；
- 当前页和筛选结果全选；
- 不可发布项禁用；
- 预检查；
- 原子发布；
- 并发Hash冲突；
- 局部和整单回滚；
- 发布后自动验证任务。

### 28.5 清理测试

- 30天默认保留；
- 锁定永久保留；
- 解锁重新计算；
- 运行中不清理；
- 路径穿越防护；
- 删除失败可重试；
- 磁盘阈值阻止新批次。

### 28.6 真实环境验收

真实Tushare和Kaipanla调用必须在测试或生产等价环境执行，并记录：

- 使用规格版本；
- 实际权限；
- 调用耗时；
- 数据总量；
- 结果文件大小；
- 磁盘增长；
- 批量总时长；
- 失败分类；
- 取消响应时间；
- 发布后验证结果。

## 29. 分阶段交付

虽然第一版包含单接口和全量批量测试，建议在一个实施计划内按以下可独立验收阶段交付：

1. 规格中心和完整性工具；
2. 单接口测试和完整结果存储；
3. 批量任务、取消和失败重测；
4. 结果历史、下载、30天清理和永久锁定；
5. 官网变化、差异页面和自由选择发布；
6. 原子发布、回滚和发布后自动验证；
7. 全量回归和真实环境验收。

## 30. 第一版验收标准

功能通过验收必须同时满足：

1. 当前Provider中的全部接口均有有效规格；
2. 每个接口全部输入参数可见、可填写、可校验；
3. 每个接口全部输出字段可选择、可解释、可对照；
4. 每个批量接口有合法预设；
5. 可执行单接口真实上游和正常链路测试；
6. 可启动全部接口批量任务；
7. 可安全取消；
8. 可只重测失败接口；
9. 所有成功和失败响应完整落盘；
10. 页面可分页查看并下载完整结果；
11. 默认保留30天；
12. 批次可锁定永久保留；
13. 官网变化在网页明显提示；
14. 管理员可自由选择零个、一个、多个或全部可发布接口；
15. 发布单原子生效；
16. 发布后默认立即运行所选接口验证任务；
17. 历史任务绑定原规格版本，不随新版本改变；
18. 未泄露任何Token、密码、Cookie或`.env`内容；
19. 自动化测试、语法检查和关键真实环境验收均有可复核记录。
