# 套餐续费与换套餐升级说明

## 1. 本次新增的四种管理员操作

| action_type | 后台名称 | 行为 |
|---|---|---|
| `open` | 首次开通 | 用户没有当前套餐和待生效套餐时，立即创建套餐 |
| `renew` | 续费当前套餐 | 只能选择当前相同套餐，直接延长当前订阅到期时间；待生效队列同步后移 |
| `switch_now` | 立即换套餐 | 当前套餐改为 `replaced`，新套餐立即生效；可选择取消或顺延待生效队列 |
| `switch_scheduled` | 到期后换套餐 | 当前套餐不变，新套餐以 `scheduled` 状态排在全部权益之后 |

管理员后台路径不变：

- `/admin/members`：套餐操作表单
- `/admin/members/list`：会员列表、当前套餐、待生效套餐、取消待生效套餐

## 2. 数据库自动变更

应用启动时 `init_db()` 会自动新增字段并迁移旧数据；也可以先手动运行：

```cmd
python -m tools.db.migrate_subscription_actions
```

### subscriptions 新增字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `operation_type` | TEXT | `open/renew/switch_now/switch_scheduled/feishu_sync` |
| `previous_subscription_id` | INTEGER | 换套餐前订阅ID |
| `extra_days` | INTEGER | 管理员补偿天数 |
| `ended_at` | TEXT | 实际结束时间 |
| `ended_reason` | TEXT | `expired/switch_now/admin_cancel_scheduled` 等 |

状态统一为：

- `active`：当前生效
- `scheduled`：等待生效
- `expired`：正常到期
- `replaced`：被立即换套餐替换
- `cancelled`：管理员取消
- `disabled`：被禁用

### manual_orders 新增字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `operation_type` | TEXT | 操作类型 |
| `subscription_id` | INTEGER | 本次操作对应订阅ID |
| `previous_subscription_id` | INTEGER | 原订阅ID |
| `previous_plan_code` | TEXT | 原套餐代码 |
| `effective_time` | TEXT | 本次操作实际生效时间 |
| `extra_days` | INTEGER | 补偿天数 |
| `operator_name` | TEXT | 后台操作管理员 |

旧数据库中：

- `start_time` 在未来但状态为 `active` 的记录会改为 `scheduled`；
- 已经过期的 `active/scheduled` 记录会改为 `expired`；
- 不删除旧订单和旧订阅。

## 3. 飞书会员表需要新增的字段

为避免在字段尚未创建时破坏现有飞书同步，新代码默认：

```env
FEISHU_EXTENDED_MEMBER_FIELDS_ENABLED=False
```

先在飞书会员多维表格中新增下面 **6个字段**，名称必须完全一致：

| 字段名称 | 推荐字段类型 | 用途 | 是否允许从飞书反向控制套餐 |
|---|---|---|---|
| `待生效套餐代码` | 单行文本 | 例如 `realtime_month` | 否，只展示 |
| `待生效套餐类型` | 单行文本或单选 | `history/realtime/admin` | 否，只展示 |
| `待生效开始时间` | 日期（包含时间） | 预约套餐生效时间 | 否，只展示 |
| `待生效截止时间` | 日期（包含时间） | 预约套餐到期时间 | 否，只展示 |
| `最近操作类型` | 单选或单行文本 | 首次开通/续费当前套餐/立即换套餐/到期后换套餐/飞书同步 | 否，只展示 |
| `额外补偿天数` | 数字（整数） | 最近一次管理员操作补偿天数 | 否，只展示 |

字段建好后，在 `.env` 修改：

```env
FEISHU_EXTENDED_MEMBER_FIELDS_ENABLED=True
```

重启服务，然后执行一次本地到飞书同步。

### 现有字段含义不变

- `套餐代码/套餐类型/开始授权时间/授权截止时间`：只表示**当前生效套餐**；
- 新增的 `待生效...` 字段：表示**下一条等待生效的套餐**；
- `状态`：表示账号/Token/当前套餐的总体可用状态；
- `来源订单号`：当前套餐来源订单号。

### 重要安全规则

本版本不把飞书新增的6个字段当作套餐操作指令。续费、立即换套餐、到期后换套餐必须在管理员网页执行，避免定时双向同步重复续费或误切套餐。

飞书 → 本地仍可维护当前账号资料、Token、当前套餐和状态，但不会读取“待生效套餐”字段创建队列。

## 4. 替换与升级步骤（Windows CMD）

1. 停止 `python run_waitress.py`。
2. 备份 `.env` 和数据库。
3. 将补丁压缩包内容覆盖到项目根目录。
4. 运行：

```cmd
cd /d C:\stockdata\stock_server
call .venv\Scripts\activate.bat
python -m tools.db.migrate_subscription_actions
python -m unittest tests.test_subscription_actions -v
python run_waitress.py
```

5. 登录 `/admin/members` 检查四种操作。
6. 飞书6个字段全部创建后再开启 `FEISHU_EXTENDED_MEMBER_FIELDS_ENABLED=True`。

## 5. 行为验证

- 首次开通：创建1条 `active` 订阅；
- 续费：订阅ID不变，只延长 `expire_time`，新增1条 `manual_orders` 审计记录；
- 立即换套餐：旧订阅变 `replaced`，新订阅变 `active`；
- 到期后换套餐：当前订阅继续 `active`，新订阅为 `scheduled`；
- 取消待生效套餐：目标订阅变 `cancelled`；
- 权限缓存：操作成功后立即清理该用户全部Token的鉴权缓存。

## 6. 本次需要覆盖的文件

### 修改文件

- `.env.example`：增加飞书扩展字段开关示例；
- `config.py`：读取 `FEISHU_EXTENDED_MEMBER_FIELDS_ENABLED`；
- `db_utils.py`：新增字段迁移、状态迁移、当前/待生效查询、套餐操作历史查询；
- `services/member_service.py`：新增四种套餐操作和取消待生效套餐；
- `services/auth_context_cache.py`：套餐变更后按用户清理全部Token缓存；
- `routes/admin_member_routes.py`：管理员选择操作类型、补偿天数、立即换套餐确认、取消待生效套餐；
- `routes/user_routes.py`：用户中心显示当前套餐、待生效套餐、最近套餐操作；
- `services/feishu_sync_service.py`：飞书当前套餐和待生效套餐分开同步。

### 新增文件

- `tools/db/migrate_subscription_actions.py`：手动迁移和检查数据库；
- `tests/test_subscription_actions.py`：续费和换套餐测试；
- `tests/test_feishu_subscription_fields.py`：飞书扩展字段映射测试；
- `scripts/windows/upgrade_subscription_actions.bat`：Windows CMD数据库迁移入口；
- `scripts/windows/run_subscription_action_tests.bat`：Windows CMD测试入口；
- `docs/features/subscription-actions.md`：本说明。

本次不删除原有业务文件，也不修改 Tushare、开盘啦、MiniQMT 数据接口路径。
