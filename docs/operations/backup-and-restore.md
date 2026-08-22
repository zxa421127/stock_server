# 备份与恢复

- 使用SQLite在线备份API或短维护窗口复制数据库，不能只复制主文件而忽略正在写入的WAL状态。
- 备份 `.env` 应加密并与数据库分开保存。
- `interface_specs/current.json`、正式release目录和数据库必须保持同一发布时间点。
- 每月至少做一次恢复演练：恢复到隔离目录，执行 `PRAGMA quick_check`、`tools.production_preflight` 和核心E2E测试。
- 备份保留策略应包含日、周、月版本，并定期验证可读性。
