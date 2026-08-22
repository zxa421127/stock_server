# 生产安全基线

## 强制条件

生产环境必须设置：

```env
APP_ENV=production
SESSION_COOKIE_SECURE=True
ALLOW_INSECURE_DEFAULTS=False
SERVER_HOST=127.0.0.1
TRUST_PROXY_HEADERS=True
PROXY_FIX_X_FOR=1
PROXY_FIX_X_PROTO=1
REDIS_REQUIRED=True
DB_AUTO_MIGRATE=False
REQUIRE_EXTERNAL_WORKERS=True
ADMIN_CLIENT_CERT_REQUIRED=True
ADMIN_CLIENT_CERT_PROXY_SECRET=REPLACE-WITH-AT-LEAST-32-RANDOM-CHARS
ADMIN_CLIENT_CERT_ADMIN_HOST=admin-api.example.com
```

必须通过 `tools/security/generate_production_secrets.py` 生成并安全保存：

- `SECRET_KEY`
- `ADMIN_PASSWORD_HASH`
- `ADMIN_CLIENT_CERT_PROXY_SECRET`
- `API_TOKEN_HASH_SECRET`
- `AUDIT_TOKEN_HMAC_SECRET`

生产环境禁止配置明文 `ADMIN_PASSWORD`。Web服务启动前会执行生产就绪检查；Redis、数据库版本、客户端证书登记或密钥不符合要求时拒绝启动。

## 管理后台

- 管理员密码仅使用自适应PBKDF2哈希验证。
- 管理员登录必须同时通过密码、图形验证码和项目签发的mTLS客户端证书。
- 敏感查看、删除和规格发布需要再次输入管理员密码，并继续绑定当前有效客户端证书。
- 登录失败计数存入Redis，多个Gunicorn Worker共享，Redis故障时生产环境失败关闭。
- 所有状态变更使用POST/PUT/PATCH/DELETE并受CSRF保护，GET不得删除、同步或发布。
- 管理后台使用独立域名；公共API域名不得暴露 `/admin/`。建议同时使用VPN或固定管理IP白名单。

## 用户和API Token

- 新用户密码至少12位；新密码使用600,000轮PBKDF2-SHA256，旧哈希仍兼容验证。
- API Token完整值只在创建或轮换时显示一次。
- 数据库只保存HMAC-SHA256摘要、前缀和后4位；迁移时旧明文会被清除。
- 轮换后旧Token立即失效。

## 网络边界

- 只向公网开放Nginx 443。
- Gunicorn绑定 `127.0.0.1:8899`，防火墙不得直接开放。
- `ProxyFix`只信任一层Nginx；代理层数与实际部署不一致时必须修改配置。
- Nginx和应用双层限制登录、注册、找回密码和API请求。

## 浏览器安全

应用设置HSTS、CSP nonce、禁止iframe、nosniff、严格Referrer-Policy、Permissions-Policy和跨源隔离头。页面事件统一使用外部辅助脚本或 `addEventListener`，CSP明确设置 `script-src-attr 'none'`，不允许HTML内联事件属性。

## 发布包

只能用 `python -m tools.release.build_production_package` 生成白名单包，并在上传前运行：

```bash
python -m tools.security.scan_release_secrets dist/stock-server-production.zip
```

生产包不得包含 `.env`、数据库、日志、虚拟环境、IDE文件、测试Token或抓包数据。
