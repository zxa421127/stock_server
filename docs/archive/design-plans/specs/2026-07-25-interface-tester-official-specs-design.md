# 市场接口测试台统一元数据与官方规格同步设计

**日期：** 2026-07-25  
**范围：** 管理员市场接口测试台、接口规格中心、批量测试、结果保留策略  
**基线：** 138 个 TuShare 接口 + 2 个 Kaipanla 接口

## 1. 目标

1. 测试台复用 API 文档管理中的业务类目，不再仅按 Provider 粗粒度筛选。
2. TuShare 接口的输入参数、输出参数、字段顺序、类型、必选性和说明均以官网文档为准。
3. 全部输出字段由后端规格中心决定，用户不能勾选或提交部分字段。
4. 支持一次性同步全部 TuShare 官网规格，先生成候选版本，通过完整性检查后再发布为正式版本。
5. 默认测试结果保留天数由管理员页面持久化修改，环境变量仅作为首次初始化默认值。
6. 保留现有单接口测试、批量测试、历史、规格变化和存储管理能力。

## 2. 权威数据源与同步策略

### 2.1 TuShare

每个现有接口已经保存 `official_doc_id`/`official_url`。同步器优先请求：

```text
https://tushare.pro/wctapi/documents/<doc_id>.md
```

该端点返回机器可读 Markdown，包含接口标题、接口名、描述、限量/权限文本、完整输入参数表和完整输出参数表。若 Markdown 请求失败，才回退到已有 HTML 页面解析。

同步结果写入候选版本，不直接覆盖正式规格。候选必须满足：

- 接口名与目录接口名一致；
- 输入参数表存在（官网确实无输入参数时允许空表，但必须记录官方已确认）；
- 输出参数表非空；
- 参数名不重复；
- 类型、必选/默认显示标记可解析；
- 138 个目标接口均有明确成功或失败结果；
- 失败接口列表和原因写入 manifest/audit report。

### 2.2 Kaipanla

两个 Kaipanla 接口继续以项目代码、请求模型和标准化响应映射为权威来源，不冒充 TuShare 官网规格。

## 3. 分类模型

正式规格保留：

```text
provider
category
category_sort_order
sort_order
```

目录 API 返回 Provider 列表、业务类目列表及数量。筛选条件为 `provider + category + q` 的交集。未分类接口归入“其他/未分类”。类目按 `category_sort_order` 排序，接口按 `sort_order` 排序。

## 4. 全字段执行模型

前端删除输出字段复选框、“全选”和“全不选”。输出字段以只读表格展示。

后端：

- `/interface-tester/run` 不接受 `fields`；检测到该字段返回 400，防止旧页面或手工请求绕过。
- 批量任务不保存客户端字段选择。
- 执行时从正式规格读取全部 `output_fields`，自动构造完整字段列表。
- Schema 报告始终将全部官方输出字段作为 expected fields。
- 结果和导出仍保存实际返回字段，同时明确报告缺失和新增字段。

## 5. 默认保留策略

新增持久化设置表：

```text
admin_api_test_settings(setting_key PRIMARY KEY, setting_value, updated_at, updated_by)
```

设置键：

```text
default_retention_days
```

读取顺序：数据库设置 > `ADMIN_API_TEST_RETENTION_DAYS` > 30。管理员可在 1–36500 天内修改。修改只影响之后创建的批次，不追溯改变已有批次；单批次保留天数和锁定能力继续保留。

## 6. ETF 基础信息验收基线

`tushare/etf_basic` 必须显示 6 个输入参数：

```text
ts_code, index_code, list_date, list_status, exchange, mgr
```

必须固定显示 14 个输出字段：

```text
ts_code, csname, extname, cname, index_code, index_name, setup_date,
list_date, list_status, exchange, mgr_name, custod_name, mgt_fee, etf_type
```

并显示官网当前的 8000 积分、单次最大 5000 条等说明。

## 7. 错误处理与安全

- 官网同步设置连接/读取超时、有限重试、逐接口错误隔离。
- 不记录或打包 Token、`.env`、数据库和真实返回数据。
- 同步失败不会破坏当前正式版本。
- 发布采用新版本目录 + 原子切换 `current.json`。
- 客户端传入 `fields` 明确拒绝。
- 管理员设置修改记录操作审计。

## 8. 测试

- Markdown 解析器单元测试，包括 ETF、长财务表、无输入接口、异常表格。
- 138 个目标接口的同步汇总/失败隔离测试（HTTP 使用 fixture/mock）。
- ETF 6/14 精确契约测试。
- 分类排序和组合筛选路由测试。
- 单接口、批量、失败重试全部使用全字段测试。
- `fields` 注入拒绝测试。
- 默认保留天数初始化、修改、刷新、重启持久化和新批次继承测试。
- 现有测试全量回归。

## 9. 交付

交付压缩包只包含修改或新增的源码、模板、测试、规格/审计工具和部署说明；不包含秘密、数据库、虚拟环境、日志或 IDE 文件。
