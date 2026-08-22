[CmdletBinding()]
param(
    [string]$ProjectRoot = "C:\stockdata\stock_server",
    [ValidateSet("Nginx", "Caddy", "None")]
    [string]$ReverseProxyType = "Nginx",
    [string]$NginxRoot = "C:\stockdata\nginx",
    [string]$CaddyRoot = "C:\caddy",
    [string]$CaddyConfig = "C:\caddy\Caddyfile",
    [switch]$RunTests,
    [string]$TestSourceRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Python虚拟环境不存在：$python" }


function Get-CaddySiteBlock {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Host
    )

    $lines = $Text -split "`r?`n"
    $hostPattern = '^\s*' + [regex]::Escape($Host) + '\s*\{\s*$'
    $started = $false
    $depth = 0
    $buffer = New-Object System.Collections.Generic.List[string]

    foreach ($line in $lines) {
        if (-not $started) {
            if ($line -notmatch $hostPattern) { continue }
            $started = $true
        }

        $buffer.Add($line)
        $depth += ([regex]::Matches($line, '\{')).Count
        $depth -= ([regex]::Matches($line, '\}')).Count
        if ($started -and $depth -eq 0) {
            return ($buffer -join "`n")
        }
    }

    return ""
}

function Assert-CaddyAdminTrustedHeaders {
    param(
        [Parameter(Mandatory = $true)][string]$CaddyText,
        [Parameter(Mandatory = $true)][string]$AdminHost,
        [Parameter(Mandatory = $true)][string]$ExpectedProxySecret
    )

    if ([string]::IsNullOrWhiteSpace($AdminHost)) { throw "ADMIN_CLIENT_CERT_ADMIN_HOST为空，无法验证Caddy管理员站点" }
    if ([string]::IsNullOrWhiteSpace($ExpectedProxySecret)) { throw "ADMIN_CLIENT_CERT_PROXY_SECRET为空，无法验证Caddy管理员代理密钥" }

    $block = Get-CaddySiteBlock -Text $CaddyText -Host $AdminHost
    if ([string]::IsNullOrWhiteSpace($block)) { throw "Caddy配置中未找到管理员站点：$AdminHost" }

    if ($block -match 'header_up\s+-X-Admin-\*') {
        throw "管理员Caddy站点禁止使用 header_up -X-Admin-*；该宽泛删除会与后续可信X-Admin头注入冲突。公共API站点可继续使用。"
    }
    if ($block -notmatch 'header_up\s+-X-Admin-Client-Cert(?:\s|$)') {
        throw "管理员Caddy站点缺少旧PEM头清理：header_up -X-Admin-Client-Cert"
    }

    $requiredPatterns = @(
        'header_up\s+X-Admin-Client-Cert-Verify\s+"SUCCESS"',
        'header_up\s+X-Admin-Client-Cert-DER\s+"\{tls_client_certificate_der_base64\}"',
        'header_up\s+X-Admin-Client-Cert-Fingerprint\s+"\{tls_client_fingerprint\}"',
        'header_up\s+X-Admin-Client-Cert-Serial\s+"\{tls_client_serial\}"',
        'header_up\s+X-Admin-Client-Cert-Subject\s+"\{tls_client_subject\}"'
    )
    foreach ($pattern in $requiredPatterns) {
        if ($block -notmatch $pattern) { throw "管理员Caddy站点缺少必要可信证书头：$pattern" }
    }

    $secretPattern = 'header_up\s+X-Admin-Proxy-Auth\s+"' + [regex]::Escape($ExpectedProxySecret) + '"'
    if ($block -notmatch $secretPattern) {
        throw "Caddy管理员站点的X-Admin-Proxy-Auth与当前应用ADMIN_CLIENT_CERT_PROXY_SECRET不一致"
    }
}

Push-Location $ProjectRoot
try {
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "pip依赖检查失败" }
    & $python -c "import flask, redis, PIL, cryptography; print('核心依赖导入正常')"
    if ($LASTEXITCODE -ne 0) { throw "核心依赖导入失败" }
    & $python -m tools.db.check_schema
    if ($LASTEXITCODE -ne 0) { throw "数据库结构检查失败" }
    & $python -m tools.production_preflight
    if ($LASTEXITCODE -ne 0) { throw "生产预检失败" }
}
finally {
    Pop-Location
}

if ($RunTests) {
    $testRoot = if ($TestSourceRoot) { $TestSourceRoot } else { $ProjectRoot }
    $testsDir = Join-Path $testRoot "tests"
    if (-not (Test-Path $testsDir)) {
        throw "生产发布包通常不包含tests。请在完整源码目录运行测试，或通过-TestSourceRoot指定完整源码目录。"
    }
    $testPython = Join-Path $testRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $testPython)) { $testPython = $python }
    Push-Location $testRoot
    try {
        & $testPython -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "自动化测试失败" }
    }
    finally {
        Pop-Location
    }
}

switch ($ReverseProxyType) {
    "Nginx" {
        $nginxExe = Join-Path $NginxRoot "nginx.exe"
        if (Test-Path $nginxExe) {
            & $nginxExe -p (($NginxRoot -replace '\\', '/').TrimEnd('/') + '/') -t -c conf/nginx.conf
            if ($LASTEXITCODE -ne 0) { throw "Nginx配置检查失败" }
        }
        else {
            Write-Warning "未找到Nginx，跳过配置检查：$nginxExe"
        }
    }
    "Caddy" {
        $caddyExe = Join-Path $CaddyRoot "caddy.exe"
        if (-not (Test-Path $caddyExe)) { throw "Caddy可执行文件不存在：$caddyExe" }
        if (-not (Test-Path $CaddyConfig)) { throw "Caddy配置文件不存在：$CaddyConfig" }

        $caddyText = Get-Content -Raw -Encoding UTF8 $CaddyConfig
        if ($caddyText -match 'REPLACE_[A-Z0-9_]+') { throw "Caddy配置仍包含REPLACE_占位符" }

        & $caddyExe validate --config $CaddyConfig --adapter caddyfile
        if ($LASTEXITCODE -ne 0) { throw "Caddy配置检查失败" }

        $runtimeJson = (& $python -c "import json, config; print(json.dumps({'admin_host': str(config.ADMIN_CLIENT_CERT_ADMIN_HOST or ''), 'proxy_secret': str(config.ADMIN_CLIENT_CERT_PROXY_SECRET or '')}))") -join ""
        if ($LASTEXITCODE -ne 0) { throw "读取当前应用管理员代理配置失败" }
        $runtimeProxy = $runtimeJson | ConvertFrom-Json
        Assert-CaddyAdminTrustedHeaders `
            -CaddyText $caddyText `
            -AdminHost ([string]$runtimeProxy.admin_host) `
            -ExpectedProxySecret ([string]$runtimeProxy.proxy_secret)

        Write-Host "PASS：Caddy管理员mTLS可信头结构与代理密钥一致"
    }
    "None" {
        Write-Warning "已选择ReverseProxyType=None，跳过反向代理配置检查。"
    }
}

Write-Host "PASS：Windows生产验证完成"
