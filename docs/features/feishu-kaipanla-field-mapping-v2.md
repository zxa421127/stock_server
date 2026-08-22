# 飞书开盘啦竞价表字段（正式 v2）

## 最终字段清单

| 字段 | 推荐类型 | 代码来源 |
|---|---|---|
| 股票代码 | 文本 | 股票代码 / symbol |
| 股票名称 | 文本 | 股票名称 / name |
| 当前价格 | 数字 | auction_price |
| 实时涨幅 | 数字 | realtime_pct |
| 竞价涨幅 | 数字 | auction_pct |
| 涨停委买额 | 数字 | limit_buy_amount |
| 20分后涨停委买 | 数字 | limit_buy_amount_after_0920 |
| 竞价匹配额 | 数字 | auction_match_amount |
| 竞价成交额 | 数字 | auction_amount |
| 竞价净额 | 数字 | auction_net_amount |
| 竞价换手 | 数字 | auction_turnover |
| 主力净额 | 数字 | main_net_amount |
| 主力买入 | 数字 | main_buy_amount |
| 主力卖出额 | 数字 | main_sell_amount，非负 |
| 实际流通 | 数字 | float_market_value |
| 板块 | 文本 | sector |
| 行业 | 文本 | industry |
| 连板 | 文本 | 开盘啦主字段 |
| 连板高度 | 数字 | limit_up_days |
| 交易日期 | 文本 | trade_date |
| 快照时间 | 日期时间 | snapshot_time |
| 快照ID | 文本 | snapshot_id |
| 快照类型 | 文本或单选 | auction / post_open / close |
| 数据源 | 文本或单选 | source_provider |
| 数据质量 | 文本或单选 | data_quality |
| Schema版本 | 文本 | kaipanla_bidding.v2 |

## 改表与部署顺序

1. 暂停飞书同步服务，避免旧代码在改表期间重新建列。
2. 将旧列“竞价竞额”改名为“竞价净额”。
3. 新增“快照类型”列；建议先使用文本，确认稳定后可改为单选并配置 `auction`、`post_open`、`close`。
4. 核对上表保留字段及类型。
5. 删除已废弃的数字下标列、签名卖出列、技术校验列及其他连板来源列。
6. 覆盖本补丁代码并执行数据库迁移与字段检查。
7. 重启服务，再执行一次竞价同步验证。

新代码的自动建列只会创建最终字段，不会重新创建已删除列。

## 同步约束

- 同步只读取已经成功落库、`data_quality=complete`、`source_provider=kaipanla_snapshot` 的快照。
- 使用“快照ID + 股票代码”作为幂等键；一次读取现有索引后批量新增或更新，不逐行扫描整表。
- 三类快照可在同一交易日同时写入；同一股票每天保留 `auction`、`post_open`、`close` 三条记录。
- 缺失数字保持为空，不统一转为 `0`。
- 日期解析失败保持为空并写日志，不使用当前时间兜底。
- 全局进程锁阻止会员同步和竞价同步并发重复执行；锁冲突返回 `busy`。

## 三时点含义

| 快照类型 | 默认上海时间 | 说明 |
|---|---:|---|
| `auction` | 09:26:05 | 集合竞价结束附近 |
| `post_open` | 09:31:00 | 正式开盘约1分钟后 |
| `close` | 15:01:00 | 收盘后约1分钟；主力资金、当前价格和实时涨幅为该时点值 |

`close` 不覆盖早盘记录。飞书表无需增加新列；若“快照类型”为单选，请增加 `close` 选项。
