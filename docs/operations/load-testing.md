# 上线前压测

小目录接口的高RPS不能代表4000～5000行历史数据接口。应使用真实Token和真实大结果压测：

```bash
python -m tools.performance.load_test \
  --url https://api.example.com/api/v1/market/tushare/ci_daily \
  --tokens-file /secure/path/test-tokens.txt \
  --method POST \
  --json-payload '{"start_date":"20260101","end_date":"20260701"}' \
  --concurrency 30 \
  --seconds 60
```

观察p95/p99、5xx/429、服务器RSS、Redis、SQLite锁、Nginx出口和上游限流。10Mbps条件下应重点记录 `network_mbps`；如果接近带宽上限，增加带宽或减少单次返回量，而不是继续增加Gunicorn线程。
