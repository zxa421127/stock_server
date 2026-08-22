# 股票数据服务从0到1生产安装手册

## 1. 适用范围

本文以Ubuntu 24.04、4核8GB内存、10Mbps带宽、Nginx、Gunicorn、Redis和SQLite本地SSD为推荐生产环境。Windows可用于本地开发和验证，不建议把开发目录和Windows `.venv` 直接复制到Linux生产服务器。

## 2. 上线架构

```text
公网用户 -> api.example.com:443 -> Nginx -> Gunicorn 127.0.0.1:8899
管理员 -> admin-api.example.com:443 + 客户端证书 -> Nginx -> Gunicorn
后台Worker -> SQLite/Redis/TuShare/开盘啦/飞书
```

只开放80和443。Redis、SQLite和8899不得直接暴露公网。

## 3. 准备域名和DNS

创建两条A记录指向服务器公网IP：

```text
api.example.com
admin-api.example.com
```

管理员域名必须独立，公共域名不得暴露 `/admin/`。

## 4. 安装系统组件

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx redis-server unzip curl sqlite3 certbot python3-certbot-nginx
sudo systemctl enable --now nginx redis-server
```

创建运行用户和目录：

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin stockserver
sudo mkdir -p /opt/stock-server /etc/stock-server /var/lib/stock-server /var/log/stock-server
sudo chown -R stockserver:stockserver /opt/stock-server /var/lib/stock-server /var/log/stock-server
sudo chmod 750 /etc/stock-server
```

## 5. 构建干净生产包

在可信构建机的项目根目录执行：

```bash
python -m tools.release.build_production_package --output dist/stock-server-production.zip
python -m tools.security.scan_release_secrets dist/stock-server-production.zip
```

禁止上传整个开发目录。生产包中不得包含 `.env`、数据库、日志、测试、IDE配置或 `.venv`。

上传并解压：

```bash
sudo unzip stock-server-production.zip -d /opt/stock-server
sudo chown -R stockserver:stockserver /opt/stock-server
```

## 6. 创建Python环境

```bash
sudo -u stockserver python3 -m venv /opt/stock-server/.venv
sudo -u stockserver /opt/stock-server/.venv/bin/pip install --upgrade pip wheel
sudo -u stockserver /opt/stock-server/.venv/bin/pip install -r /opt/stock-server/requirements.txt
```

正式发布建议先在联网构建机生成并审核 `requirements.lock`，再用锁文件安装。

## 7. 创建生产密钥

生成管理员密码哈希和随机密钥：

```bash
cd /opt/stock-server
sudo -u stockserver .venv/bin/python -m tools.security.generate_production_secrets
```

把输出写入 `/etc/stock-server/stock-server.env`，同时配置第三方Token。示例：

```env
APP_ENV=production
SECRET_KEY=<随机值>
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=<PBKDF2哈希>
ADMIN_PASSWORD=
ADMIN_CLIENT_CERT_REQUIRED=True
ADMIN_CLIENT_CERT_PROXY_SECRET=<随机代理共享密钥>
ADMIN_CLIENT_CERT_ADMIN_HOST=admin-api.example.com
ADMIN_CAPTCHA_LENGTH=5
ADMIN_CAPTCHA_TTL_SECONDS=300
API_TOKEN_HASH_SECRET=<随机值>
AUDIT_TOKEN_HMAC_SECRET=<随机值>
SESSION_COOKIE_SECURE=True
ALLOW_INSECURE_DEFAULTS=False
SERVER_HOST=127.0.0.1
SERVER_PORT=8899
TRUST_PROXY_HEADERS=True
PROXY_FIX_X_FOR=1
PROXY_FIX_X_PROTO=1
PROXY_FIX_X_HOST=0
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_REQUIRED=True
DB_FILE=/var/lib/stock-server/tokens.db
LOG_DIR=/var/log/stock-server
DATA_DIR=/var/lib/stock-server
DB_AUTO_MIGRATE=False
REQUIRE_EXTERNAL_WORKERS=True
ADMIN_API_TEST_IN_PROCESS_WORKER=False
ENABLE_IN_PROCESS_FEISHU_WORKER=False
API_DOC_STATUS_IN_PROCESS=False
KAIPANLA_SNAPSHOT_IN_PROCESS=False
TUSHARE_SPEC_MONITOR_IN_PROCESS=False
TUSHARE_TOKEN=<你的Token>
KAIPANLA_TOKEN=<你的Token>
FEISHU_APP_ID=<你的App ID>
FEISHU_APP_SECRET=<你的App Secret>
```

设置权限：

```bash
sudo chown root:stockserver /etc/stock-server/stock-server.env
sudo chmod 640 /etc/stock-server/stock-server.env
```

## 8. 数据库迁移

```bash
sudo -u stockserver bash -c 'set -a; source /etc/stock-server/stock-server.env; set +a; cd /opt/stock-server; .venv/bin/python -m tools.db.migrate'
sudo -u stockserver bash -c 'set -a; source /etc/stock-server/stock-server.env; set +a; cd /opt/stock-server; .venv/bin/python -m tools.db.check_schema'
```

迁移后 schema 版本应为 5，并存在 `admin_client_certificates`、`contact_verification_challenges` 等安全相关表。

## 9. 创建管理员CA和设备证书

初始化CA：

```bash
sudo mkdir -p /etc/stock-server/admin-client-ca /root/admin-client-certificates
cd /opt/stock-server
sudo bash -c 'set -a; source /etc/stock-server/stock-server.env; set +a; .venv/bin/python -m tools.security.admin_client_certificate init-ca --output-dir /etc/stock-server/admin-client-ca'
```

签发主电脑证书：

```bash
sudo bash -c 'set -a; source /etc/stock-server/stock-server.env; set +a; cd /opt/stock-server; .venv/bin/python -m tools.security.admin_client_certificate issue --ca-dir /etc/stock-server/admin-client-ca --output-dir /root/admin-client-certificates --admin admin --device office-main-pc'
```

再签发一张备用证书：

```bash
sudo bash -c 'set -a; source /etc/stock-server/stock-server.env; set +a; cd /opt/stock-server; .venv/bin/python -m tools.security.admin_client_certificate issue --ca-dir /etc/stock-server/admin-client-ca --output-dir /root/admin-client-certificates --admin admin --device backup-pc'
```

把两个 `.p12` 分别安全传输到对应管理员设备。不要通过公开网盘、普通邮件或聊天工具发送PFX密码。

Windows安装：双击 `.p12`，选择“当前用户”，输入PFX密码，放入“个人”证书存储。Chrome和Edge使用Windows证书存储。Firefox可能需要在浏览器证书设置中单独导入。

CA私钥文件 `admin-client-ca.key.pem` 应加密离线备份；日常Web服务不需要读取它。Nginx只需要CA公钥证书。

## 10. 申请HTTPS证书

先使用不带mTLS的临时Nginx站点完成证书申请：

```bash
sudo certbot --nginx -d api.example.com -d admin-api.example.com
```

确认两个域名HTTPS证书有效后，再启用项目Nginx模板。

## 11. 配置Nginx

复制模板：

```bash
sudo cp /opt/stock-server/deploy/nginx/stock-server.conf /etc/nginx/sites-available/stock-server
sudo ln -s /etc/nginx/sites-available/stock-server /etc/nginx/sites-enabled/stock-server
```

编辑并替换：

- `api.example.com`
- `admin-api.example.com`
- Let’s Encrypt证书路径
- `/etc/stock-server/pki/admin-client-ca.crt.pem`
- `REPLACE_WITH_ADMIN_CLIENT_CERT_PROXY_SECRET`

复制CA公钥：

```bash
sudo mkdir -p /etc/stock-server/pki
sudo cp /etc/stock-server/admin-client-ca/admin-client-ca.crt.pem /etc/stock-server/pki/
sudo chmod 644 /etc/stock-server/pki/admin-client-ca.crt.pem
```

检查并重载：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

从未安装客户端证书的浏览器访问管理员域名应在TLS阶段失败；公共API域名访问 `/admin/login` 应返回404。

## 12. 安装systemd服务

检查 `deploy/systemd/*.service` 中的项目路径、用户和环境文件。复制后：

```bash
sudo cp /opt/stock-server/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stock-web.service
sudo systemctl enable --now stock-admin-api-test-worker.service
sudo systemctl enable --now stock-api-doc-status.service
sudo systemctl enable --now stock-audit-cleanup.service
sudo systemctl enable --now stock-feishu-worker.service
sudo systemctl enable --now stock-kaipanla-snapshot.service
sudo systemctl enable --now stock-tushare-spec-monitor.service
```

按实际业务配置决定是否启动飞书、开盘啦等可选Worker。

查看状态：

```bash
systemctl --no-pager --full status stock-web.service
journalctl -u stock-web.service -n 100 --no-pager
```

## 13. 生产预检

```bash
sudo -u stockserver bash -c 'set -a; source /etc/stock-server/stock-server.env; set +a; cd /opt/stock-server; .venv/bin/python -m tools.production_preflight'
```

必须满足：

- 配置检查通过；
- 数据库schema和完整性通过；
- 至少一张有效管理员证书；
- Redis PING通过；
- data、logs、interface_specs目录可写。

## 14. 首次管理员登录

使用已安装证书的设备访问：

```text
https://admin-api.example.com/admin/login
```

浏览器可能先弹出证书选择框。登录页会自动显示图形验证码。输入：

1. 管理员用户名；
2. 管理员密码；
3. 图片中的数字和大小写字母。

不再需要短信或第三方验证器App。

## 15. 安装140个接口文档

```bash
sudo -u stockserver bash -c 'set -a; source /etc/stock-server/stock-server.env; set +a; cd /opt/stock-server; .venv/bin/python -m tools.sync_full_api_docs'
```

目标：140个接口、12个类目、版本和指纹一致。

## 16. TuShare官方规格全量校准

```bash
sudo -u stockserver bash -c 'set -a; source /etc/stock-server/stock-server.env; set +a; cd /opt/stock-server; .venv/bin/python -X utf8 -m tools.sync_tushare_interface_specs > /tmp/tushare-scan.json'
```

必须达到：

```text
target_count=138
success_count=138
failure_count=0
complete_scan=true
```

不完整候选不得发布。登录后台“市场接口测试台 -> 规格变化”，审核完整候选、输入管理员密码发布，并等待发布后二次官网核验。

发布后：

```bash
python -m tools.sync_full_api_docs
python -m tools.audit_interface_specs --require-official-tushare --output docs/operations/tushare-production-audit.json
```

严格审计应为：

```text
tushare_pending_official=0
incomplete=0
missing_input_count=0
missing_output_count=0
catalog_seed_count=0
sample_description_count=0
forbidden_fields_input_count=0
```

## 17. 功能测试

内部测试：

```bash
.venv/bin/python -m pytest -q tests
```

端到端测试使用 `e2e_tests/`，测试账号和Token只能使用专门测试数据。

重点验收：

- 普通用户注册、登录、套餐和Token；
- 管理员证书、密码、图形验证码；
- 无证书设备无法访问后台；
- 撤销证书后立即失效；
- ETF、指数、财务等接口参数与官网一致；
- 输出字段全量返回；
- 接口测试结果下载；
- 默认保留天数修改和清理；
- 飞书、开盘啦和TuShare Worker；
- 审计日志和敏感信息脱敏。

## 18. 容量测试

使用真实4000至5000行结果执行30并发：

```bash
python -m tools.performance.load_test --base-url https://api.example.com --token-file /root/test-token.txt --concurrency 30
```

观察：

- CPU、RSS内存；
- Redis命中率；
- SQLite锁等待；
- 磁盘空间；
- 10Mbps出口带宽；
- 上游TuShare限流。

`MARKET_DATA_CACHE_MAX_ITEMS`继续由 `.env` 调整，本次认证改造不改变其默认值。

## 19. 备份

每天备份：

- SQLite数据库及WAL一致性快照；
- `interface_specs/current.json` 和当前release；
- `/etc/stock-server/stock-server.env` 加密备份；
- CA私钥离线备份；
- Nginx和systemd配置。

每月至少进行一次恢复演练。

## 20. 证书丢失和撤销

```bash
python -m tools.security.admin_client_certificate list
python -m tools.security.admin_client_certificate revoke --fingerprint <指纹> --reason "设备丢失"
```

撤销后测试该设备不能再访问后台。使用备用设备登录，再签发新证书。

## 21. 升级流程

1. 维护窗口停止Web和Worker；
2. 备份数据库、环境文件和接口规格；
3. 上传白名单生产包；
4. 新环境安装或升级依赖；
5. 执行数据库迁移；
6. 执行生产预检；
7. 启动Web和Worker；
8. 验证健康检查、后台证书登录、接口调用和日志；
9. 异常时回滚代码和数据库备份。

## 22. 不允许的做法

- 直接上传 `.env`、数据库或开发 `.venv` 到代码仓库；
- 对公网开放8899、6379或SQLite文件；
- 在公共API域名开启客户端证书请求；
- 把CA私钥放在Nginx可读取目录；
- 将PFX密码与PFX文件通过同一渠道发送；
- 发布138个接口未全部成功的候选；
- 绕过生产预检启动服务。
