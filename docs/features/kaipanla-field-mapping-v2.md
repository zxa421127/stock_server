# 开盘啦早盘竞价字段映射（正式 v2）

## 1. Schema

- `schema_version` 固定为 `kaipanla_bidding.v2`。
- 正式快照类型仅允许 `auction`、`post_open`、`close`。
- 上游完整响应继续保存在压缩 `raw_payload` 中；公开 API、飞书和标准业务结果不返回数字下标字段。
- 缺失值保持为空；只有上游真实返回数值 `0` 时才输出 `0`。

## 2. 核心资金字段

| 上游数组位置 | 中文业务字段 | 英文字段 | 规则 |
|---|---|---|---|
| 6 | 竞价净额 | `auction_net_amount` | 与主力净额独立 |
| 10 | 竞价匹配额 | `auction_match_amount` | 数字下标不公开 |
| 13 | 主力净额 | `main_net_amount` | 数字下标不公开 |
| 14 | 主力买入 | `main_buy_amount` | 数字下标不公开 |
| 15 | 主力卖出额 | `main_sell_amount` | 取绝对值，公开值非负 |

内部可校验：`main_net_amount = main_buy_amount - main_sell_amount`。校验失败只写结构化日志，不给每行增加技术校验字段。

## 3. 最终公开字段

中文字段：

`股票代码、股票名称、当前价格、实时涨幅、竞价涨幅、涨停委买额、20分后涨停委买、竞价匹配额、竞价成交额、竞价净额、竞价换手、主力净额、主力买入、主力卖出额、实际流通、板块、行业、连板、连板高度`

标准英文字段：

`ts_code、name、trade_date、snapshot_type、snapshot_time、snapshot_id、auction_price、auction_pct、realtime_pct、limit_buy_amount、limit_buy_amount_after_0920、auction_net_amount、auction_match_amount、auction_amount、auction_turnover、main_net_amount、main_buy_amount、main_sell_amount、float_market_value、sector、limit_up_days、source_provider、source_api、data_quality、schema_version`

## 4. 连板规则

正式连板文字只采用开盘啦竞价主数据。`limit_up_days` 从该文字解析：

- `首板` → `1`
- `2连板` → `2`
- `4天3板` → `3`
- `9天7板` → `7`
- 无法可靠解析 → 空值

不再向外输出其他来源、冲突标记或补充接口字段。

## 5. 三时点快照

| 类型 | 上海时间 | 用途 |
|---|---:|---|
| `auction` | 09:26:05 | 正式集合竞价状态，用于历史、复盘、回测和审计 |
| `post_open` | 09:31:00 | 补充开盘后才出现的主力资金等数据，不回填或覆盖 `auction` |
| `close` | 15:01:00 | 保存收盘后约1分钟的价格、涨幅和主力资金状态，不覆盖前两类快照 |

唯一业务维度至少包含 `trade_date + snapshot_type + stock_code`。快照 ID 示例：

- `20260723_092605_auction_abcd1234`
- `20260723_093100_post_open_abcd1234`
- `20260723_150100_close_abcd1234`


`close` 中的竞价涨幅、竞价成交额、竞价匹配额等字段仍表示当天集合竞价指标；主力净额、主力买入、主力卖出额、当前价格和实时涨幅表示 15:01 采集时上游返回的状态。
