# 管理员客户端证书认证

## 1. 目标

管理员后台不依赖短信、邮箱验证码或第三方验证器应用。认证链路由项目自行管理，但不自创密码算法，而是使用标准 TLS、X.509、ECDSA P-256、SHA-256 和 PKCS#12。

生产后台登录同时要求：

1. 浏览器持有项目签发、已登记且未撤销的管理员客户端证书；
2. 管理员用户名和PBKDF2密码正确；
3. 图形验证码正确；
4. Redis登录失败限制未触发；
5. 可选管理员IP白名单通过。

客户端私钥只存在于管理员设备的证书存储中。SQLite只保存证书序列号、SHA-256指纹、有效期、设备名称和撤销状态。

## 2. 网络边界

必须使用独立管理员域名，例如：

- 公共API：`api.example.com`
- 管理后台：`admin-api.example.com`

公共域名明确拒绝 `/admin/`。管理员域名必须在可信反向代理的 TLS 握手阶段强制客户端证书：Nginx 使用 `ssl_verify_client on`；Caddy 使用 `client_auth { mode require_and_verify }`。没有受信任证书的请求不应进入管理员应用链路。

可信反向代理会覆盖以下请求头：

- `X-Admin-Proxy-Auth`
- `X-Admin-Client-Cert-Verify`
- `X-Admin-Client-Cert`（Nginx PEM兼容头）
- `X-Admin-Client-Cert-DER`（Caddy DER头）
- `X-Admin-Client-Cert-Fingerprint`
- `X-Admin-Client-Cert-Serial`
- `X-Admin-Client-Cert-Subject`

Flask不直接相信浏览器提交的头。它先校验随机代理共享密钥，再解析可信反向代理转发的完整证书（Nginx PEM 或 Caddy Base64 DER），重新计算SHA-256指纹和序列号，并与本地登记表比对。

### Caddy管理员站点头清理规则

公共Caddy站点可以并且应该使用 `header_up -X-Admin-*`，阻止任何外部伪造管理员头进入应用。管理员Caddy站点则不能在同一个 `reverse_proxy` 中先宽泛删除 `X-Admin-*`、再注入可信 `X-Admin-*`；实机回归已证明这种组合可导致应用收到 `proxy_auth_missing`。管理员站点应只删除旧 PEM 兼容头 `header_up -X-Admin-Client-Cert`，并用 `header_up <name> <value>` 显式覆盖 Proxy-Auth、Verify、DER、Fingerprint、Serial 和 Subject。Caddy 的“set”语义会覆盖客户端已有的同名值，因此这些可信字段仍由代理控制。

## 3. 证书生命周期

### 初始化私有CA

```bash
python -m tools.security.admin_client_certificate init-ca \
  --output-dir /etc/stock-server/admin-client-ca
```

CA私钥使用强密码加密。首次签发主证书和备用证书后，应把CA私钥离线备份，并从Web服务运行目录移走。Nginx只需要CA公钥证书：

```text
/etc/stock-server/admin-client-ca/admin-client-ca.crt.pem
```

### 签发设备证书

```bash
python -m tools.security.admin_client_certificate issue \
  --ca-dir /etc/stock-server/admin-client-ca \
  --output-dir /root/admin-client-certificates \
  --admin admin \
  --device office-main-pc
```

输出：

- `admin-office-main-pc.p12`：安装到管理员电脑；
- `admin-office-main-pc.crt.pem`：公开证书副本；
- 数据库登记记录。

至少签发两张：主电脑一张，备用可信设备一张。

### 查看登记

```bash
python -m tools.security.admin_client_certificate list
```

### 撤销

```bash
python -m tools.security.admin_client_certificate revoke \
  --fingerprint <SHA256指纹> \
  --reason "设备丢失"
```

撤销后，Nginx仍可能完成CA链验证，但Flask会在每个后台请求上查表并拒绝该证书，因此现有登录会话也立即失效。

## 4. 图形验证码

访问登录页时，浏览器自动请求 `/admin/captcha.png`，服务端生成5位数字及大小写字母图片。验证码具备：

- 5分钟过期；
- 每次验证后立即销毁；
- 刷新后旧验证码立即失效；
- 服务端Session只保存HMAC摘要，不保存明文；
- 图片禁止浏览器、代理和CDN缓存；
- 登录失败统一提示，避免泄露究竟是哪一项错误。

图形验证码只负责防自动化；真正的第二因素是设备中的客户端私钥。

## 5. 配置项

```env
ADMIN_CLIENT_CERT_REQUIRED=True
ADMIN_CLIENT_CERT_PROXY_SECRET=REPLACE-WITH-AT-LEAST-32-RANDOM-CHARS
ADMIN_CLIENT_CERT_ADMIN_HOST=admin-api.example.com
ADMIN_CLIENT_CERT_VERIFY_HEADER=X-Admin-Client-Cert-Verify
ADMIN_CLIENT_CERT_PEM_HEADER=X-Admin-Client-Cert
ADMIN_CLIENT_CERT_DER_HEADER=X-Admin-Client-Cert-DER
ADMIN_CLIENT_CERT_FINGERPRINT_HEADER=X-Admin-Client-Cert-Fingerprint
ADMIN_CLIENT_CERT_SERIAL_HEADER=X-Admin-Client-Cert-Serial
ADMIN_CLIENT_CERT_SUBJECT_HEADER=X-Admin-Client-Cert-Subject
ADMIN_CLIENT_CERT_PROXY_HEADER=X-Admin-Proxy-Auth
ADMIN_CAPTCHA_LENGTH=5
ADMIN_CAPTCHA_TTL_SECONDS=300
ADMIN_CAPTCHA_WIDTH=180
ADMIN_CAPTCHA_HEIGHT=58
```

`ADMIN_CLIENT_CERT_PROXY_SECRET`必须与当前可信反向代理（Nginx或Caddy）管理员站点中的 `X-Admin-Proxy-Auth` 值完全一致。

## 6. 故障排查

### 浏览器提示没有可用证书

确认 `.p12` 已安装到当前用户的“个人”证书存储，证书用途包含“客户端身份验证”，且证书没有过期。

### Nginx 400/495/496

检查：

- `ssl_client_certificate` 指向正确CA公钥证书；
- 浏览器证书由该CA签发；
- 证书有效期和系统时间；
- Nginx错误日志。

### Flask返回 certificate_unknown

TLS证书合法，但没有登记到当前数据库。必须使用项目签发命令，或确认生产服务连接的 `DB_FILE` 与签发命令使用的是同一数据库。

### certificate_revoked

证书已撤销。重新签发新设备证书，不要恢复旧记录状态。

### proxy_auth_missing

先确认运行中应用已加载非空 `ADMIN_CLIENT_CERT_PROXY_SECRET`，再确认反向代理管理员站点实际向上游发送 `X-Admin-Proxy-Auth`。使用Caddy时，如果Secret一致、`caddy validate`通过、客户端证书也能完成TLS握手，但页面仍返回 `proxy_auth_missing`，重点检查管理员 `reverse_proxy` 是否错误使用了 `header_up -X-Admin-*`。管理员站点应改为只删除 `header_up -X-Admin-Client-Cert`，随后显式覆盖所有可信管理员头，并在 `validate` 后执行受控 `reload`。

### proxy_auth_invalid

可信反向代理中的共享密钥与 `.env` 不一致，或请求绕过了可信代理。禁止对公网开放8898/8899端口。
