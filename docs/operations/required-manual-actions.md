# 上线前必须由运维人员完成的操作

以下事项涉及外部账号、服务器权限或第三方系统，程序无法代替管理员自动执行。

## 1. 立即轮换历史发布包中出现过的秘密

按“已泄露”处理并重新生成：

- Flask `SECRET_KEY`
- `ADMIN_PASSWORD_HASH` 对应的新管理员密码
- `ADMIN_CLIENT_CERT_PROXY_SECRET`
- `API_TOKEN_HASH_SECRET`
- `AUDIT_TOKEN_HMAC_SECRET`
- TuShare Token
- 开盘啦 Token、设备信息
- 飞书 App Secret
- 现存用户 API Token

生成本系统秘密：

```bash
python -m tools.security.generate_production_secrets
```

使所有用户旧 Token 失效：

```bash
python -m tools.security.revoke_all_api_tokens --confirm REVOKE-ALL
```

第三方 Token 必须到对应平台控制台撤销并重发。

## 2. 创建生产环境文件

将生产变量放在 `/etc/stock-server/stock-server.env`，权限设为 `600`。不要把 `.env` 放进代码目录、Git仓库或发布压缩包。

## 3. 生成并审查依赖锁文件

联网的可信构建机执行：

```bash
python -m tools.release.compile_requirements
python -m tools.security.audit_dependencies
```

本补丁不伪造无法在离线沙箱验证的依赖锁版本。生产部署必须使用生成并评审过的 `requirements.lock`。

## 4. 数据库迁移和备份

停止Web与全部Worker，备份数据库和 `interface_specs/current.json`，然后执行：

```bash
python -m tools.db.migrate
python -m tools.db.check_schema
python -m tools.production_preflight
```

`API_TOKEN_HASH_SECRET` 一旦用于迁移，不得随意更换；更换会使现有 Token 哈希无法匹配，需要全部轮换。

## 5. 创建管理员CA和客户端证书

迁移数据库后执行：

```bash
python -m tools.security.admin_client_certificate init-ca --output-dir /etc/stock-server/admin-client-ca
python -m tools.security.admin_client_certificate issue --ca-dir /etc/stock-server/admin-client-ca --output-dir /root/admin-client-certificates --admin admin --device main-pc
```

将 `.p12` 安装到管理员电脑；Nginx只需要CA公钥证书。CA私钥应加密、离线备份，并从Web服务运行目录移走。

## 6. 安装Nginx、Redis和systemd服务

按 `deploy/` 示例修改域名、证书、运行用户和项目路径。公网只开放Nginx的80/443端口，不得直接开放Gunicorn的8899端口。

## 7. 真实容量测试

使用真实4000～5000行接口数据执行：

```bash
python -m tools.performance.load_test \
  --base-url https://你的域名 \
  --token-file /安全路径/test-token.txt \
  --concurrency 30
```

观察CPU、RSS内存、Redis命中率、SQLite锁等待、磁盘和10Mbps出口带宽。`MARKET_DATA_CACHE_MAX_ITEMS` 保持环境变量可调，本补丁没有改其默认值。

## 8. 独立安全测试

自动化单元测试和发布包秘密扫描不能替代外部渗透测试。正式开放公网前，至少完成：

- 依赖漏洞扫描
- 动态Web扫描
- 管理员客户端证书、图形验证码、CSRF、越权和Token生命周期测试
- Nginx/TLS配置检查
- 备份恢复演练
- 由独立人员执行的渗透测试
