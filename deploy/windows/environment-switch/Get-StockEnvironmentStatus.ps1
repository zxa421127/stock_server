[CmdletBinding()]
param(
    [string]$EnvironmentMap = "",
    [string]$ServiceAccount = "StockServerSvc",
    [string]$CaddyExe = "C:\caddy\caddy.exe",
    [string]$CaddyConfig = "C:\caddy\Caddyfile",
    [switch]$FailOnError
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Resolve the default map only after parameter binding. This avoids an empty
# $PSScriptRoot default-expression failure on Windows PowerShell 5.1.
$resolvedScriptRoot = [string]$PSScriptRoot
if ([string]::IsNullOrWhiteSpace($resolvedScriptRoot)) {
    $invocationPath = [string]$MyInvocation.MyCommand.Path
    if ([string]::IsNullOrWhiteSpace($invocationPath)) {
        throw "无法解析 environment-switch 脚本目录；请显式传入 -EnvironmentMap"
    }
    $resolvedScriptRoot = Split-Path -Parent $invocationPath
}
if ([string]::IsNullOrWhiteSpace($EnvironmentMap)) {
    $EnvironmentMap = Join-Path -Path $resolvedScriptRoot -ChildPath "environment-map.psd1"
}
if (-not (Test-Path -LiteralPath $EnvironmentMap)) {
    throw "环境映射文件不存在：$EnvironmentMap"
}
$EnvironmentMap = (Resolve-Path -LiteralPath $EnvironmentMap -ErrorAction Stop).Path

$TaskArguments = [ordered]@{
    Web                       = "-X utf8 run_waitress.py"
    AdminApiTestWorker        = "-X utf8 -m tools.admin_api_test_worker"
    ApiDocStatusWorker        = "-X utf8 -m tools.api_doc_status_worker"
    AuditCleanupWorker        = "-X utf8 -m tools.audit_cleanup_worker"
    FeishuWorker              = "-X utf8 -m tools.feishu_worker"
    KaipanlaSnapshotWorker    = "-X utf8 -m tools.kaipanla_snapshot_worker"
    TushareSpecMonitorWorker  = "-X utf8 -m tools.tushare_spec_monitor_worker"
}

$map = Import-PowerShellDataFile -Path $EnvironmentMap

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
}

function Test-PathEquals {
    param([string]$Left, [string]$Right)
    if ([string]::IsNullOrWhiteSpace($Left) -or [string]::IsNullOrWhiteSpace($Right)) { return $false }
    return (Get-NormalizedPath $Left).Equals(
        (Get-NormalizedPath $Right),
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Test-LocalServiceAccountIdentity {
    param([string]$Identity)
    if ([string]::IsNullOrWhiteSpace($Identity) -or [string]::IsNullOrWhiteSpace($ServiceAccount)) {
        return $false
    }
    $value = $Identity.Trim()
    $domain = ""
    $user = $value
    $separatorIndex = $value.IndexOf("\", [System.StringComparison]::Ordinal)
    if ($separatorIndex -ge 0) {
        $domain = $value.Substring(0, $separatorIndex)
        $user = $value.Substring($separatorIndex + 1)
    }
    if (-not $user.Equals($ServiceAccount, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    if ([string]::IsNullOrWhiteSpace($domain) -or $domain -eq ".") {
        return $true
    }
    return $domain.Equals([string]$env:COMPUTERNAME, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-ProcessOwnerIdentity {
    param([Parameter(Mandatory = $true)][object]$Process)

    # GetOwner is a read-only CIM query. Invoke-CimMethod honors the script-level
    # -WhatIf preference, so explicitly disable WhatIf for this read-only call;
    # otherwise -WhatIf suppresses the query and no MethodResult is returned.
    $owner = Invoke-CimMethod `
        -InputObject $Process `
        -MethodName GetOwner `
        -ErrorAction Stop `
        -WhatIf:$false

    if ($null -eq $owner) {
        throw "无法读取进程 PID=$($Process.ProcessId) 所有者：GetOwner 未返回结果"
    }

    $returnValueProperty = $owner.PSObject.Properties["ReturnValue"]
    $userProperty = $owner.PSObject.Properties["User"]
    $domainProperty = $owner.PSObject.Properties["Domain"]
    if ($null -eq $returnValueProperty -or $null -eq $userProperty) {
        throw "无法读取进程 PID=$($Process.ProcessId) 所有者：GetOwner 返回结构异常"
    }

    $returnValue = [int]$returnValueProperty.Value
    $user = [string]$userProperty.Value
    $domain = if ($null -eq $domainProperty) { "" } else { [string]$domainProperty.Value }
    if ($returnValue -ne 0 -or [string]::IsNullOrWhiteSpace($user)) {
        throw "无法读取进程 PID=$($Process.ProcessId) 所有者，ReturnValue=$returnValue"
    }
    if ([string]::IsNullOrWhiteSpace($domain)) {
        return $user
    }
    return "$domain\$user"
}
function Assert-TaskPrincipal {
    param([Parameter(Mandatory = $true)][object]$Task)
    $userId = [string]$Task.Principal.UserId
    if (-not (Test-LocalServiceAccountIdentity $userId)) {
        throw "计划任务 $($Task.TaskName) 运行账号错误：$userId；期望本机 $ServiceAccount"
    }
    $logonType = [string]$Task.Principal.LogonType
    if (-not $logonType.Equals("Password", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "计划任务 $($Task.TaskName) LogonType 错误：$logonType；期望 Password"
    }
    return $userId
}

function Test-CaddyState {
    try {
        if (-not (Test-Path $CaddyExe)) { throw "Caddy 不存在：$CaddyExe" }
        if (-not (Test-Path $CaddyConfig)) { throw "Caddyfile 不存在：$CaddyConfig" }
        $processes = @(Get-CimInstance Win32_Process -Filter "Name='caddy.exe'")
        if ($processes.Count -ne 1) { throw "Caddy 进程数量=$($processes.Count)，期望=1" }
        $process = $processes[0]
        if (-not (Test-PathEquals ([string]$process.ExecutablePath) $CaddyExe)) {
            throw "Caddy 可执行路径错误：$($process.ExecutablePath)"
        }
        $commandLine = [string]$process.CommandLine
        if ($commandLine.IndexOf("--config", [System.StringComparison]::OrdinalIgnoreCase) -lt 0 -or
            $commandLine.IndexOf((Get-NormalizedPath $CaddyConfig), [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
            throw "运行中的 Caddy 未使用 $CaddyConfig"
        }
        & $CaddyExe validate --config $CaddyConfig --adapter caddyfile | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Caddyfile validate 失败" }
        $listeners = @(Get-NetTCPConnection -LocalPort 80,443 -State Listen -ErrorAction SilentlyContinue)
        foreach ($port in @(80, 443)) {
            $items = @($listeners | Where-Object LocalPort -eq $port)
            if ($items.Count -eq 0 -or @($items | Where-Object OwningProcess -ne $process.ProcessId).Count -gt 0) {
                throw "端口 $port 未由唯一 Caddy PID=$($process.ProcessId) 监听"
            }
        }
        return [pscustomobject]@{ Ok = $true; Detail = "PID=$($process.ProcessId); Config=$CaddyConfig" }
    }
    catch {
        return [pscustomobject]@{ Ok = $false; Detail = $_.Exception.Message }
    }
}

function Test-LocalPing {
    param([string]$Uri)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 5
        $contentType = [string]$response.Headers["Content-Type"]
        return [pscustomobject]@{
            Ok = ($response.StatusCode -eq 200 -and $response.Content -ceq "pong" -and $contentType -like "text/plain*")
            Detail = "$($response.StatusCode) ContentType=$contentType Body=$($response.Content)"
        }
    }
    catch {
        return [pscustomobject]@{ Ok = $false; Detail = $_.Exception.Message }
    }
}

function Get-ConfigIdentity {
    param([hashtable]$Definition)
    $python = Join-Path $Definition.ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) { return [pscustomobject]@{ Ok = $false; Detail = "虚拟环境 Python 不存在" } }
    if (-not (Test-Path (Join-Path $Definition.ProjectRoot ".env"))) {
        return [pscustomobject]@{ Ok = $false; Detail = ".env 不存在" }
    }
    $code = @'
import json
import config
from services.environment_guard import collect_environment_errors, describe_environment
errors = collect_environment_errors(config, require_enabled=True)
print(json.dumps(dict(ok=not errors, errors=errors, actual=describe_environment(config)), ensure_ascii=False))
'@
    Push-Location $Definition.ProjectRoot
    try {
        $raw = & $python -X utf8 -c $code 2>&1
        if ($LASTEXITCODE -ne 0) { return [pscustomobject]@{ Ok = $false; Detail = ($raw -join "`n") } }
        $parsed = ($raw -join "`n") | ConvertFrom-Json
        return [pscustomobject]@{ Ok = [bool]$parsed.ok; Detail = ($parsed | ConvertTo-Json -Depth 8 -Compress) }
    }
    finally {
        Pop-Location
    }
}

function Test-EnvironmentTaskActions {
    param([hashtable]$Definition)
    try {
        $tasks = @(Get-ScheduledTask -TaskName "$($Definition.TaskPrefix)-*" -ErrorAction Stop |
            Where-Object { $_.TaskName -notmatch '-(Caddy|Nginx)$' })
        $webTask = $tasks | Where-Object TaskName -eq "$($Definition.TaskPrefix)-Web" | Select-Object -First 1
        if (-not $webTask) { throw "缺少 Web 计划任务" }
        $expectedPython = Join-Path $Definition.ProjectRoot ".venv\Scripts\python.exe"
        foreach ($task in $tasks) {
            $actions = @($task.Actions)
            if ($actions.Count -ne 1) { throw "$($task.TaskName) Action 数量不是 1" }
            $action = $actions[0]
            $prefix = "$($Definition.TaskPrefix)-"
            if (-not $task.TaskName.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "任务前缀错误：$($task.TaskName)"
            }
            $suffix = $task.TaskName.Substring($prefix.Length)
            if (-not $TaskArguments.Contains($suffix)) { throw "未知任务后缀：$suffix" }
            if (-not (Test-PathEquals ([string]$action.Execute) $expectedPython)) {
                throw "$($task.TaskName) Python 路径错误：$($action.Execute)"
            }
            if (-not (Test-PathEquals ([string]$action.WorkingDirectory) $Definition.ProjectRoot)) {
                throw "$($task.TaskName) 工作目录错误：$($action.WorkingDirectory)"
            }
            $expectedArguments = [string]$TaskArguments[$suffix]
            if (-not ([string]$action.Arguments).Equals(
                $expectedArguments,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
                throw "$($task.TaskName) 参数错误：$($action.Arguments)"
            }
            $null = Assert-TaskPrincipal -Task $task
        }
        return [pscustomobject]@{
            Ok = $true
            Detail = "已验证 $($tasks.Count) 个 Web/Worker 任务 Action"
            WebTask = $webTask
            TaskCount = $tasks.Count
        }
    }
    catch {
        return [pscustomobject]@{ Ok = $false; Detail = $_.Exception.Message; WebTask = $null; TaskCount = 0 }
    }
}

function Test-WorkerTaskStates {
    param([hashtable]$Definition, [bool]$WebRunning)
    try {
        $tasks = @(Get-ScheduledTask -TaskName "$($Definition.TaskPrefix)-*" -ErrorAction SilentlyContinue |
            Where-Object {
                $_.TaskName -ne "$($Definition.TaskPrefix)-Web" -and
                $_.TaskName -notmatch '-(Caddy|Nginx)$'
            })
        $items = @()
        $ok = $true
        foreach ($task in $tasks) {
            $info = Get-ScheduledTaskInfo -TaskName $task.TaskName -ErrorAction Stop
            $enabled = [string]$task.State -ne "Disabled"
            $running = [string]$task.State -eq "Running"
            $healthy = (-not $enabled) -or (-not $WebRunning) -or $running
            if (-not $healthy) { $ok = $false }
            $items += "$($task.TaskName):State=$($task.State),LastTaskResult=$($info.LastTaskResult)"
        }
        $detail = if ($items.Count -gt 0) { $items -join '; ' } else { "没有 Worker 任务" }
        return [pscustomobject]@{
            Ok = $ok
            Detail = $detail
        }
    }
    catch {
        return [pscustomobject]@{ Ok = $false; Detail = $_.Exception.Message }
    }
}

function Test-WebProcessIdentity {
    param([hashtable]$Definition)
    try {
        $listeners = @(Get-NetTCPConnection -LocalPort $Definition.Port -State Listen -ErrorAction SilentlyContinue)
        if ($listeners.Count -eq 0) { return [pscustomobject]@{ Ok = $true; Running = $false; Detail = "未监听" } }
        $pids = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
        if ($pids.Count -ne 1) { throw "多个监听 PID：$($pids -join ',')" }
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($pids[0])" -ErrorAction Stop
        $webTaskName = "$($Definition.TaskPrefix)-Web"
        $webTask = Get-ScheduledTask -TaskName $webTaskName -ErrorAction Stop
        if ([string]$webTask.State -ne "Running") { throw "$webTaskName 状态不是 Running：$($webTask.State)" }
        $null = Assert-TaskPrincipal -Task $webTask
        if ([string]$process.CommandLine -notmatch 'run_waitress\.py') { throw "命令行不是 run_waitress.py" }
        $ownerIdentity = Get-ProcessOwnerIdentity -Process $process
        if (-not (Test-LocalServiceAccountIdentity $ownerIdentity)) {
            throw "进程所有者错误：$ownerIdentity；期望本机 $ServiceAccount"
        }
        return [pscustomobject]@{
            Ok = $true
            Running = $true
            Detail = "PID=$($process.ProcessId); Created=$($process.CreationDate); Owner=$ownerIdentity; Executable=$($process.ExecutablePath)"
        }
    }
    catch {
        return [pscustomobject]@{ Ok = $false; Running = $true; Detail = $_.Exception.Message }
    }
}

$caddy = Test-CaddyState
$results = foreach ($key in @("Production", "Test")) {
    $definition = $map[$key]
    $rootExists = Test-Path $definition.ProjectRoot
    $identity = if ($rootExists) { Get-ConfigIdentity -Definition $definition } else { [pscustomobject]@{ Ok = $false; Detail = "项目目录不存在" } }
    $taskAction = Test-EnvironmentTaskActions -Definition $definition
    $process = Test-WebProcessIdentity -Definition $definition
    $ping = if ($process.Running) { Test-LocalPing -Uri $definition.LocalPing } else { [pscustomobject]@{ Ok = $true; Detail = "服务未运行，未执行 ping" } }
    $workers = Test-WorkerTaskStates -Definition $definition -WebRunning ([bool]$process.Running)
    $taskState = if ($taskAction.WebTask) { [string]$taskAction.WebTask.State } else { "Missing" }
    $operationalOk = $rootExists -and $identity.Ok -and $taskAction.Ok -and $process.Ok -and $workers.Ok
    if ($process.Running -or $taskState -eq "Running") { $operationalOk = $operationalOk -and $ping.Ok -and $process.Running }

    [pscustomobject]@{
        Environment       = $key
        Label             = $definition.Label
        ProjectRoot       = $definition.ProjectRoot
        RootExists        = $rootExists
        IdentityOk        = $identity.Ok
        IdentityDetail    = $identity.Detail
        Port              = $definition.Port
        ProcessIdentityOk = $process.Ok
        ProcessDetail     = $process.Detail
        LocalPingOk       = $ping.Ok
        LocalPingDetail   = $ping.Detail
        TaskActionsOk     = $taskAction.Ok
        WebTaskActionOk   = $taskAction.Ok
        WebTaskDetail     = $taskAction.Detail
        WebTaskState      = $taskState
        TaskCount         = $taskAction.TaskCount
        WorkerStatesOk    = $workers.Ok
        WorkerStates      = $workers.Detail
        OperationalOk     = $operationalOk
    }
}

Write-Host "CaddyOk=$($caddy.Ok) $($caddy.Detail)"
$results | Format-List

if ($FailOnError) {
    $bad = @($results | Where-Object { -not $_.OperationalOk })
    if (-not $caddy.Ok -or $bad.Count -gt 0) { exit 1 }
}
