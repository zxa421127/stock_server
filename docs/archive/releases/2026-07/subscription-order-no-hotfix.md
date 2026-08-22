# 套餐操作订单号冲突修复

## 问题

Windows 的系统时钟可能在一个调度周期内连续返回相同的 `datetime.now()` 值。
旧实现只使用“时间戳 + user_id”生成 `manual_orders.order_no`，连续执行开通、续费或换套餐时可能生成相同订单号，触发：

```
sqlite3.IntegrityError: UNIQUE constraint failed: manual_orders.order_no
```

## 修复

内部订单号改为：

```
MANUAL_时间戳_用户ID_随机128位后缀
```

随机后缀由 `secrets.token_hex(8)` 生成，适用于快速连续操作和并发管理员提交。

同时改进两个测试文件的临时数据库清理：即使 `setUp()` 中途失败，也会先关闭 SQLite 连接再删除临时文件，避免 Windows 的 `WinError 32`。

## 替换文件

- `services/member_service.py`
- `tests/test_subscription_actions.py`
- `tests/test_feishu_subscription_fields.py`

## 验证

```
python -m unittest tests.test_subscription_actions tests.test_feishu_subscription_fields -v
python -m unittest discover -s tests -v
```

预期分别为：

- 9项通过
- 36项通过
