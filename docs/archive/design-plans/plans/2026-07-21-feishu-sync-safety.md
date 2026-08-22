# 飞书同步安全收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 将会员同步改为本地权威的单向发布，并把飞书反向同步限制为仅导入新用户登记；竞价表继续单向写入。

**Architecture:** `services/feishu_sync_service.py`负责权威边界和数据流；`integrations/feishu/bitable.py`只按用户ID更新会员记录；`routes/admin_sync_routes.py`明确管理员接口只触发本地发布。新增专项测试用临时SQLite和假的Bitable对象验证不覆盖既有用户、不导入Token/套餐以及新用户回写。

**Tech Stack:** Python 3.12/3.13、Flask、SQLite、pytest/unittest、飞书 lark-oapi。

## Global Constraints

- 不需要数据库迁移。
- 不删除飞书现有字段，但必须清空并停止写入完整“授权码”。
- 保留现有公开函数名和路由路径。
- `sync_feishu_to_local()`不得修改既有用户、Token或订阅。
- 周期同步和`/api/admin/sync/feishu`只执行本地→飞书。
- 开盘啦竞价同步逻辑和39字段结构保持不变。

---

### Task 1: 会员发布去Token并只按用户ID upsert

**Files:**
- Modify: `services/feishu_sync_service.py`
- Modify: `integrations/feishu/bitable.py`
- Test: `tests/test_feishu_member_sync_safety.py`

**Interfaces:**
- Produces: `_build_feishu_member_fields(row, bitable) -> dict`
- Produces: `FeishuBitableManager.upsert_member_record(fields: dict, user_id) -> str`

- [x] 写失败测试：payload的“授权码”为空，返回值不再携带Token；upsert不调用Token查找。
- [x] 运行专项测试并确认因现有Token行为失败。
- [x] 修改payload构造和upsert签名，清空历史授权码，仅按用户ID匹配。
- [x] 更新所有调用点。
- [x] 运行专项测试和原有飞书字段测试。

### Task 2: 反向同步仅导入新登记用户

**Files:**
- Modify: `services/feishu_sync_service.py`
- Test: `tests/test_feishu_member_sync_safety.py`

**Interfaces:**
- Keeps: `sync_feishu_to_local() -> tuple[int, int]`
- Return meaning: `(added_users, linked_existing_users)`

- [x] 写失败测试：飞书修改既有用户的联系方式、状态、套餐、时间和授权码不得改变本地users/api_keys/subscriptions。
- [x] 写失败测试：新登记记录创建active普通用户、本地生成Token、不创建订阅并更新原飞书记录。
- [x] 写失败测试：唯一联系方式匹配只回写；重复联系方式冲突跳过。
- [x] 运行测试确认现有直接SQL覆盖行为失败。
- [x] 重写反向同步为登记导入流程，并增加唯一匹配辅助函数。
- [x] 运行专项测试确认通过。

### Task 3: 自动同步和管理员接口改为单向发布

**Files:**
- Modify: `services/feishu_sync_service.py`
- Modify: `routes/admin_sync_routes.py`
- Modify: `tests/test_admin_state_change_audit.py`
- Test: `tests/test_feishu_member_sync_safety.py`

**Interfaces:**
- Keeps: `run_full_sync()`，但行为为本地发布+竞价时间检查。
- Keeps: `trigger_sync_now()`。

- [x] 写失败测试：`run_full_sync()`不调用`sync_feishu_to_local()`，只调用`sync_local_to_feishu()`和竞价检查。
- [x] 写失败测试：管理员接口返回“已触发本地→飞书同步”。
- [x] 修改同步流程、日志和接口文案。
- [x] 运行专项测试及管理员审计测试。

### Task 4: 文档、回归和补丁打包

**Files:**
- Create: `README_飞书同步安全收口说明.md`
- Create: `修改文件清单.txt`
- Create: `SHA256SUMS.txt`

- [x] 写部署说明、行为变化、手工新用户导入命令、回滚步骤和测试命令。
- [x] 安装/使用项目测试依赖，运行飞书专项测试。
- [x] 运行全部测试，确认无回归。
- [x] 编译检查修改的Python文件。
- [x] 只打包修改文件，生成直接覆盖ZIP和SHA256。
