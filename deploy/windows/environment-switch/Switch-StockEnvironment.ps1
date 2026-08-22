[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Production", "Test")]
    [string]$Target,

    [string[]]$WorkerNames = @(),

    [switch]$RestartTarget,

    [switch]$StopOtherEnvironment,

    [string]$ConfirmProductionStop = "",

    [int]$WaitSeconds = 45,

    [string]$EnvironmentMap = "",

    [string]$ServiceAccount = "StockServerSvc",

    [string]$CaddyExe = "C:\caddy\caddy.exe",

    [string]$CaddyConfig = "C:\caddy\Caddyfile"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Do not resolve $PSScriptRoot inside param() defaults. On Windows PowerShell 5.1
# it can be empty while default parameter expressions are being evaluated. Resolve
# the map only after script parameter binding has completed.
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

$current = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $current.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "请使用管理员 PowerShell 运行本脚本"
}
$map = Import-PowerShellDataFile -Path $EnvironmentMap
$targetDefinition = $map[$Target]
$otherKey = if ($Target -eq "Production") { "Test" } else { "Production" }
$otherDefinition = $map[$otherKey]
$script:ExecutedChange = $false
$script:TaskStateSnapshots = [ordered]@{}

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
}

function Test-PathEquals {
    param([string]$Left, [string]$Right)
    if ([string]::IsNullOrWhiteSpace($Left) -or [string]::IsNullOrWhiteSpace($Right)) {
        return $false
    }
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

function Assert-CaddyHealthy {
    if (-not (Test-Path $CaddyExe)) { throw "Caddy 不存在：$CaddyExe" }
    if (-not (Test-Path $CaddyConfig)) { throw "Caddyfile 不存在：$CaddyConfig" }

    $caddyProcesses = @(Get-CimInstance Win32_Process -Filter "Name='caddy.exe'")
    if ($caddyProcesses.Count -ne 1) {
        throw "必须且只能存在一个 Caddy 进程，当前数量=$($caddyProcesses.Count)"
    }
    $caddy = $caddyProcesses[0]
    if (-not (Test-PathEquals ([string]$caddy.ExecutablePath) $CaddyExe)) {
        throw "运行中的 Caddy 路径错误：$($caddy.ExecutablePath)；期望：$CaddyExe"
    }
    $commandLine = [string]$caddy.CommandLine
    if ($commandLine.IndexOf("run", [System.StringComparison]::OrdinalIgnoreCase) -lt 0 -or
        $commandLine.IndexOf("--config", [System.StringComparison]::OrdinalIgnoreCase) -lt 0 -or
        $commandLine.IndexOf((Get-NormalizedPath $CaddyConfig), [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "运行中的 Caddy 未使用期望配置：$CaddyConfig；CommandLine=$commandLine"
    }

    & $CaddyExe validate --config $CaddyConfig --adapter caddyfile
    if ($LASTEXITCODE -ne 0) { throw "Caddyfile validate 失败；本脚本不会 reload" }

    $listeners = @(Get-NetTCPConnection -LocalPort 80,443 -State Listen -ErrorAction SilentlyContinue)
    foreach ($port in @(80, 443)) {
        $portListeners = @($listeners | Where-Object LocalPort -eq $port)
        if ($portListeners.Count -eq 0) { throw "Caddy 当前未监听 $port" }
        $wrongOwners = @($portListeners | Where-Object OwningProcess -ne $caddy.ProcessId)
        if ($wrongOwners.Count -gt 0) {
            throw "端口 $port 不是由唯一 Caddy PID=$($caddy.ProcessId) 独占监听"
        }
    }
}

function Get-TaskSuffix {
    param([string]$TaskName, [hashtable]$Definition)
    $prefix = "$($Definition.TaskPrefix)-"
    if (-not $TaskName.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "计划任务名称不属于目标前缀：$TaskName"
    }
    return $TaskName.Substring($prefix.Length)
}

function Assert-TaskPointsToRoot {
    param([string]$TaskName, [hashtable]$Definition)
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $actions = @($task.Actions)
    if ($actions.Count -ne 1) { throw "计划任务 $TaskName 的 Action 数量不是 1" }
    $action = $actions[0]
    $expectedPython = Join-Path $Definition.ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-PathEquals ([string]$action.WorkingDirectory) $Definition.ProjectRoot)) {
        throw "计划任务 $TaskName 工作目录错误：$($action.WorkingDirectory)；期望：$($Definition.ProjectRoot)"
    }
    if (-not (Test-PathEquals ([string]$action.Execute) $expectedPython)) {
        throw "计划任务 $TaskName Python 路径错误：$($action.Execute)；期望：$expectedPython"
    }
    $suffix = Get-TaskSuffix -TaskName $TaskName -Definition $Definition
    if (-not $TaskArguments.Contains($suffix)) {
        throw "计划任务 $TaskName 后缀不在允许清单中"
    }
    $expectedArguments = [string]$TaskArguments[$suffix]
    if (-not ([string]$action.Arguments).Equals(
        $expectedArguments,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "计划任务 $TaskName 参数错误：$($action.Arguments)；期望：$expectedArguments"
    }
    $null = Assert-TaskPrincipal -Task $task
    return $task
}

function Invoke-Preflight {
    param([string]$EnvironmentKey, [hashtable]$Definition)
    $root = $Definition.ProjectRoot
    $python = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $root)) { throw "$EnvironmentKey 项目目录不存在：$root" }
    if (-not (Test-Path $python)) { throw "$EnvironmentKey 虚拟环境不存在：$python" }
    if (-not (Test-Path (Join-Path $root ".env"))) { throw "$EnvironmentKey .env 不存在" }

    Push-Location $root
    try {
        Write-Host "[$EnvironmentKey] 执行通用环境预检..."
        & $python -X utf8 -m tools.environment_preflight
        if ($LASTEXITCODE -ne 0) { throw "$EnvironmentKey 通用环境预检失败" }
        if ($EnvironmentKey -eq "Production") {
            Write-Host "[$EnvironmentKey] 执行生产失败关闭预检..."
            & $python -X utf8 -m tools.production_preflight
            if ($LASTEXITCODE -ne 0) { throw "$EnvironmentKey 生产预检失败" }
        }
    }
    finally {
        Pop-Location
    }
}

function Get-WebProcess {
    param([hashtable]$Definition, [switch]$AllowMissing)
    $connections = @(Get-NetTCPConnection -LocalPort $Definition.Port -State Listen -ErrorAction SilentlyContinue)
    if ($connections.Count -eq 0) {
        if ($AllowMissing) { return $null }
        throw "端口 $($Definition.Port) 未监听"
    }
    $processIds = @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($processIds.Count -ne 1) {
        throw "端口 $($Definition.Port) 存在多个监听进程：$($processIds -join ',')"
    }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($processIds[0])" -ErrorAction Stop
    $webTaskName = "$($Definition.TaskPrefix)-Web"
    $webTask = Assert-TaskPointsToRoot -TaskName $webTaskName -Definition $Definition
    if ([string]$webTask.State -ne "Running") {
        throw "端口 $($Definition.Port) 正在监听，但计划任务 $webTaskName 状态不是 Running：$($webTask.State)"
    }
    $commandLine = [string]$process.CommandLine
    if ($commandLine.IndexOf("run_waitress.py", [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "端口 $($Definition.Port) 不是由 run_waitress.py 监听：$commandLine"
    }
    $ownerIdentity = Get-ProcessOwnerIdentity -Process $process
    if (-not (Test-LocalServiceAccountIdentity $ownerIdentity)) {
        throw "端口 $($Definition.Port) 进程所有者错误：$ownerIdentity；期望本机 $ServiceAccount"
    }
    # Windows venv may launch the base interpreter, so Win32_Process.ExecutablePath can
    # legitimately be C:\Program Files\Python312\python.exe. The scheduled-task
    # Action remains strictly pinned to the project .venv; runtime identity is proven by
    # task Action + task principal + listener PID + run_waitress.py + process owner + /ping.
    return $process
}

function Wait-PortReleased {
    param([hashtable]$Definition)
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    do {
        if (@(Get-NetTCPConnection -LocalPort $Definition.Port -State Listen -ErrorAction SilentlyContinue).Count -eq 0) {
            return
        }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)
    throw "端口 $($Definition.Port) 在 $WaitSeconds 秒内未释放"
}

function Wait-ScheduledTaskSettled {
    param([string]$TaskName, [hashtable]$Definition)
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    $stableChecks = 0
    do {
        $task = Assert-TaskPointsToRoot -TaskName $TaskName -Definition $Definition
        $state = [string]$task.State
        if ($state -in @("Ready", "Disabled")) {
            $stableChecks++
            if ($stableChecks -ge 2) { return $task }
        }
        else {
            $stableChecks = 0
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    $finalTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    throw "计划任务 $TaskName 在 $WaitSeconds 秒内未完成停止状态收敛：State=$($finalTask.State)"
}

function Wait-WebTaskStopped {
    param(
        [string]$TaskName,
        [hashtable]$Definition,
        [int]$OldPid
    )
    # A released TCP port does not guarantee Task Scheduler has finished the old
    # instance.  Wait for all three signals before starting a replacement:
    # listener gone + old PID gone + task settled to Ready/Disabled.
    Wait-PortReleased -Definition $Definition
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    $stableChecks = 0
    do {
        $task = Assert-TaskPointsToRoot -TaskName $TaskName -Definition $Definition
        $listeners = @(Get-NetTCPConnection -LocalPort $Definition.Port -State Listen -ErrorAction SilentlyContinue)
        $oldProcess = if ($OldPid -gt 0) { Get-Process -Id $OldPid -ErrorAction SilentlyContinue } else { $null }
        $taskSettled = ([string]$task.State -in @("Ready", "Disabled"))
        $portReleased = ($listeners.Count -eq 0)
        $oldProcessGone = ($OldPid -le 0 -or $null -eq $oldProcess)
        if ($taskSettled -and $portReleased -and $oldProcessGone) {
            $stableChecks++
            if ($stableChecks -ge 2) { return }
        }
        else {
            $stableChecks = 0
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    $finalTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $finalListeners = @(Get-NetTCPConnection -LocalPort $Definition.Port -State Listen -ErrorAction SilentlyContinue)
    $oldStillExists = $false
    if ($OldPid -gt 0) {
        $oldStillExists = $null -ne (Get-Process -Id $OldPid -ErrorAction SilentlyContinue)
    }
    throw "等待 $TaskName 完全停止超时：State=$($finalTask.State)，PortListeners=$($finalListeners.Count)，OldPid=$OldPid，OldPidExists=$oldStillExists"
}

function Wait-ScheduledTaskReadyForStart {
    param([string]$TaskName, [hashtable]$Definition)
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    do {
        $task = Assert-TaskPointsToRoot -TaskName $TaskName -Definition $Definition
        $state = [string]$task.State
        if ($state -eq "Ready") { return $task }
        if ($state -eq "Running") {
            throw "拒绝重复启动：计划任务 $TaskName 当前仍为 Running"
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    $finalTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    throw "计划任务 $TaskName 在 $WaitSeconds 秒内未进入 Ready：State=$($finalTask.State)"
}

function Wait-EnvironmentHealthy {
    param([hashtable]$Definition)
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    do {
        Start-Sleep -Seconds 2
        try {
            $process = Get-WebProcess -Definition $Definition
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Definition.LocalPing -TimeoutSec 5
            $contentType = [string]$response.Headers["Content-Type"]
            if ($response.StatusCode -eq 200 -and $response.Content -ceq "pong" -and $contentType -like "text/plain*") {
                return $process
            }
        }
        catch {
            # Keep waiting until the deadline.
        }
    } while ((Get-Date) -lt $deadline)
    throw "$($Definition.Label) 在 $WaitSeconds 秒内未通过进程身份和本机 /ping 验证：$($Definition.LocalPing)"
}

function Enable-TaskForStart {
    param([object]$Task, [string]$EnvironmentKey)
    if ([string]$Task.State -eq "Disabled") {
        if ($PSCmdlet.ShouldProcess($Task.TaskName, "启用 $EnvironmentKey 计划任务")) {
            Enable-ScheduledTask -TaskName $Task.TaskName | Out-Null
            $script:ExecutedChange = $true
        }
    }
}

function Save-TaskStateSnapshot {
    param([string]$TaskName, [hashtable]$Definition)
    if ($script:TaskStateSnapshots.Contains($TaskName)) { return }
    $task = Assert-TaskPointsToRoot -TaskName $TaskName -Definition $Definition
    $script:TaskStateSnapshots[$TaskName] = [pscustomobject]@{
        TaskName = $TaskName
        Enabled = ([string]$task.State -ne "Disabled")
        Running = ([string]$task.State -eq "Running")
    }
}

function Restore-TaskStateSnapshots {
    param([hashtable]$Definition)
    if ($WhatIfPreference -or $script:TaskStateSnapshots.Count -eq 0) { return }
    Write-Warning "目标环境启动未完成，正在恢复本次操作前的任务启用/运行状态。"
    foreach ($snapshot in @($script:TaskStateSnapshots.Values)) {
        try {
            $null = Assert-TaskPointsToRoot -TaskName $snapshot.TaskName -Definition $Definition
            $currentTask = Get-ScheduledTask -TaskName $snapshot.TaskName -ErrorAction Stop
            if ([string]$currentTask.State -eq "Running" -and -not $snapshot.Running) {
                Stop-ScheduledTask -TaskName $snapshot.TaskName -ErrorAction SilentlyContinue
            }
            if ($snapshot.Enabled) {
                Enable-ScheduledTask -TaskName $snapshot.TaskName | Out-Null
            }
            else {
                Disable-ScheduledTask -TaskName $snapshot.TaskName | Out-Null
            }
            $currentTask = Get-ScheduledTask -TaskName $snapshot.TaskName -ErrorAction Stop
            if ($snapshot.Running -and [string]$currentTask.State -ne "Running") {
                Start-ScheduledTask -TaskName $snapshot.TaskName
            }
        }
        catch {
            Write-Warning "恢复任务 $($snapshot.TaskName) 失败：$($_.Exception.Message)"
        }
    }
}

function Wait-WorkerHealthy {
    param([string]$TaskName, [hashtable]$Definition)
    $null = Assert-TaskPointsToRoot -TaskName $TaskName -Definition $Definition
    $deadline = (Get-Date).AddSeconds([Math]::Min([Math]::Max($WaitSeconds, 10), 60))
    do {
        Start-Sleep -Seconds 2
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
        if ([string]$task.State -eq "Running") {
            return [pscustomobject]@{
                TaskName = $TaskName
                State = [string]$task.State
                LastTaskResult = [int64]$info.LastTaskResult
            }
        }
        if ([int64]$info.LastTaskResult -ne 0) {
            throw "Worker $TaskName 已退出，LastTaskResult=$($info.LastTaskResult)"
        }
    } while ((Get-Date) -lt $deadline)
    $finalTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $finalInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
    throw "Worker $TaskName 未保持 Running：State=$($finalTask.State)，LastTaskResult=$($finalInfo.LastTaskResult)"
}

function Get-SelectedWorkerNames {
    param([hashtable]$Definition)
    foreach ($workerName in $WorkerNames) {
        if (-not $TaskArguments.Contains($workerName) -or $workerName -eq "Web") {
            throw "WorkerNames 包含无效后缀：$workerName"
        }
    }
    if ($WorkerNames.Count -gt 0 -or -not $RestartTarget) {
        return @($WorkerNames | Select-Object -Unique)
    }
    $tasks = @(Get-ScheduledTask -TaskName "$($Definition.TaskPrefix)-*" -ErrorAction SilentlyContinue)
    return @(
        $tasks |
            Where-Object {
                $_.TaskName -ne "$($Definition.TaskPrefix)-Web" -and
                $_.TaskName -notmatch '-(Caddy|Nginx)$' -and
                [string]$_.State -ne "Disabled"
            } |
            ForEach-Object { Get-TaskSuffix -TaskName $_.TaskName -Definition $Definition } |
            Where-Object { $TaskArguments.Contains($_) } |
            Select-Object -Unique
    )
}

function Stop-TargetForRestart {
    param(
        [string]$EnvironmentKey,
        [hashtable]$Definition,
        [string[]]$SelectedWorkers,
        [int]$OldWebPid
    )
    $stoppedWorkers = @()
    foreach ($workerName in $SelectedWorkers) {
        $taskName = "$($Definition.TaskPrefix)-$workerName"
        $task = Assert-TaskPointsToRoot -TaskName $taskName -Definition $Definition
        if ([string]$task.State -eq "Running" -and $PSCmdlet.ShouldProcess($taskName, "停止以加载新代码")) {
            Stop-ScheduledTask -TaskName $taskName
            $stoppedWorkers += $taskName
            $script:ExecutedChange = $true
        }
    }
    $webName = "$($Definition.TaskPrefix)-Web"
    $webTask = Assert-TaskPointsToRoot -TaskName $webName -Definition $Definition
    $webStopRequested = $false
    if ([string]$webTask.State -eq "Running" -and $PSCmdlet.ShouldProcess($webName, "停止以加载新代码")) {
        Stop-ScheduledTask -TaskName $webName
        $webStopRequested = $true
        $script:ExecutedChange = $true
    }

    if (-not $WhatIfPreference) {
        foreach ($taskName in $stoppedWorkers) {
            $null = Wait-ScheduledTaskSettled -TaskName $taskName -Definition $Definition
        }
        if ($webStopRequested) {
            Wait-WebTaskStopped -TaskName $webName -Definition $Definition -OldPid $OldWebPid
        }
        elseif ($OldWebPid -gt 0) {
            throw "请求重启时检测到旧 Web PID=$OldWebPid，但计划任务 $webName 未执行停止；拒绝继续启动"
        }
    }
}

function Start-Environment {
    param([string]$EnvironmentKey, [hashtable]$Definition, [string[]]$SelectedWorkers)
    $webName = "$($Definition.TaskPrefix)-Web"
    Save-TaskStateSnapshot -TaskName $webName -Definition $Definition
    foreach ($workerName in $SelectedWorkers) {
        Save-TaskStateSnapshot -TaskName "$($Definition.TaskPrefix)-$workerName" -Definition $Definition
    }
    $oldProcess = Get-WebProcess -Definition $Definition -AllowMissing
    $oldPid = if ($oldProcess) { [int]$oldProcess.ProcessId } else { 0 }

    if ($RestartTarget) {
        Stop-TargetForRestart -EnvironmentKey $EnvironmentKey -Definition $Definition -SelectedWorkers $SelectedWorkers -OldWebPid $oldPid
    }

    $webName = "$($Definition.TaskPrefix)-Web"
    $webTask = Assert-TaskPointsToRoot -TaskName $webName -Definition $Definition
    Enable-TaskForStart -Task $webTask -EnvironmentKey $EnvironmentKey
    $runningProcess = Get-WebProcess -Definition $Definition -AllowMissing
    if ($RestartTarget -and $WhatIfPreference) {
        # The simulated stop above does not actually stop the process, so the live
        # listener still exists during -WhatIf. Explicitly show the corresponding
        # planned start; otherwise WhatIf would display only half of the restart.
        $null = $PSCmdlet.ShouldProcess($webName, "启动并验证 $EnvironmentKey Web（重启计划）")
    }
    elseif (-not $runningProcess) {
        if (-not $WhatIfPreference) {
            $null = Wait-ScheduledTaskReadyForStart -TaskName $webName -Definition $Definition
        }
        if ($PSCmdlet.ShouldProcess($webName, "启动并验证 $EnvironmentKey Web")) {
            Start-ScheduledTask -TaskName $webName
            $script:ExecutedChange = $true
        }
    }

    if (-not $WhatIfPreference) {
        $newProcess = Wait-EnvironmentHealthy -Definition $Definition
        if ($RestartTarget -and $oldPid -gt 0 -and [int]$newProcess.ProcessId -eq $oldPid) {
            throw "请求重启后 Web PID 未变化，不能确认新代码已加载"
        }
    }

    foreach ($workerName in $SelectedWorkers) {
        $taskName = "$($Definition.TaskPrefix)-$workerName"
        $task = Assert-TaskPointsToRoot -TaskName $taskName -Definition $Definition
        Enable-TaskForStart -Task $task -EnvironmentKey $EnvironmentKey
        $task = Get-ScheduledTask -TaskName $taskName
        if ($RestartTarget -and $WhatIfPreference -and [string]$task.State -eq "Running") {
            # Same reason as Web: a WhatIf stop leaves the real Worker running, so
            # explicitly surface the start half of the restart plan.
            $null = $PSCmdlet.ShouldProcess($taskName, "启动 $EnvironmentKey Worker（重启计划）")
        }
        elseif ([string]$task.State -ne "Running") {
            if (-not $WhatIfPreference) {
                $null = Wait-ScheduledTaskReadyForStart -TaskName $taskName -Definition $Definition
            }
            if ($PSCmdlet.ShouldProcess($taskName, "启动 $EnvironmentKey Worker")) {
                Start-ScheduledTask -TaskName $taskName
                $script:ExecutedChange = $true
            }
        }
        if (-not $WhatIfPreference) {
            $workerStatus = Wait-WorkerHealthy -TaskName $taskName -Definition $Definition
            Write-Host "Worker 健康：$($workerStatus.TaskName) State=$($workerStatus.State)"
        }
    }
}

function Stop-Environment {
    param([string]$EnvironmentKey, [hashtable]$Definition)
    if ($EnvironmentKey -eq "Production" -and $ConfirmProductionStop -cne "STOP-PRODUCTION") {
        throw "停止生产环境必须显式传入 -ConfirmProductionStop STOP-PRODUCTION"
    }
    $tasks = @(Get-ScheduledTask -TaskName "$($Definition.TaskPrefix)-*" -ErrorAction SilentlyContinue |
        Where-Object { $_.TaskName -notmatch '-(Caddy|Nginx)$' })
    $ordered = @($tasks | Where-Object TaskName -ne "$($Definition.TaskPrefix)-Web") +
        @($tasks | Where-Object TaskName -eq "$($Definition.TaskPrefix)-Web")
    foreach ($task in $ordered) {
        $null = Assert-TaskPointsToRoot -TaskName $task.TaskName -Definition $Definition
        if ($PSCmdlet.ShouldProcess($task.TaskName, "停止并禁用 $EnvironmentKey 任务")) {
            if ([string]$task.State -eq "Running") {
                Stop-ScheduledTask -TaskName $task.TaskName
            }
            Disable-ScheduledTask -TaskName $task.TaskName | Out-Null
            $script:ExecutedChange = $true
        }
    }
}

Write-Host "目标环境：$Target ($($targetDefinition.ProjectRoot), 端口 $($targetDefinition.Port))"
Write-Host "本脚本不会修改或 reload Caddy，也不会复制/覆盖 .env、数据库、证书或日志。"
Assert-CaddyHealthy
Invoke-Preflight -EnvironmentKey $Target -Definition $targetDefinition
$selectedWorkers = Get-SelectedWorkerNames -Definition $targetDefinition
try {
    Start-Environment -EnvironmentKey $Target -Definition $targetDefinition -SelectedWorkers $selectedWorkers
}
catch {
    Restore-TaskStateSnapshots -Definition $targetDefinition
    throw
}

if ($StopOtherEnvironment) {
    Write-Warning "已请求停止并禁用另一套环境：$otherKey。两个环境本可并行运行，通常无需执行此操作。"
    Stop-Environment -EnvironmentKey $otherKey -Definition $otherDefinition
}

if ($WhatIfPreference) {
    Write-Host "WHATIF：已完成只读预检和计划展示；未启动、停止、启用或禁用任何任务。"
    return
}

$finalProcess = Wait-EnvironmentHealthy -Definition $targetDefinition
Write-Host "PASS：$Target 当前健康；PID=$($finalProcess.ProcessId)，本机 /ping 已通过；已选择 Worker=$($selectedWorkers -join ',')."
if ($RestartTarget) {
    Write-Host "已执行受控重启并验证 PID 变化；目标 Web 已加载新进程。"
}
elseif (-not $script:ExecutedChange) {
    Write-Host "目标环境原本已运行，本次只完成身份、配置和健康复核。"
}
Write-Host "公网只读复核：$($targetDefinition.PublicPing)"
