# 股票数据 API 服务

Flask股票数据服务，统一接入TuShare、开盘啦和可选MiniQMT，包含会员套餐、API Token鉴权、接口文档、市场接口测试台、官方规格监控、审计和后台Worker。

## 生产架构

Linux/systemd生产环境推荐：Nginx HTTPS → Gunicorn（4 workers × 8 threads）→ SQLite(WAL，本地SSD) + Redis。Windows Server支持Waitress配合Nginx或Caddy，且同一台服务器的80/443只能由一套可信反向代理入口监听。接口测试、TuShare规格监控、API文档状态、飞书、开盘啦快照和审计清理使用独立Worker。

`MARKET_DATA_CACHE_MAX_ITEMS` 继续由环境变量控制，本项目不会在源码中替你固定生产值；应根据实际内存和缓存对象大小调整。

## 本地开发

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
python -m tools.db.migrate
python run_waitress.py
```

## 生产发布

不要直接压缩整个开发目录。使用白名单发布器：

```bash
python -m tools.release.build_production_package
python -m tools.security.scan_release_secrets dist/stock-server-production.zip
```

在服务器上使用全新的虚拟环境安装依赖，不上传本机 `.venv`。生产首次启动或升级前：

```bash
python -m tools.db.migrate
python -m tools.production_preflight
```

Linux/systemd部署安装 `deploy/nginx/stock-server.conf` 和 `deploy/systemd/*.service`。Windows Server按 `docs/operations/windows-production-installation.md` 选择Nginx或Caddy。两种架构都必须为独立管理员域名配置客户端证书校验。

## 安全要求

生产环境必须使用：

- 哈希管理员密码；
- 项目自签发的管理员客户端证书（mTLS）和图形验证码；
- Redis共享登录保护和API限流；
- 独立 `API_TOKEN_HASH_SECRET`，数据库不保存完整API Token；
- `APP_ENV=production`、安全Cookie和显式数据库迁移；
- 唯一可信反向代理公网入口（Nginx或Caddy），应用服务器只绑定回环地址；
- 状态变更POST及CSRF保护。

可用以下命令生成安全值，但不要把输出发送到聊天或提交到Git：

```bash
python -m tools.security.generate_production_secrets
```

## 测试目录

- `tests/`：单元、内部集成、安全回归和fixtures，不访问真实生产服务。
- `e2e_tests/`：对已部署服务器执行端到端验收。
- `scripts/manual_tests/`：需要人工确认、可能访问真实第三方服务的诊断脚本。

```bash
pytest -q tests
```

真实30并发大结果压测：

```bash
python -m tools.performance.load_test --help
```

## 文档

从 `docs/README.md` 开始。生产重点阅读：

- `docs/operations/production-deployment.md`
- `docs/security/production-security.md`
- `docs/operations/load-testing.md`
- `docs/operations/monitoring.md`
- `docs/architecture/project-layout.md`

Windows生产部署：`docs/operations/windows-production-installation.md`。
