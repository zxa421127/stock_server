# 市场接口测试台统一元数据与官方规格同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让140个市场接口由统一规格驱动分类、输入表单和全字段输出，并提供可持久化的管理员默认保留天数。

**Architecture:** 规格中心继续使用不可变 release/candidate 架构；TuShare 同步器改为优先解析官方 Markdown 文档端点，候选检查通过后发布。测试执行服务彻底移除客户端字段选择，统一从正式规格生成全部输出字段。保留策略通过数据库设置仓储集中读取。

**Tech Stack:** Python 3、Flask、SQLite、requests、原生 HTML/CSS/JavaScript、pytest。

## Global Constraints

- 当前目录基线为138个 TuShare接口和2个 Kaipanla接口，运行时不得写死140作为业务逻辑。
- TuShare 输入和输出字段以官方文档为准；不得从请求示例或第一条响应推断正式规格。
- 用户不得选择输出字段；执行、重试和导出均以正式规格全部字段为基线。
- 默认保留天数范围为1–36500，数据库值优先，环境变量只作初始化回退。
- 不打包 `.env`、Token、数据库、虚拟环境、日志、真实测试结果。

---

### Task 1: 建立测试基线和官方 Markdown 解析契约

**Files:**
- Modify: `services/tushare_spec_sync_service.py`
- Modify: `tests/test_tushare_spec_sync_service.py`
- Create: `tests/fixtures/tushare_docs/etf_basic_385.md`
- Create: `tests/fixtures/tushare_docs/income_33.md`

**Interfaces:**
- Produces: `parse_tushare_official_document(text: str, source_url: str) -> dict`
- Produces: `TushareSpecSyncService.official_markdown_url(spec: dict) -> str`

- [ ] 写 ETF 6输入/14输出和长财务表解析的失败测试。
- [ ] 运行目标测试确认失败原因来自缺少 Markdown 解析能力。
- [ ] 实现 Markdown 标题、描述、权限/限量、输入表、输出表解析，并保留顺序。
- [ ] 增加重复字段、接口名不匹配、输出表为空的校验。
- [ ] 运行同步器测试并确认通过。

### Task 2: 全量同步候选及审计报告

**Files:**
- Modify: `services/tushare_spec_sync_service.py`
- Modify: `services/market_interface_spec_service.py`
- Modify: `tools/sync_tushare_interface_specs.py`
- Create: `tools/audit_interface_specs.py`
- Modify: `tests/test_tushare_spec_sync_service.py`
- Modify: `tests/test_market_interface_specs.py`

**Interfaces:**
- Produces: `sync_official_specs(api_names=None, publish=False, published_by='') -> dict`
- Produces: candidate manifest fields `target_count`, `success_count`, `fetch_error_count`, `parse_error_count`, `failed_interfaces`.
- Produces: audit JSON/Markdown summarizing all effective specs.

- [ ] 写 Markdown 优先、HTML回退、逐接口失败隔离和完整 manifest 的失败测试。
- [ ] 实现超时、有限重试、User-Agent、Markdown/HTML回退与错误明细。
- [ ] 保留现有 override/preset，官方字段整体替换种子字段。
- [ ] 将 `category_sort_order` 纳入种子、候选和正式排序。
- [ ] 增加命令行 `--publish`/`--published-by` 与审计工具。
- [ ] 运行全量规格静态测试。

### Task 3: 分类目录 API 与页面筛选

**Files:**
- Modify: `routes/admin_market_test_routes.py`
- Modify: `templates/admin/interface_tester.html`
- Modify: `tests/test_admin_market_test_routes.py`

**Interfaces:**
- Produces: `GET /admin/interface-tester/catalog.json?provider=&category=&q=` response with `providers`, `categories`, `items`.

- [ ] 写 Provider+category+q 交集、排序、计数和未分类兜底测试。
- [ ] 修改路由复用 `list_effective_specs(provider, category, keyword)`。
- [ ] 返回类目排序值、数量和 Provider 关联信息。
- [ ] 页面增加业务类目筛选，条件变化时刷新列表并保持当前选择。
- [ ] 运行路由和页面静态测试。

### Task 4: 移除输出字段选择并强制全字段

**Files:**
- Modify: `routes/admin_market_test_routes.py`
- Modify: `services/market_interface_spec_service.py`
- Modify: `services/admin_market_test_service.py`
- Modify: `services/admin_api_test_batch_service.py`
- Modify: `services/admin_api_test_repository.py`
- Modify: `templates/admin/interface_tester.html`
- Modify: `tests/test_interface_test_params.py`
- Modify: `tests/test_admin_market_test_service.py`
- Modify: `tests/test_admin_api_test_batch_service.py`
- Modify: `tests/test_admin_market_test_routes.py`

**Interfaces:**
- Produces: `MarketInterfaceSpecService.execution_output_fields(provider, api_name) -> list[str]`
- Changes: single/batch creation no longer accepts user-selected fields.

- [ ] 写客户端提交 `fields` 返回400的路由测试。
- [ ] 写执行服务始终使用14个 ETF字段和全部 expected fields 的测试。
- [ ] 从参数验证器中删除 `fields` 特例并明确拒绝未知参数。
- [ ] 批量任务创建时始终存储正式规格全部输出字段，仅供审计，不接受客户端覆盖。
- [ ] 页面把输出字段改为只读字段说明表，删除全选/全不选和复选框。
- [ ] 运行单接口、批量、重试和导出相关回归测试。

### Task 5: 持久化默认保留天数

**Files:**
- Modify: `services/admin_api_test_repository.py`
- Modify: `services/admin_api_test_batch_service.py`
- Modify: `routes/admin_market_test_routes.py`
- Modify: `templates/admin/interface_tester.html`
- Modify: `tests/test_admin_api_test_repository.py`
- Modify: `tests/test_admin_api_test_batch_service.py`
- Modify: `tests/test_admin_market_test_routes.py`

**Interfaces:**
- Produces: `get_default_retention_days(fallback: int) -> int`
- Produces: `set_default_retention_days(days: int, updated_by: str) -> dict`
- Produces: `GET /admin/interface-tester/settings.json`
- Produces: `POST /admin/interface-tester/settings/retention`

- [ ] 写初始化回退、持久化、范围校验和新批次继承测试。
- [ ] 建表并实现设置仓储方法。
- [ ] 批量服务在未显式指定时动态读取数据库默认值。
- [ ] 增加设置查询/修改路由和操作审计。
- [ ] 顶部卡片改为可编辑数字框和保存按钮。
- [ ] 运行保留策略及清理回归测试。

### Task 6: ETF 正式契约、综合回归和交付包

**Files:**
- Modify: `services/api_doc_catalog.py`（仅修正 ETF 目录展示元信息/种子回退）
- Create: `tests/test_etf_basic_official_contract.py`
- Create: `docs/INTERFACE_TESTER_OFFICIAL_SYNC_DEPLOYMENT.md`
- Create: `docs/INTERFACE_SPEC_AUDIT.md`

**Interfaces:**
- Produces: ETF契约测试：6输入、14输出、8000积分、5000条限制。

- [ ] 将官方 ETF Markdown fixture 生成候选并发布到临时规格目录，写精确契约测试。
- [ ] 修正目录中 ETF 的陈旧积分/说明，避免首次同步前展示错误。
- [ ] 运行目标测试、相关测试集和全量 pytest。
- [ ] 运行规格审计，记录140个接口分类/完整性/官方确认状态。
- [ ] 检查模板无输出字段复选控件，路由无客户端 fields 通道。
- [ ] 编写部署、全量同步、候选发布、回滚说明。
- [ ] 仅收集修改/新增文件，生成补丁清单和 ZIP。
