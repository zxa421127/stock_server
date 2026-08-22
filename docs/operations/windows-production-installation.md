# Windows轻量服务器生产部署说明

适用架构：Windows Server、Waitress、Nginx或Caddy、Redis兼容服务、SQLite本地SSD。

## 关键原则

- 公网只开放80和443；
- Waitress只监听 `127.0.0.1:8899`；同机测试实例使用 `127.0.0.1:8898`；
- Redis只监听本机或可信内网；
- 同一台服务器的80/443只能由一个可信反向代理入口监听，不能同时启动Nginx和Caddy抢占端口；
- 公共域名拒绝所有 `/admin` 路径；
- 独立管理员域名强制客户端证书；
- 测试和生产必须使用不同项目目录、数据库、Redis逻辑库、管理员CA和代理密钥；
- 所有命令均在“管理员PowerShell”运行，不要在CMD中运行；
- `.env`、数据库、CA私钥、PFX和虚拟环境不得进入源码包。

## 推荐执行顺序

```powershell
Set-Location "C:\stockdata\stock_server"

# 创建或重新创建虚拟环境后安装依赖
PowerShell -ExecutionPolicy Bypass -File .\deploy\windows\install-dependencies.ps1

# 数据库迁移并检查Schema 5
& ".\.venv\Scripts\python.exe" -m tools.db.migrate
& ".\.venv\Scripts\python.exe" -m tools.db.check_schema

# 交互式生成生产密钥，管理员密码不会进入命令行历史
& ".\.venv\Scripts\python.exe" -m tools.security.generate_production_secrets

# 创建CA和签发设备证书；密码均通过隐藏提示输入
& ".\.venv\Scripts\python.exe" -m tools.security.admin_client_certificate init-ca
& ".\.venv\Scripts\python.exe" -m tools.security.admin_client_certificate issue --device main-pc
& ".\.venv\Scripts\python.exe" -m tools.security.admin_client_certificate issue --device backup-pc
```

完成以上步骤后，根据实际公网入口选择Nginx或Caddy分支。必须显式传入 `-ReverseProxyType`，不要依赖脚本默认值判断服务器当前使用哪一种代理。

## Nginx分支

Windows Nginx模板位于 `deploy/windows/nginx/stock-server.conf`。复制为Nginx的 `conf/nginx.conf` 后，替换域名、服务器证书路径、管理员客户端CA公钥路径和代理密钥。

```powershell
PowerShell -ExecutionPolicy Bypass -File .\deploy\windows\set-ntfs-permissions.ps1 `
  -ProjectRoot "C:\stockdata\stock_server" `
  -ServiceAccount "StockServerSvc" `
  -ReverseProxyType Nginx `
  -NginxRoot "C:\stockdata\nginx"

PowerShell -ExecutionPolicy Bypass -File .\deploy\windows\verify-production.ps1 `
  -ProjectRoot "C:\stockdata\stock_server" `
  -ReverseProxyType Nginx `
  -NginxRoot "C:\stockdata\nginx" `
  -RunTests
```

只有这台服务器确实由Stock Server脚本管理Nginx时，才注册Nginx计划任务：

```powershell
PowerShell -ExecutionPolicy Bypass -File .\deploy\windows\register-scheduled-tasks.ps1 `
  -ProjectRoot "C:\stockdata\stock_server" `
  -ServiceAccount "StockServerSvc" `
  -TaskPrefix "StockData" `
  -ReverseProxyType Nginx `
  -NginxRoot "C:\stockdata\nginx"
```

## Caddy分支

Caddy四域名合并片段位于 `deploy/windows/caddy/stock-server-four-hosts.Caddyfile`。该文件不是完整服务器配置，不能直接覆盖 `C:\caddy\Caddyfile`。合并时必须保留服务器已有的根域名站点块，并分别填写生产/测试管理员CA公钥路径和不同的代理密钥。

四域名配置必须保持以下安全边界：

- 公共 `api.lifesupermarket.cn` / `test-api.lifesupermarket.cn`：继续使用 `header_up -X-Admin-*`，并对 `/admin`、`/admin/*` 返回404；
- 管理员 `admin-api.lifesupermarket.cn` / `test-admin-api.lifesupermarket.cn`：**禁止**在注入可信管理员头的同一个 `reverse_proxy` 中使用 `header_up -X-Admin-*`；只删除旧 PEM 头 `header_up -X-Admin-Client-Cert`，随后由 Caddy 显式覆盖 `X-Admin-Proxy-Auth`、`X-Admin-Client-Cert-Verify`、DER、Fingerprint、Serial 和 Subject；
- 有效管理员P12必须能够经 mTLS 到达后台登录页；仅有代理共享密钥、没有可信证书信息时，应用必须继续返回403。

这条规则来自真实 Windows/Caddy 实机回归：管理员站点使用宽泛 `-X-Admin-*` 时可出现 `proxy_auth_missing`；改为仅删除旧 PEM 头并显式覆盖可信头后，合法证书可正常进入登录页，同时公共域 `/admin/*` 仍保持404。

当前腾讯云服务器实际使用：

```text
C:\caddy\caddy.exe
C:\caddy\Caddyfile
```

配置文件修改前必须备份，先执行 `caddy validate`，验证通过后才可在维护流程中执行平滑reload。

```powershell
$CaddyCaFiles = @(
  "C:\caddy\certs\prod\admin-client-ca.crt.pem"
  "C:\caddy\certs\test\admin-client-ca.crt.pem"
)

# 仅在已经确认Caddy实际运行账号时填写-CaddyServiceAccount。
PowerShell -ExecutionPolicy Bypass -File .\deploy\windows\set-ntfs-permissions.ps1 `
  -ProjectRoot "C:\stockdata\stock_server" `
  -ServiceAccount "StockServerSvc" `
  -ReverseProxyType Caddy `
  -CaddyConfig "C:\caddy\Caddyfile" `
  -CaddyCaFiles $CaddyCaFiles

PowerShell -ExecutionPolicy Bypass -File .\deploy\windows\verify-production.ps1 `
  -ProjectRoot "C:\stockdata\stock_server" `
  -ReverseProxyType Caddy `
  -CaddyRoot "C:\caddy" `
  -CaddyConfig "C:\caddy\Caddyfile" `
  -RunTests
```

当前Caddy已经由既有服务、计划任务或其他机制管理时，只注册Stock Server的Web和Worker任务，必须跳过代理任务，防止重复启动第二个Caddy：

```powershell
PowerShell -ExecutionPolicy Bypass -File .\deploy\windows\register-scheduled-tasks.ps1 `
  -ProjectRoot "C:\stockdata\stock_server" `
  -ServiceAccount "StockServerSvc" `
  -TaskPrefix "StockData" `
  -ReverseProxyType Caddy `
  -SkipReverseProxyTask
```

## 生产验证标准

无论使用Nginx还是Caddy，均须确认：

- `python -m tools.db.check_schema` 显示Schema 5并通过；
- `python -m tools.production_preflight` 通过；
- `verify-production.ps1` 对选定代理的配置验证通过；Caddy分支还必须通过管理员可信头结构与当前 `ADMIN_CLIENT_CERT_PROXY_SECRET` 一致性检查；
- 公共域名访问 `/admin` 和 `/admin/*` 返回404；
- 管理员域名在无有效客户端证书时由TLS/反向代理拒绝；
- 管理员域名在有效证书、正确Host和可信代理头条件下必须进入后台登录页，页面应显示当前登记的管理员证书设备；不得出现 `proxy_auth_missing`；
- 本机直连应用时，即使提供正确 `X-Admin-Proxy-Auth`，若没有可信证书验证信息仍应返回403（如 `certificate_not_verified`）；
- 8898、8899、6379和1025没有对公网开放；
- 完整测试以当前源码实际pytest输出为准，必须0 failed、0 error。

这些脚本不会自动重载正在运行的Nginx或Caddy。代理配置变更必须先备份、验证，再在维护步骤中单独执行reload。
