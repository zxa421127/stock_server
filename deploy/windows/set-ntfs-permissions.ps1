[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ProjectRoot = "C:\stockdata\stock_server",
    [string]$ServiceAccount = "StockServerSvc",
    [ValidateSet("Nginx", "Caddy", "None")]
    [string]$ReverseProxyType = "Nginx",
    [string]$NginxRoot = "C:\stockdata\nginx",
    [string]$CaddyConfig = "C:\caddy\Caddyfile",
    [string[]]$CaddyCaFiles = @(),
    [string]$CaddyServiceAccount = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$current = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $current.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "请使用管理员PowerShell运行本脚本"
}
if (-not (Get-LocalUser -Name $ServiceAccount -ErrorAction SilentlyContinue)) {
    throw "本地服务账号不存在：$ServiceAccount"
}
if (-not (Test-Path $ProjectRoot)) { throw "项目目录不存在：$ProjectRoot" }

$serviceIdentity = "$env:COMPUTERNAME\$ServiceAccount"
$administratorsSid = "*S-1-5-32-544"
$systemSid = "*S-1-5-18"

function Resolve-ProjectPath {
    param([Parameter(Mandatory = $true)][string]$PathValue)
    if ([IO.Path]::IsPathRooted($PathValue)) {
        return [IO.Path]::GetFullPath($PathValue)
    }
    return [IO.Path]::GetFullPath((Join-Path $ProjectRoot $PathValue))
}

function Resolve-AccountIdentity {
    param([Parameter(Mandatory = $true)][string]$AccountValue)
    $trimmed = $AccountValue.Trim()
    if ($trimmed.Contains("\")) { return $trimmed }
    return "$env:COMPUTERNAME\$trimmed"
}

if ($PSCmdlet.ShouldProcess($ProjectRoot, "设置项目根目录只读执行权限")) {
    & icacls $ProjectRoot /inheritance:r | Out-Host
    & icacls $ProjectRoot /grant:r `
        "${administratorsSid}:(OI)(CI)F" `
        "${systemSid}:(OI)(CI)F" `
        "${serviceIdentity}:(OI)(CI)RX" | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "项目根目录权限设置失败" }
}

$writeDirs = @(
    (Join-Path $ProjectRoot "data"),
    (Join-Path $ProjectRoot "logs"),
    (Join-Path $ProjectRoot "interface_specs")
)

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $python) {
    Push-Location $ProjectRoot
    try {
        $runtimeJson = & $python -c "import json, config; print(json.dumps({'DB_FILE': config.DB_FILE, 'AUDIT_SPOOL_DB_FILE': config.AUDIT_SPOOL_DB_FILE, 'AUDIT_EMERGENCY_DIR': str(config.AUDIT_EMERGENCY_DIR), 'FEISHU_SYNC_LOCK_FILE': config.FEISHU_SYNC_LOCK_FILE, 'LOG_DIR': str(config.LOG_DIR)}, ensure_ascii=False))"
        if ($LASTEXITCODE -ne 0) { throw "读取运行时路径失败" }
        $runtimePaths = $runtimeJson | ConvertFrom-Json
        $writeDirs += Split-Path -Parent (Resolve-ProjectPath ([string]$runtimePaths.DB_FILE))
        $writeDirs += Split-Path -Parent (Resolve-ProjectPath ([string]$runtimePaths.AUDIT_SPOOL_DB_FILE))
        $writeDirs += Resolve-ProjectPath ([string]$runtimePaths.AUDIT_EMERGENCY_DIR)
        $writeDirs += Split-Path -Parent (Resolve-ProjectPath ([string]$runtimePaths.FEISHU_SYNC_LOCK_FILE))
        $writeDirs += Resolve-ProjectPath ([string]$runtimePaths.LOG_DIR)
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Warning "未找到虚拟环境Python，只能设置默认data/logs/interface_specs目录权限。"
}

$writeDirs = $writeDirs | Where-Object { $_ } | Sort-Object -Unique
foreach ($path in $writeDirs) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    if ($PSCmdlet.ShouldProcess($path, "授予服务账号修改权限")) {
        & icacls $path /grant:r "${serviceIdentity}:(OI)(CI)M" | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "目录权限设置失败：$path" }
    }
}

$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
    & icacls $envFile /inheritance:r | Out-Host
    & icacls $envFile /grant:r `
        "${administratorsSid}:F" `
        "${systemSid}:F" `
        "${serviceIdentity}:R" | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ".env权限设置失败" }
}

$securityDir = Join-Path $ProjectRoot "security"
if (Test-Path $securityDir) {
    & icacls $securityDir /inheritance:r | Out-Host
    & icacls $securityDir /grant:r "${administratorsSid}:(OI)(CI)F" "${systemSid}:(OI)(CI)F" | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "security敏感目录权限设置失败" }
}

switch ($ReverseProxyType) {
    "Nginx" {
        $nginxCertDir = Join-Path $NginxRoot "certs"
        if (Test-Path $nginxCertDir) {
            & icacls $nginxCertDir /inheritance:r | Out-Host
            & icacls $nginxCertDir /grant:r `
                "${administratorsSid}:(OI)(CI)F" `
                "${systemSid}:(OI)(CI)F" `
                "${serviceIdentity}:(OI)(CI)R" | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "Nginx证书目录权限设置失败" }
        }
    }
    "Caddy" {
        if (-not $CaddyServiceAccount.Trim()) {
            Write-Warning "未提供CaddyServiceAccount，跳过Caddy文件权限设置；不会猜测现有Caddy进程账号。"
        }
        else {
            $caddyIdentity = Resolve-AccountIdentity $CaddyServiceAccount
            $caddyReadFiles = @($CaddyConfig) + @($CaddyCaFiles)
            $caddyReadFiles = $caddyReadFiles | Where-Object { $_ } | Sort-Object -Unique
            foreach ($filePath in $caddyReadFiles) {
                if (-not (Test-Path $filePath -PathType Leaf)) {
                    Write-Warning "Caddy只读文件不存在，跳过：$filePath"
                    continue
                }
                if ($PSCmdlet.ShouldProcess($filePath, "收紧Caddy敏感文件权限并授予运行账号读取权限")) {
                    & icacls $filePath /inheritance:r | Out-Host
                    if ($LASTEXITCODE -ne 0) { throw "Caddy文件继承权限移除失败：$filePath" }

                    $caddyGrantArgs = @(
                        "${administratorsSid}:F",
                        "${systemSid}:F"
                    )
                    if ($CaddyServiceAccount.Trim() -notmatch '^(NT AUTHORITY\\SYSTEM|SYSTEM)$') {
                        $caddyGrantArgs += "${caddyIdentity}:R"
                    }

                    & icacls $filePath /grant:r $caddyGrantArgs | Out-Host
                    if ($LASTEXITCODE -ne 0) { throw "Caddy文件权限设置失败：$filePath" }
                }
            }
        }
    }
    "None" {
        Write-Host "ReverseProxyType=None，未修改反向代理文件权限。"
    }
}

Write-Host "PASS：NTFS权限设置完成"
