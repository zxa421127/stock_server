# 开盘啦生产加固补丁 V3 替换说明

1. 备份当前项目目录和 SQLite 数据库。
2. 将本 ZIP 解压到 `stock_server` 项目根目录，保持目录结构并覆盖同名文件。
3. 不要用补丁内文件覆盖生产 `.env`；本补丁不包含 `.env`。
4. 安装依赖后运行：

```bash
python -m pytest
python -m compileall -q -x '(^|/)(\.venv|venv|__pycache__|\.pytest_cache)(/|$)' .
```

5. 飞书上线前先运行：

```bash
python tools/check_feishu_bidding_schema.py
python tools/check_feishu_bidding_schema.py --apply
```

6. 重启 Web 服务和独立快照/飞书 Worker。

新增环境变量：

```dotenv
FEISHU_BIDDING_AUTO_CREATE_FIELDS=true
FEISHU_BIDDING_ALLOW_TUSHARE_FALLBACK=false
```

默认行为是不把 Tushare partial 降级数据写入开盘啦飞书表。
