# 接口数量统一与测试加固设计

## 目标

1. 删除数据库中两条旧接口文档：`/api/data/stock/basic?list_status=L` 与 `/api/data/trade/cal?exchange=SSE&start_date=20260701&end_date=20260731`。
2. 所有页面、同步工具和测试统一通过集中统计函数自动计算接口文档数量，不再写死 139、140 或 142。
3. 自动目录数量由 `len(FULL_API_DOCS)` 得出；数据库统计区分自动文档、自定义文档、状态和权限类型。
4. 全接口测试在当日收盘前使用最近一个已完成工作日；分钟接口使用该交易日的完整时段；仅真实实时接口保留当前实时参数。
5. 飞书同步日志不输出 Token 原文或前缀，只输出不可逆短指纹。
6. `.env.example` 与补充配置说明默认开启开盘啦每日快照，真实 `.env` 不打入交付包。

## 数据库清理

`sync_full_api_docs()` 在同步前幂等删除两个精确旧路径，且只删除这两条。若其所属类目已无任何接口，则删除空类目。清理结果写入返回值和日志，重复执行不会影响其他自定义文档。

## 集中统计

`get_api_doc_statistics()` 返回：

- `document_count`
- `active_count`
- `non_active_count`
- `generated_count`
- `custom_count`
- `general_count`
- `special_count`
- `other_scope_count`
- `expected_generated_count`
- `installed_generated_count`
- 同步版本字段

自动文档通过两个受管路径前缀识别；权限分类与用户页面现有规则一致。管理员页面和用户页面都使用同一统计结果。

## 测试日期策略

`tools.interface_tester` 提供可注入当前时间的日期函数。上海时间在 15:30 之前时，最近完成工作日为前一工作日；15:30 之后使用当天（周末继续回退）。分钟接口使用最近完成工作日 09:00:00—15:30:00。实时接口名单不改为历史参数。

## 日志安全

飞书日志使用审计 HMAC 密钥对 Token 生成 12 位十六进制短指纹，日志字段名为 `token_fingerprint`。任何日志不得包含 Token 原文或其可识别前缀。

## 配置

`.env.example` 将 `KAIPANLA_SNAPSHOT_ENABLED` 默认示例改为 `true`，保留其他快照参数。另生成 `env_需要追加配置.txt`，供用户手工合并；交付包不包含真实 `.env`。

## 验收

- 旧数据库副本同步后总文档为 140，两条旧路径不存在。
- 自动目录数量由列表长度计算。
- 管理员与用户页面不含“完整139接口”或写死“完整收录140个接口”。
- 全量单元测试通过。
- 新增测试覆盖幂等清理、集中统计、日期边界、实时参数保持和Token日志脱敏。
- 完整项目包和直接替换包均通过 ZIP 完整性及 SHA-256 校验。
