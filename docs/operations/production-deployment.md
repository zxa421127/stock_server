# 4核8G生产部署

目标场景：约1000日活、30人在线、10Mbps出口。推荐单机架构：

```text
Internet → Nginx:443 → Gunicorn 127.0.0.1:8899
                         ├─ 4 workers × 8 threads
                         ├─ SQLite(WAL，本地SSD)
                         └─ Redis(共享缓存/限流/登录保护)
独立systemd Worker：接口测试、规格监控、API文档状态、飞书、开盘啦、审计清理
```

## 首次部署

```bash
python3 -m venv /opt/stock-server/.venv
/opt/stock-server/.venv/bin/pip install --upgrade pip
/opt/stock-server/.venv/bin/pip install -r requirements.txt
python -m tools.security.generate_production_secrets
```

将环境变量保存到 `/etc/stock-server/stock-server.env`，权限设为 `600`，不要放入代码目录。

首次或升级数据库时，在停止Web和Worker后执行：

```bash
python -m tools.db.migrate
python -m tools.production_preflight
```

随后安装 `deploy/systemd/*.service` 和 `deploy/nginx/stock-server.conf`，按实际域名和证书路径修改。

## 启动顺序

1. Redis。
2. 数据库迁移与预检。
3. Web服务。
4. 所需独立Worker。
5. Nginx。
6. `/health/ready`、管理员登录、用户鉴权和真实大结果接口验收。

## 资源建议

- Gunicorn默认4×8，避免64线程同时进行DataFrame复制和JSON压缩。
- `MARKET_DATA_CACHE_MAX_ITEMS` 保持环境变量可调，本补丁不改变其默认值；上线后根据RSS、Redis命中率和对象大小调整。
- 10Mbps理论上限约1.25MB/s，大型JSON/CSV并发下载可能先打满带宽。
- SQLite必须放本地SSD，不能放NFS/SMB共享盘。
- 当持续出现写锁、多台Web实例或订单写入明显增加时迁移PostgreSQL。
