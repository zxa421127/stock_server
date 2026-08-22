# 管理员用户编辑中心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 建设独立管理员用户详情/编辑中心，并把普通用户和管理员登录、失败登录及退出纳入现有操作审计。

**Architecture:** 新增聚焦业务规则的 `services/admin_user_service.py` 和独立后台蓝图 `routes/admin_user_routes.py`。现有用户列表只增加入口，认证路由只接入审计和禁用会话检查，审计仓储增加精确目标用户过滤。

**Tech Stack:** Python 3、Flask 2.3、SQLite、现有飞书同步服务、pytest。

## Global Constraints

- 不修改数据库表结构、`.env`、现有用户、套餐或Token数据。
- 用户名只读；仅手机号、邮箱、淘宝昵称、注册来源和账号状态可编辑。
- 禁用账号不得修改Token和套餐状态。
- 飞书同步失败不得回滚本地资料。
- 所有登录失败记录不得包含密码。
- 采用TDD：每项生产行为先写失败测试并观察正确失败。

---

### Task 1: 用户资料业务服务

**Files:**
- Create: `services/admin_user_service.py`
- Test: `tests/test_admin_user_service.py`

**Interfaces:**
- Produces: `normalize_profile_input(current_user, payload) -> dict`
- Produces: `update_user_profile(user_id, payload) -> dict`
- Produces: `set_user_status(user_id, new_status) -> dict`
- Produces: `get_admin_user_detail(user_id) -> dict | None`
- Produces: `sync_user_profile_to_feishu(user_id) -> dict`

- [x] 写手机号、邮箱、淘宝昵称、注册来源清洗和校验失败测试。
- [x] 运行专项测试并确认因服务不存在而失败。
- [x] 实现最小字段校验。
- [x] 写手机号/邮箱重复、事务更新、状态仅改变 `users.status` 的失败测试。
- [x] 实现参数化SQL更新、查重和状态切换。
- [x] 写详情聚合与飞书同步成功/关闭/失败返回结构测试。
- [x] 实现详情聚合和同步封装。
- [x] 运行 `python -m pytest tests/test_admin_user_service.py -q`，预期全部通过。

### Task 2: 独立用户中心页面与接口

**Files:**
- Create: `routes/admin_user_routes.py`
- Modify: `app.py`
- Modify: `routes/admin_member_routes.py`
- Test: `tests/test_admin_user_center.py`

**Interfaces:**
- Consumes: Task 1服务函数。
- Produces: `admin_user_bp`，GET/POST `/admin/users/<int:user_id>`，POST `/admin/users/<int:user_id>/status`。

- [x] 写未登录重定向、详情页字段、历史分区和列表入口的失败测试。
- [x] 运行测试确认路由/链接不存在。
- [x] 实现蓝图、详情页、导航共享及蓝图注册。
- [x] 写CSRF、保存成功、校验错误、飞书同步警告和状态切换审计测试。
- [x] 实现POST处理、消息展示、二次确认和审计。
- [x] 运行 `python -m pytest tests/test_admin_user_center.py -q`，预期全部通过。

### Task 3: 普通用户认证审计与禁用会话

**Files:**
- Modify: `routes/user_routes.py`
- Test: `tests/test_auth_operation_audit.py`

**Interfaces:**
- Produces: 普通用户 `login_success/login_failed/logout/session_rejected` 操作审计。

- [x] 写成功登录、存在账号密码错误、未知账号失败、禁用登录、退出的失败测试。
- [x] 运行测试确认缺少审计事件。
- [x] 在不记录密码的前提下实现认证审计。
- [x] 写已登录用户被禁用后访问dashboard清除会话并记录 `session_rejected` 的失败测试。
- [x] 实现 `_current_user()` 的禁用会话拒绝和审计。
- [x] 运行认证专项测试，预期全部通过。

### Task 4: 管理员认证审计

**Files:**
- Modify: `routes/admin_member_routes.py`
- Test: `tests/test_auth_operation_audit.py`

**Interfaces:**
- Produces: 管理员 `login_success/login_failed/logout` 操作审计和登录后CSRF令牌。

- [x] 写管理员成功、失败登录和退出审计失败测试。
- [x] 运行并确认事件缺失。
- [x] 实现管理员认证审计，失败记录不含密码，退出前保留身份。
- [x] 登录成功时生成会话CSRF令牌。
- [x] 运行专项测试，预期全部通过。

### Task 5: 审计精确筛选与详情页历史

**Files:**
- Modify: `services/audit_repository.py`
- Modify: `routes/admin_audit_routes.py`
- Test: `tests/test_admin_audit_user_filter.py`

**Interfaces:**
- Produces: `target_user_id` 精确筛选；操作历史操作者类型含 `anonymous`。

- [x] 写精确目标用户筛选和anonymous下拉项失败测试。
- [x] 运行并确认筛选未生效。
- [x] 实现仓储过滤和路由参数接收。
- [x] 运行专项测试，预期全部通过。

### Task 6: 回归、说明与直接替换包

**Files:**
- Create: `README_管理员用户编辑中心说明.md`
- Create: `修改文件清单.txt`
- Create: `SHA256SUMS.txt`
- Package: `/mnt/data/stock_server_管理员用户编辑中心_直接替换包_20260720.zip`

- [x] 运行新增专项测试。
- [x] 运行原有后台、审计、鉴权和飞书相关测试。
- [x] 运行全量 `python -m pytest -q`，预期零失败。
- [x] 运行 `python -m compileall` 对所有修改Python文件做编译检查。
- [x] 在全新解压副本中覆盖补丁并再次运行专项测试。
- [x] 生成说明、文件清单、SHA-256并仅打包本次新增/修改文件。
