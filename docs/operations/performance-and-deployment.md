# 性能、限流与生产部署说明

## 1. 目标换算

```text
30 人 × 800 次/分钟 = 24,000 次/分钟 ≈ 400 次/秒
```

默认配置留有余量：

```env
DEFAULT_REQUESTS_PER_MINUTE=1000
MIN_REQUESTS_PER_MINUTE=800
GLOBAL_REQUESTS_PER_SECOND=600
SERVER_THREADS=64
```

## 2. 800 次/分钟如何保证

`services/rate_limit_service.py` 使用每用户固定分钟窗口：

- 普通套餐数据库值低于 800 时，实际仍按 800；
- 默认套餐写入 1000；
- 第 801 次或第 1001 次是否被拒绝取决于套餐配置；
- 每日额度另外判断；
- 管理员不受每用户分钟额度限制，但仍受全局服务器保护值影响。

Redis 模式通过 Lua 一次性检查和增加：

- 用户分钟计数；
- 用户每日计数；
- 全局每秒计数。

单进程模式使用线程锁和内存字典。

## 3. 缓存与上游保护

- 历史数据默认缓存 300 秒；
- 实时数据默认缓存 1 秒；
- 30 人同一秒请求相同参数时，多数请求直接返回同一份缓存；
- 同一进程发生相同 cache miss 时，通过 keyed lock 合并为一次上游调用；
- Redis 用于多 worker 共享响应缓存。

`download_history` 默认不缓存，因为它是有副作用的下载动作。

## 4. Windows 单机部署

适合当前约 100 日活规模：

```bash
python run_waitress.py
```

推荐：

```env
SERVER_THREADS=64
WAITRESS_CONNECTION_LIMIT=1000
REDIS_URL=
ENABLE_IN_PROCESS_FEISHU_WORKER=True
```

单个 Waitress 进程中，本地限流和 keyed lock 是一致的。Redis仍建议开启，以便进程重启后更平滑并为后续扩容做准备。

## 5. Linux 多 worker 部署

```env
REDIS_URL=redis://127.0.0.1:6379/0
ENABLE_IN_PROCESS_FEISHU_WORKER=False
```

启动 Web：

```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

飞书定时同步只启动一个：

```bash
python -m tools.feishu_worker
```

多 worker 不配置 Redis 时，每个进程会有独立分钟计数和独立缓存，因此不能准确实现全局每人 800/1000 次限额。

## 6. SQLite 适用边界

当前对 SQLite 做了：

- WAL；
- `synchronous=NORMAL`；
- busy timeout；
- 鉴权缓存；
- usage_logs 批量事务；
- API Key 最近使用时间节流更新；
- `daily_usage_counters` 精确汇总全部调用；
- `usage_logs` 成功明细默认抽样10%、失败明细全部保留。

这足以覆盖当前低用户数、读取为主的业务。若未来出现以下情况，迁移 PostgreSQL：

- 多台 Web 服务器；
- 会员/订单大量并发写入；
- usage_logs 必须保留每一条成功明细且持续数百条/秒；
- 需要复杂统计和长期海量日志。

## 7. 调用日志存储策略

默认：

```env
USAGE_LOG_SUCCESS_SAMPLE_RATE=0.10
USAGE_LOG_RETAIN_FAILURES=True
USAGE_LOG_RETENTION_DAYS=30
```

- 每日总量、成功量、失败量100%写入 `daily_usage_counters`；
- 详细成功请求约保留10%；
- 详细失败请求全部保留；
- 每日配额使用精确汇总，不受抽样影响；
- 清理旧明细：`python -m tools.db.cleanup_usage_logs`；
- 确实需要每条成功明细时可设为 `1.0`，但数据库增长和写入压力会显著增加。

## 8. 压测复现

准备 30 个 Token，每行一个，保存为 `tokens.txt`：

```bash
python -m tools.load_test \
  --url http://127.0.0.1:8899/api/v1/market/providers \
  --tokens-file tokens.txt \
  --concurrency 30 \
  --rps 400 \
  --seconds 60
```

先运行一次热身，再记录第二次结果。

## 9. 最终验证结果

在短暂热身后，最终归档代码完成：

```text
30并发，30个Token
目标：400次/秒，持续60秒
请求：24,000
成功：24,000
失败：0
实际开始速率：399.98次/秒
实际完成速率：399.63次/秒
平均延迟：22.00ms
p95：84.84ms
p99：103.63ms
HTTP 200：24,000
```

无429、无SQLite锁错误、无未处理异常。

## 10. 不能错误理解的地方

“服务器可接受约 400 次/秒”不等于：

- Tushare账号允许400次不同查询/秒；
- 中转服务器允许400次不同查询/秒；
- 开盘啦允许持续高频抓取；
- MiniQMT在任意硬件上都能返回400次不同的大批量历史查询/秒。

生产吞吐依靠热门请求缓存、相同请求合并和合理的批量参数。真实外部数据源的限额、网络、权限和稳定性需要单独测试。
