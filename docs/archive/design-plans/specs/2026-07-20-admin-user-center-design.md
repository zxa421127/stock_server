# 管理员用户编辑中心设计

## 目标

在现有管理员用户列表基础上增加独立用户详情/编辑中心，允许管理员安全修改手机号、邮箱、淘宝昵称、注册来源和账号状态；集中展示套餐、Token和用户历史；将普通用户与管理员的登录成功、登录失败和退出全部写入现有操作审计。

## 范围

- 新增 `/admin/users/<int:user_id>` 独立详情页。
- 用户名、用户ID、注册时间、更新时间、最近登录只读。
- 手机号、邮箱、淘宝昵称、注册来源可编辑。
- 注册来源使用 `self/admin/feishu/legacy_migration/other` 受控选项，已有未知值可原样保留。
- 账号状态只允许 `active/disabled`，禁用不改变Token和套餐记录。
- 保存本地资料后立即调用现有 `sync_single_user_to_feishu(user_id)`；同步失败不回滚本地修改，但必须提示并写审计。
- 详情页分区展示最近20条登录/退出记录和最近20条管理员操作记录。
- 登录审计覆盖普通用户和管理员：成功、失败、退出；存在用户名但密码错误的普通用户失败记录归入对应用户。
- 不记录密码；失败登录对外保持统一错误提示。
- 不修改数据库表结构、现有套餐、Token、`.env`或用户数据。

## 架构

### `routes/admin_user_routes.py`

独立蓝图，负责：管理员会话/IP保护、详情页渲染、资料更新、状态切换、详情页历史展示。复用现有管理员导航和审计服务。

### `services/admin_user_service.py`

负责：字段清洗、邮箱校验、手机号/邮箱查重、数据库事务更新、状态切换、详情数据聚合、飞书同步封装。路由只处理HTTP和页面反馈。

### 现有文件调整

- `routes/admin_member_routes.py`：用户列表增加“查看/编辑”链接；管理员登录/失败/退出审计；暴露共享后台页面/导航/会话辅助函数。
- `routes/user_routes.py`：普通用户登录成功、失败、禁用拒绝、退出和禁用会话拒绝审计。
- `routes/admin_audit_routes.py`：操作者类型增加 `anonymous`；支持详情页“查看全部”传入目标用户过滤。
- `services/audit_repository.py`：操作审计增加精确 `target_user_id` 过滤，同时保留原模糊 `target` 过滤。
- `app.py`：注册新管理员用户中心蓝图。

## 数据与安全

- 手机号：允许空，trim，最大64字符，非空唯一。
- 邮箱：允许空，trim后转小写，最大254字符，基本格式校验，非空按 `LOWER(email)` 唯一。
- 淘宝昵称：允许空，trim，最大128字符。
- 未知注册来源仅允许在提交值与当前原值完全相同时保留；否则必须选择受控值。
- 资料更新和状态切换采用参数化SQL和事务。
- 状态切换只更新 `users.status` 和 `updated_at`。
- POST使用会话CSRF令牌；管理员登录时生成，详情页表单携带并验证。
- 登录失败审计的 `request_data` 只包含账号输入和失败原因，不包含密码。
- 审计写入失败不得阻断登录、退出或资料保存。

## 审计事件

- `user.auth.login_success`
- `user.auth.login_failed`
- `user.auth.logout`
- `user.auth.session_rejected`
- `admin.auth.login_success`
- `admin.auth.login_failed`
- `admin.auth.logout`
- `admin.user_profile.update`
- `admin.user_status.disable`
- `admin.user_status.enable`
- `admin.user_profile.feishu_sync`

## UI

详情页包括：返回用户列表、基础资料表单、账号状态卡、安全与套餐摘要、登录/退出记录、管理员操作记录。列表原有套餐、重置密码等入口保持不变，并新增“查看/编辑”。

## 验收

1. 管理员可打开详情页并修改可编辑字段。
2. 重复手机号/邮箱、非法邮箱、超长字段被拒绝且不修改数据库。
3. 本地保存成功后触发飞书同步；失败时本地数据保留并显示警告。
4. 禁用后普通用户登录、既有会话和API Token访问均被拒绝；启用后Token和套餐记录未被改写。
5. 普通用户和管理员成功、失败登录与退出均进入操作历史。
6. 存在账号的密码错误记录归入该用户，未知账号归 `anonymous`。
7. 审计内容不包含密码。
8. 详情页两个历史分区各最多20条并可跳转全量筛选。
9. 全量测试零失败。
