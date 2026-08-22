# Windows轻量服务器生产部署资源

本目录用于 Windows Server + Waitress + Nginx 或 Caddy 部署。两种反向代理均受支持，但同一台服务器的 80/443 只能由一套公网入口监听。

## 共同执行顺序

1. 用管理员 PowerShell 运行 `install-dependencies.ps1`；
2. 运行数据库迁移与结构检查；
3. 创建项目 CA 并签发至少两张管理员设备证书；
4. 运行 `create-service-account.ps1`，创建/复核 `StockServerSvc` 并确保它具备 `SeBatchLogonRight`，同时拒绝显式 `SeDenyBatchLogonRight`；
5. 配置选定的反向代理；
6. 运行 `set-ntfs-permissions.ps1`；
7. 运行 `verify-production.ps1`；
8. 最后按实际启动架构运行 `register-scheduled-tasks.ps1`。注册脚本会先检查批处理登录权限、要求现有服务账号密码隐藏输入两次并验证凭据。

## Nginx

把 `nginx/stock-server.conf` 复制为 Nginx 的 `conf/nginx.conf`，替换域名、证书路径和代理密钥。验证示例：

```powershell
.\deploy\windows\verify-production.ps1 `
  -ProjectRoot "C:\stockdata\stock_server" `
  -ReverseProxyType Nginx `
  -NginxRoot "C:\stockdata\nginx"
```

## Caddy

`caddy/stock-server-four-hosts.Caddyfile` 只是 Stock Server 四个域名的合并片段，不含根域名网站。保留现有 `lifesupermarket.cn` 和 `www.lifesupermarket.cn` 站点块，删除旧的单一 `api.lifesupermarket.cn` 站点块，再合并该片段并替换四个 `REPLACE_*` 占位值。

**管理员站点与公共站点的请求头清理规则不同。** 公共 `api` / `test-api` 站点继续使用 `header_up -X-Admin-*`，确保任何外部伪造的管理员头都不能进入应用；管理员 `admin-api` / `test-admin-api` 站点不得使用这一宽泛删除，因为同一 `reverse_proxy` 中还要由 Caddy 注入可信的 `X-Admin-Proxy-Auth`、证书 DER、指纹、序列号和 Subject。管理员站点只删除旧 PEM 兼容头 `X-Admin-Client-Cert`，其余可信头全部由 Caddy 使用 `header_up <name> <value>` 显式覆盖。

`verify-production.ps1 -ReverseProxyType Caddy` 会同时检查：Caddyfile 无 `REPLACE_` 占位符、管理员站点没有 `header_up -X-Admin-*`、存在 `header_up -X-Admin-Client-Cert`、可信证书头完整，并且当前应用的 `ADMIN_CLIENT_CERT_PROXY_SECRET` 与管理员站点中的 `X-Admin-Proxy-Auth` 完全一致。不要只以 `caddy validate` 通过作为 mTLS 上线依据。

Caddy 验证示例：

```powershell
.\deploy\windows\verify-production.ps1 `
  -ProjectRoot "C:\stockdata\stock_server" `
  -ReverseProxyType Caddy `
  -CaddyRoot "C:\caddy" `
  -CaddyConfig "C:\caddy\Caddyfile"
```

当前 Caddy 已经由其他服务或计划任务管理时，注册 Stock Server 的 Web/Worker 任务必须跳过代理任务，防止重复启动第二个 Caddy：

```powershell
.\deploy\windows\register-scheduled-tasks.ps1 `
  -ProjectRoot "C:\stockdata\stock_server" `
  -TaskPrefix "StockData" `
  -ReverseProxyType Caddy `
  -SkipReverseProxyTask
```

只有明确知道 Caddy 的运行账号时，才设置 Caddyfile 和管理员 CA 公钥的读取权限。脚本不会猜测运行账号，也不会修改 Caddy 根目录所有权。

这些脚本只检查或注册任务，不会自动重载正在运行的 Nginx 或 Caddy。`register-scheduled-tasks.ps1` 注册完成后会读取 Web 的实际状态：如果为 `Ready`，首次部署再显式启动并检查本地端口与 `/ping`；如果已经为 `Running`，不要再次执行 `Start-ScheduledTask`。尤其在覆盖了 Python/应用代码后，正在运行的旧进程不会自动重新加载磁盘新代码，应使用 `environment-switch\Switch-StockEnvironment.ps1 -RestartTarget` 做受控重启并确认新 PID、端口和严格 `/ping`。配置变更必须先备份、验证，并在维护步骤中单独执行重载。

所有脚本必须在 PowerShell 中运行，不要粘贴到 CMD。生产服务器公网只开放 80 和 443，8898、8899、6379 和 1025 不得开放。

## 生产/测试环境并行切换

腾讯云同机部署生产 `C:\stockdata\stock_server:8899` 与测试
`C:\stockdata\stock_server_test:8898` 时，使用
`environment-switch\Get-StockEnvironmentStatus.ps1` 和
`environment-switch\Switch-StockEnvironment.ps1`。两个脚本的 `-EnvironmentMap` 默认值会在参数绑定完成后再按脚本目录解析 `environment-map.psd1`，避免 Windows PowerShell 5.1 在 `param()` 默认表达式阶段 `$PSScriptRoot` 为空导致 `Join-Path` 失败。运行时 Web 身份不再错误要求 `Win32_Process.ExecutablePath` 必须等于 `.venv\Scripts\python.exe`；计划任务 Action 仍严格固定项目 `.venv`，同时通过 Task Principal、`Password` LogonType、监听 PID、`run_waitress.py` CommandLine、实际进程所有者 `StockServerSvc` 和严格 `/ping` 共同验收。两套任务分别使用
`StockData-*`、`StockDataTest-*`，注册时均使用 `-SkipReverseProxyTask`，
由唯一现有 Caddy 的四域名配置提供入口。详细步骤见
`docs\operations\production-test-environment-switch.md`。切换脚本不会修改或自动重载 Caddy。

### environment-switch 的 WhatIf 与进程所有者检查

`Switch-StockEnvironment.ps1 -WhatIf` 必须仍然执行只读的进程所有者查询；`Invoke-CimMethod GetOwner` 显式使用 `-WhatIf:$false`，避免 WhatIf 抑制只读查询后产生 `ReturnValue` 缺失误报。脚本同时校验 GetOwner 返回结构。`-RestartTarget -WhatIf` 会同时展示“停止”和“重新启动”的完整计划；正式执行前必须先让 WhatIf 通过。
