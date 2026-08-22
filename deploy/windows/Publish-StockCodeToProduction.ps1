[CmdletBinding()]
param(
    [string]$TestRoot = "C:\stockdata\stock_server_test",
    [string]$ProductionRoot = "C:\stockdata\stock_server",
    [string]$PackageRoot = "C:\stockdata\packages",
    [string]$BackupRoot = "C:\stockdata\backups",
    [string]$PipIndexUrl = "https://mirrors.cloud.tencent.com/pypi/simple/",
    [switch]$SkipFullPytest,
    [switch]$BootstrapProductionVenv,
    [switch]$SkipDependencyInstall,
    [switch]$KeepStage,
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host ("===== {0} =====" -f $Message)
}

function Assert-Administrator {
    $current = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $current.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "请使用管理员 PowerShell 运行本脚本。"
    }
}

function Get-FullNormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
}

function Assert-DifferentRoots {
    param([string]$Left, [string]$Right)
    $a = Get-FullNormalizedPath $Left
    $b = Get-FullNormalizedPath $Right
    if ($a.Equals($b, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "TestRoot 与 ProductionRoot 不能是同一个目录。"
    }
}

function Invoke-RobocopyChecked {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [string[]]$ExtraArguments = @()
    )
    & robocopy $Source $Destination @ExtraArguments
    $code = $LASTEXITCODE
    if ($code -ge 8) {
        throw "Robocopy 失败，退出码=$code；Source=$Source；Destination=$Destination"
    }
    return $code
}

function Assert-ProductionOffline {
    $listeners = @(Get-NetTCPConnection -LocalPort 8899 -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0) {
        $listeners | Select-Object LocalAddress, LocalPort, OwningProcess | Out-Host
        throw "Production 8899 正在监听。为避免在线覆盖代码，本脚本拒绝继续。"
    }

    $runningTasks = @(
        Get-ScheduledTask -TaskName "StockData-*" -ErrorAction SilentlyContinue |
            Where-Object { [string]$_.State -eq "Running" }
    )
    if ($runningTasks.Count -gt 0) {
        $runningTasks | Select-Object TaskName, State | Out-Host
        throw "存在 Running 的 StockData-* Production 任务。为避免在线覆盖代码，本脚本拒绝继续。"
    }

    Write-Host "PASS：Production 当前离线。"
}

function Assert-ZipSafe {
    param([Parameter(Mandatory = $true)][string]$ZipPath)

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $names = @($zip.Entries.FullName)
        $forbidden = @(
            $zip.Entries | Where-Object {
                $_.FullName -eq ".env" -or
                $_.FullName -like "*/.env" -or
                $_.FullName -match '(?i)\.(p12|pfx|key|pem)$' -or
                $_.FullName -match '(?i)(tokens\.db|audit_spool\.db|membership_test_tokens\.json)$'
            }
        )
        if ($forbidden.Count -gt 0) {
            $forbidden | Select-Object FullName | Out-Host
            throw "源码 ZIP 中发现禁止文件，停止发布。"
        }

        foreach ($required in @(
            "app.py",
            "config.py",
            "requirements.txt",
            "requirements-dev.txt",
            "SOURCE_MANIFEST.json",
            "SHA256SUMS.txt"
        )) {
            if ($names -notcontains $required) {
                throw "源码 ZIP 缺少关键文件：$required"
            }
        }
    }
    finally {
        $zip.Dispose()
    }

    Write-Host "PASS：源码 ZIP 安全检查通过。"
}

function Assert-SourceManifest {
    param([Parameter(Mandatory = $true)][string]$StageRoot)

    $manifestPath = Join-Path $StageRoot "SOURCE_MANIFEST.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "SOURCE_MANIFEST.json 不存在：$manifestPath"
    }

    $manifest = Get-Content -LiteralPath $manifestPath -Raw -ErrorAction Stop | ConvertFrom-Json
    $bad = @()

    foreach ($item in @($manifest.files)) {
        $relative = ([string]$item.path).Replace('/', '\')
        $file = Join-Path $StageRoot $relative
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            $bad += "MISSING $($item.path)"
            continue
        }
        $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
        $expected = ([string]$item.sha256).ToLowerInvariant()
        if ($actual -ne $expected) {
            $bad += "HASH $($item.path)"
        }
    }

    if ($bad.Count -gt 0) {
        $bad | Out-Host
        throw "SOURCE_MANIFEST 校验失败，停止发布。"
    }

    Write-Host ("PASS：SOURCE_MANIFEST 校验通过，文件数={0}" -f @($manifest.files).Count)
}

function Assert-ProtectedRuntimeAssets {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$ExpectedEnvHash,
        [hashtable]$ExpectedDirectoryPresence
    )

    $envPath = Join-Path $Root ".env"
    if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
        throw "Production .env 在发布后不存在，停止。"
    }
    $afterHash = (Get-FileHash -LiteralPath $envPath -Algorithm SHA256).Hash
    if ($afterHash -ne $ExpectedEnvHash) {
        throw "Production .env 在发布过程中发生变化，停止。"
    }

    foreach ($name in @("data", "logs", "security")) {
        if ($ExpectedDirectoryPresence.ContainsKey($name) -and $ExpectedDirectoryPresence[$name]) {
            $path = Join-Path $Root $name
            if (-not (Test-Path -LiteralPath $path -PathType Container)) {
                throw "Production 受保护目录在发布后丢失：$path"
            }
        }
    }

    Write-Host "PASS：Production .env 哈希未变化，data/logs/security 未被删除。"
}

Assert-Administrator
Assert-DifferentRoots -Left $TestRoot -Right $ProductionRoot

$TestRoot = Get-FullNormalizedPath $TestRoot
$ProductionRoot = Get-FullNormalizedPath $ProductionRoot
$PackageRoot = Get-FullNormalizedPath $PackageRoot
$BackupRoot = Get-FullNormalizedPath $BackupRoot

$testPython = Join-Path $TestRoot ".venv\Scripts\python.exe"
$prodPython = Join-Path $ProductionRoot ".venv\Scripts\python.exe"
$prodEnv = Join-Path $ProductionRoot ".env"

Write-Step "1/11 基础路径与 Production 离线门禁"
if (-not (Test-Path -LiteralPath $TestRoot -PathType Container)) { throw "TestRoot 不存在：$TestRoot" }
if (-not (Test-Path -LiteralPath $ProductionRoot -PathType Container)) { throw "ProductionRoot 不存在：$ProductionRoot" }
if (-not (Test-Path -LiteralPath $testPython -PathType Leaf)) { throw "测试虚拟环境 Python 不存在：$testPython" }
if (-not (Test-Path -LiteralPath $prodEnv -PathType Leaf)) {
    throw "Production .env 不存在：$prodEnv。脚本不会从 Test 复制 .env。"
}
Assert-ProductionOffline

Write-Step "2/11 测试槽环境门禁"
Push-Location $TestRoot
try {
    & $testPython -X utf8 -m tools.environment_preflight
    if ($LASTEXITCODE -ne 0) { throw "Test environment_preflight 失败，停止发布。" }

    # FIX3C_TEST_PLAN_GATE_V1
    & $testPython -B -X utf8 -m tools.db.verify_plan_catalog
    if ($LASTEXITCODE -ne 0) {
        throw "Test plan catalog gate failed. Publish stopped."
    }

    & $testPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Test pip check 失败，停止发布。" }
}
finally {
    Pop-Location
}

Write-Step "3/11 Test 完整 pytest"
if ($SkipFullPytest) {
    Write-Warning "已显式跳过完整 pytest。正式发布前不建议使用。"
}
else {
    Push-Location $TestRoot
    try {
        & $testPython -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "Test 完整 pytest 失败，停止发布。" }
    }
    finally {
        Pop-Location
    }
}

Write-Step "4/11 构建干净源码包"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Path $PackageRoot -Force | Out-Null
$zipPath = Join-Path $PackageRoot ("stock-server-source-{0}.zip" -f $stamp)

Push-Location $TestRoot
try {
    & $testPython -X utf8 -m tools.release.build_source_package --output $zipPath
    if ($LASTEXITCODE -ne 0) { throw "build_source_package 失败，停止发布。" }
}
finally {
    Pop-Location
}
$zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
Write-Host "源码包：$zipPath"
Write-Host "源码包 SHA256：$zipHash"

Write-Step "5/11 ZIP 安全检查 + SOURCE_MANIFEST 校验"
Assert-ZipSafe -ZipPath $zipPath
$stageRoot = Join-Path $PackageRoot ("stage-{0}" -f $stamp)
if (Test-Path -LiteralPath $stageRoot) { Remove-Item -LiteralPath $stageRoot -Recurse -Force }
New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null
Expand-Archive -LiteralPath $zipPath -DestinationPath $stageRoot -Force
Assert-SourceManifest -StageRoot $stageRoot

# FIX3C_STAGE_PLAN_GATE_V1
Write-Host ""
Write-Host "Checking staged catalog against Production DB in read-only mode..."

$previousPythonPath = [Environment]::GetEnvironmentVariable(
    "PYTHONPATH",
    "Process"
)

try {
    [Environment]::SetEnvironmentVariable(
        "PYTHONPATH",
        $stageRoot,
        "Process"
    )

    Push-Location $stageRoot

    try {
        & $testPython `
            -B `
            -X utf8 `
            -m tools.db.verify_plan_catalog `
            --project-root $ProductionRoot

        if ($LASTEXITCODE -ne 0) {
            throw "Stage catalog and Production DB differ. Production source has not been modified."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    [Environment]::SetEnvironmentVariable(
        "PYTHONPATH",
        $previousPythonPath,
        "Process"
    )
}

Write-Host "PASS: staged catalog matches Production DB; database access was read-only."

Write-Step "6/11 生成发布计划"
Write-Host "唯一代码源：$TestRoot"
Write-Host "Production：$ProductionRoot"
Write-Host "永不从 Test 发布/覆盖：.env、.venv、data、logs、security"
Write-Host "本脚本不会停止/启动/注册 Production 任务，不启动 8899，不修改/reload Caddy。"

if ($ValidateOnly) {
    Write-Host "VALIDATE-ONLY PASS：Production 未被修改。"
    if (-not $KeepStage) { Remove-Item -LiteralPath $stageRoot -Recurse -Force -ErrorAction SilentlyContinue }
    exit 0
}

Write-Step "7/11 记录受保护资产并备份旧 Production 代码"
$envHashBefore = (Get-FileHash -LiteralPath $prodEnv -Algorithm SHA256).Hash
$protectedPresence = @{}
foreach ($name in @("data", "logs", "security")) {
    $protectedPresence[$name] = Test-Path -LiteralPath (Join-Path $ProductionRoot $name) -PathType Container
}

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
$backupPath = Join-Path $BackupRoot ("prod-code-before-{0}" -f $stamp)
New-Item -ItemType Directory -Path $backupPath -Force | Out-Null

$backupArgs = @(
    "/E", "/R:2", "/W:2", "/NFL", "/NDL", "/NJH", "/NJS", "/NP",
    "/XD", (Join-Path $ProductionRoot ".venv"),
           (Join-Path $ProductionRoot "data"),
           (Join-Path $ProductionRoot "logs"),
           (Join-Path $ProductionRoot "security"),
    "/XF", (Join-Path $ProductionRoot ".env")
)
Invoke-RobocopyChecked -Source $ProductionRoot -Destination $backupPath -ExtraArguments $backupArgs | Out-Null
Write-Host "PASS：旧 Production 代码已备份：$backupPath"

Write-Step "8/11 同步干净源码到 Production"
$syncArgs = @(
    "/MIR", "/R:2", "/W:2", "/NFL", "/NDL", "/NJH", "/NJS", "/NP",
    "/XD", (Join-Path $ProductionRoot ".venv"),
           (Join-Path $ProductionRoot "data"),
           (Join-Path $ProductionRoot "logs"),
           (Join-Path $ProductionRoot "security"),
    "/XF", (Join-Path $ProductionRoot ".env")
)
Invoke-RobocopyChecked -Source $stageRoot -Destination $ProductionRoot -ExtraArguments $syncArgs | Out-Null

Assert-ProtectedRuntimeAssets `
    -Root $ProductionRoot `
    -ExpectedEnvHash $envHashBefore `
    -ExpectedDirectoryPresence $protectedPresence

Write-Step "9/11 Production 独立 .venv 与依赖"
if (-not (Test-Path -LiteralPath $prodPython -PathType Leaf)) {
    if (-not $BootstrapProductionVenv) {
        throw "Production .venv 不存在。源码已同步，但未创建虚拟环境。请重新运行并加 -BootstrapProductionVenv。旧代码备份：$backupPath"
    }

    $basePython = (& $testPython -c "import sys; print(sys._base_executable)").Trim()
    if ([string]::IsNullOrWhiteSpace($basePython) -or -not (Test-Path -LiteralPath $basePython -PathType Leaf)) {
        throw "无法解析系统 Python：$basePython"
    }

    & $basePython -m venv (Join-Path $ProductionRoot ".venv")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $prodPython -PathType Leaf)) {
        throw "创建 Production 独立 .venv 失败。"
    }
    Write-Host "PASS：已创建 Production 独立 .venv。"
}

if ($SkipDependencyInstall) {
    Write-Warning "已显式跳过 Production 依赖安装。"
}
else {
    & $prodPython -m pip install --upgrade pip setuptools wheel -i $PipIndexUrl
    if ($LASTEXITCODE -ne 0) { throw "Production pip 基础组件安装失败。" }

    & $prodPython -m pip install -r (Join-Path $ProductionRoot "requirements.txt") -i $PipIndexUrl
    if ($LASTEXITCODE -ne 0) { throw "Production requirements 安装失败。" }
}

& $prodPython -m pip check
if ($LASTEXITCODE -ne 0) { throw "Production pip check 失败。" }

Write-Step "10/11 Production 双预检"
Push-Location $ProductionRoot
try {
    & $prodPython -X utf8 -m tools.environment_preflight
    if ($LASTEXITCODE -ne 0) {
        throw "Production environment_preflight 失败。Production 保持离线；旧代码备份：$backupPath"
    }

    & $prodPython -X utf8 -m tools.production_preflight
    if ($LASTEXITCODE -ne 0) {
        throw "Production production_preflight 失败。Production 保持离线；旧代码备份：$backupPath"
    }
}
finally {
    Pop-Location
}

Write-Step "11/11 完成"
$report = [ordered]@{
    ok = $true
    timestamp = (Get-Date).ToString("s")
    test_root = $TestRoot
    production_root = $ProductionRoot
    source_zip = $zipPath
    source_zip_sha256 = $zipHash
    production_code_backup = $backupPath
    production_env_unchanged = $true
    production_started = $false
    caddy_modified = $false
}
$reportPath = Join-Path $PackageRoot ("publish-report-{0}.json" -f $stamp)
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding UTF8

Write-Host "PUBLISH PASS"
Write-Host "源码已同步到 Production，但 Production 仍保持离线。"
Write-Host "旧代码备份：$backupPath"
Write-Host "发布报告：$reportPath"
Write-Host "下一步：NTFS / 计划任务 / DPL-06 最终运行时验收。"

if (-not $KeepStage) {
    Remove-Item -LiteralPath $stageRoot -Recurse -Force -ErrorAction SilentlyContinue
}
