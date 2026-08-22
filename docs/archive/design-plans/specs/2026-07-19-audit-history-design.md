# 审计历史功能设计说明

**日期：** 2026-07-19  
**项目：** stock_server(30)  
**状态：** 用户已确认实施

## 1. 目标

在现有 Flask + Waitress + SQLite 股票数据服务中增加两套仅管理员可见的历史能力：

1. 操作历史：记录管理员和普通用户对业务状态产生影响的操作，成功与失败均记录。
2. 数据访问历史：记录全部 `/api` 与 `/api/...` 请求，包括已认证用户、匿名访问、缺失 Token、无效 Token、权限不足、限流和服务端异常。

历史记录必须支持筛选、分页、详情、脱敏展示和 CSV 导出，并按照环境变量设置自动清理。后台不提供手工删除入口。

## 2. 已确认的产品决策

- 采用独立审计模块，继续使用现有 `tokens.db` 保存审计主表。
- 新增独立 `audit_spool.db` 作为持久化缓冲；后台线程批量转存到主库。
- 操作历史默认保留 365 天；数据访问历史默认保留 30 天；配置为 `0` 时永久保留。
- 数据访问保存安全过滤后的请求参数，不保存响应正文。
- 密码、密码哈希、API Token 原文、Cookie、Authorization、私钥和外部平台密钥永不保存。
- 手机号、邮箱等敏感业务字段允许完整入库，但后台页面默认脱敏。
- 管理员查看完整敏感信息或导出完整 CSV 时，必须重新输入管理员密码；每次查看或完整导出本身也写入操作历史。
- 默认 CSV 脱敏；二次确认后可导出完整业务敏感字段；凭证类高敏感数据永远不导出。
- 后台不允许手工删除审计记录。
- 本期不记录管理员/用户登录、退出和登录失败。
- 数据访问历史记录全部 API 请求，HTML 页面访问不记录；HTML 页面产生的业务写操作进入操作历史。

## 3. 数据模型

### 3.1 `operation_audit_logs`

核心字段：

- `id`：自增主键
- `event_id`：唯一事件 ID
- `actor_type`：`admin`、`user`、`system`
- `actor_id`、`actor_name`
- `target_user_id`、`target_username`、`target_phone`、`target_email`
- `action_category`、`action_code`、`action_name`
- `request_method`、`request_path`
- `success`、`status_code`、`error_code`、`error_message`
- `before_data_json`、`after_data_json`、`request_data_json`
- `related_event_id`
- `client_ip`、`forwarded_for`、`user_agent`
- `created_at`

### 3.2 `api_access_logs`

核心字段：

- `id`、`event_id`、`request_id`
- `principal_type`：`user`、`admin`、`anonymous`
- `user_id`、`username_snapshot`、`phone_snapshot`、`email_snapshot`
- `auth_state`
- `token_fingerprint`
- `provider`、`api_name`
- `route_rule`、`request_path`、`request_method`
- `required_scope`、`package_code`
- `request_params_json`、`content_type`
- `status_code`、`success`、`duration_ms`
- `error_code`、`error_message`
- `client_ip`、`forwarded_for`、`user_agent`
- `created_at`

### 3.3 `audit_maintenance_state`

保存每日清理任务的最后开始、完成、租约、结果和删除数量，避免多个进程重复清理。

### 3.4 `audit_spool.db`

包含：

- `audit_spool_queue`：待落库事件、重试次数、下一次重试时间、最后错误。
- `audit_spool_dead_letters`：超过最大重试次数的事件。

所有主表和缓冲表均以 `event_id` 唯一约束防止重启补写产生重复记录。

## 4. 捕获方式

### 4.1 API 访问

在 Flask 应用注册全局钩子：

- `before_request`：仅对 `/api` 和 `/api/...` 初始化审计上下文，生成请求 ID、事件 ID、开始时间，并保存过滤后的参数。
- 鉴权中间件：只更新 `g` 中的用户、套餐、Scope 和鉴权状态，不再负责完整访问日志落库。
- `after_request`：统一生成访问事件并提交持久化缓冲。
- `teardown_request`：异常兜底，依靠 `event_id` 去重。

鉴权状态至少包括：`valid`、`admin_session`、`public_endpoint`、`missing_token`、`invalid_token`、`disabled_token`、`expired_subscription`、`insufficient_scope`、`rate_limited`、`internal_error`。

### 4.2 操作历史

首批接入：

- 用户注册成功与失败
- 用户修改密码成功与失败（如现有项目没有修改密码路由，则本次新增）
- 管理员重置用户密码成功与失败
- 首次开通套餐、续费、立即切换、到期后切换、取消待生效套餐的成功与失败
- 用户资料、账号状态、Token 状态变更（仅接入现有实际写操作）
- 管理员查看完整敏感信息
- 脱敏和完整 CSV 导出
- 清空缓存
- 触发飞书同步、竞价同步
- API 文档创建、编辑、删除和同步

所有密码操作仅保存 `password_changed=true` 等结果标记，不保存密码或哈希。

## 5. 安全过滤和脱敏

### 5.1 永久过滤字段

字段名大小写不敏感，包含以下关键词时替换为 `[REDACTED]`：

`password`、`old_password`、`new_password`、`confirm_password`、`token`、`api_token`、`x-api-token`、`authorization`、`cookie`、`session`、`secret`、`access_key`、`private_key`。

过滤支持嵌套字典、数组、查询参数、JSON 和表单。上传文件仅保存字段名、文件名和大小。

### 5.2 Token 指纹

使用服务器秘密值做 HMAC-SHA256。原始 Token 不进入主库、缓冲库、应急文件、应用日志、页面或 CSV。

### 5.3 页面脱敏

- 手机：保留前 3 位和后 4 位，中间使用 `*`。
- 邮箱：保留用户名开头部分和域名，中间使用 `*`。
- 其他文本：保留开头和结尾，中间使用 `*`。

## 6. 管理员页面

新增：

- `/admin/operation-history`
- `/admin/data-access-history`

两个页面均复用现有管理员 Session 和 IP 白名单；普通用户无法访问。

### 6.1 操作历史筛选

时间、操作代码、成功状态、操作者类型、操作者、目标用户、IP 和关键词；默认时间倒序，每页 50 条，可选 20/50/100/200。

### 6.2 数据访问历史筛选

时间、用户、数据源、接口名、路径、HTTP 方法、状态码、成功状态、鉴权状态、套餐、Scope、IP 和耗时范围。

### 6.3 详情和敏感信息

详情默认脱敏。管理员提交当前密码后，只返回指定记录和指定字段的完整值；刷新后恢复脱敏。二次验证成功与失败都写入操作历史。

### 6.4 CSV

两个页面均支持导出当前筛选结果：

- 脱敏 CSV：无需二次密码，但导出行为写入历史。
- 完整 CSV：POST 提交管理员密码，审计记录必须先持久化成功，否则返回 503。
- 最大行数默认 50,000；超过限制提示缩小筛选范围。
- 对以 `= + - @` 开头的字段进行 CSV 公式注入防护。

## 7. 持久化和故障策略

普通 API 请求：

1. 同步写入 `audit_spool.db`。
2. 失败时写入按日期滚动的应急 JSONL，并 `flush`、`fsync`。
3. 两者都失败时写 CRITICAL 日志，但不让股票数据 API 全部停摆。

敏感信息查看和完整 CSV：

- 必须先成功持久化审计事件，否则拒绝并返回 503。

套餐修改、密码重置等关键后台操作：

- 业务成功但审计主缓冲失败时写应急 JSONL，并在页面明确提示审计告警。

服务启动时恢复缓冲和应急 JSONL，按 `event_id` 去重。

## 8. 保留和清理

环境变量默认值：

```env
AUDIT_ENABLED=true
API_ACCESS_LOG_RETENTION_DAYS=30
OPERATION_LOG_RETENTION_DAYS=365
AUDIT_CLEANUP_INTERVAL_HOURS=24
AUDIT_SPOOL_DB_FILE=data/audit_spool.db
AUDIT_SPOOL_BATCH_SIZE=500
AUDIT_SPOOL_FLUSH_INTERVAL_SECONDS=1
AUDIT_SPOOL_MAX_RETRIES=10
AUDIT_SPOOL_SYNCHRONOUS=FULL
AUDIT_REQUEST_PARAMS_MAX_CHARS=12000
AUDIT_ERROR_MESSAGE_MAX_CHARS=2000
AUDIT_CSV_EXPORT_MAX_ROWS=50000
AUDIT_TOKEN_HMAC_SECRET=
```

后台每小时检查一次维护状态，但同一清理任务至少间隔 24 小时。每批最多删除 5,000 条。配置为 `0` 时跳过对应表。清理后执行 `PRAGMA optimize`，不自动执行阻塞性的 `VACUUM`。

## 9. 兼容性和非目标

- 保留原 `usage_logs` 和 `daily_usage_counters`，不迁移、不删除。
- 原有用量统计、积分、套餐、Scope 和限流逻辑必须保持。
- 不增加普通用户查看历史功能。
- 不增加超级管理员角色。
- 不保存响应正文。
- 不提供 Excel/PDF 导出。
- 不增加 Redis、Kafka 或外部日志平台依赖。
