# 开盘啦三时点快照部署与验证

## 目标

每个交易日按上海时区保存三类互不覆盖的完整快照：

- `auction`：09:26:05
- `post_open`：09:31:00
- `close`：15:01:00

原始 JSON 和标准化 JSON 均压缩保存在 SQLite。数据库唯一索引、判重、快照 ID、任务租约和历史查询均包含 `snapshot_type`。

## 配置

```env
KAIPANLA_SNAPSHOT_ENABLED=true
KAIPANLA_SNAPSHOT_IN_PROCESS=true
KAIPANLA_AUCTION_SNAPSHOT_HOUR=9
KAIPANLA_AUCTION_SNAPSHOT_MINUTE=26
KAIPANLA_AUCTION_SNAPSHOT_SECOND=5
KAIPANLA_POST_OPEN_SNAPSHOT_HOUR=9
KAIPANLA_POST_OPEN_SNAPSHOT_MINUTE=31
KAIPANLA_POST_OPEN_SNAPSHOT_SECOND=0
KAIPANLA_CLOSE_SNAPSHOT_HOUR=15
KAIPANLA_CLOSE_SNAPSHOT_MINUTE=1
KAIPANLA_CLOSE_SNAPSHOT_SECOND=0
KAIPANLA_SNAPSHOT_WINDOW_SECONDS=120
KAIPANLA_SNAPSHOT_POLL_SECONDS=5
KAIPANLA_SNAPSHOT_PAGE_SIZE=1000
KAIPANLA_SNAPSHOT_MAX_PAGES=10
KAIPANLA_SNAPSHOT_LEASE_SECONDS=300
KAIPANLA_SNAPSHOT_RETENTION_DAYS=1095
```

单进程 Waitress 可使用进程内调度。多 Web worker 部署应设置 `KAIPANLA_SNAPSHOT_IN_PROCESS=false`，只启动一个独立 worker：

```bash
python -m tools.kaipanla_snapshot_worker
```

## 迁移

先只检查：

```powershell
python -m tools.db.migrate_kaipanla_dual_snapshot --db data\tokens.db --check-only
```

正式执行会先复制到临时数据库预演，再创建不可覆盖的在线备份，最后在事务中迁移：

```powershell
python -m tools.db.migrate_kaipanla_dual_snapshot --db data\tokens.db --report data\kaipanla_dual_snapshot_migration.json
```

旧记录自动设置为 `snapshot_type=auction`。重复执行安全；生产数据不删除。

## API

实时接口始终直接请求开盘啦：

```text
GET /api/v1/market/kaipanla/morning_bidding
```

历史接口：

```text
GET /api/v1/market/kaipanla/morning_bidding/history?trade_date=20260723&snapshot_type=auction
GET /api/v1/market/kaipanla/morning_bidding/history?trade_date=20260723&snapshot_type=post_open
GET /api/v1/market/kaipanla/morning_bidding/history?trade_date=20260723&snapshot_type=close
```

不传 `snapshot_type` 时默认 `auction`。非法值返回 400。指定 `post_open` 或 `close` 但不存在时返回 404，不会用 `auction` 或 Tushare 数据冒充命中。

## SQLite 检查

```powershell
python -c "import sqlite3; c=sqlite3.connect(r'data\tokens.db'); print(c.execute('select trade_date,snapshot_type,count(*) from kaipanla_bidding_snapshots group by trade_date,snapshot_type order by trade_date desc,snapshot_type').fetchall())"
```

验证同日三类快照 ID 和时间：

```powershell
python -c "import sqlite3; c=sqlite3.connect(r'data\tokens.db'); print(c.execute('select snapshot_id,trade_date,snapshot_type,snapshot_time,record_count,data_quality,schema_version from kaipanla_bidding_snapshots order by snapshot_time desc limit 10').fetchall())"
```

## 飞书多维表格

三类快照写入同一张竞价表。现有 `交易日期`、`快照时间`、`快照ID`、`快照类型` 字段可直接承载 `close`，无需新增列。若 `快照类型` 是单选字段，建议提前增加 `close` 选项。唯一键继续使用 `快照ID + 股票代码`，因此同一只股票每天保留三条记录。

建议建立三个视图：

- 集合竞价：`快照类型 = auction`
- 开盘后：`快照类型 = post_open`
- 收盘：`快照类型 = close`

按 `交易日期`、`股票代码`、`快照时间` 排序可连续比较同一股票的三个时点。
