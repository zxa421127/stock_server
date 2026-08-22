[CmdletBinding()]
param(
    [string]$ProjectRoot = "C:\stockdata\stock_server",
    [string]$ServiceAccount = "StockServerSvc",
    [string]$TaskPrefix = "StockData",
    [ValidateSet("Nginx", "Caddy", "None")]
    [string]$ReverseProxyType = "Nginx",
    [string]$NginxRoot = "C:\stockdata\nginx",
    [string]$CaddyRoot = "C:\caddy",
    [string]$CaddyConfig = "C:\caddy\Caddyfile",
    [string[]]$EnabledWorkers = @(),
    [switch]$SkipReverseProxyTask,
    [switch]$SkipOptionalWorkers
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$rightsHelper = Join-Path $PSScriptRoot "service-account-rights.ps1"
if (-not (Test-Path $rightsHelper -PathType Leaf)) { throw "服务账号权限辅助脚本不存在：$rightsHelper" }
. $rightsHelper

$current = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $current.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "请使用管理员PowerShell运行本脚本"
}

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Python虚拟环境不存在：$python" }
$serviceUser = Get-LocalUser -Name $ServiceAccount -ErrorAction SilentlyContinue
if (-not $serviceUser) {
    throw "本地服务账号不存在：$ServiceAccount"
}
if (-not $serviceUser.Enabled) {
    throw "本地服务账号已禁用：$ServiceAccount"
}

$definitions = [ordered]@{
    "Web" = "-X utf8 run_waitress.py"
    "AdminApiTestWorker" = "-X utf8 -m tools.admin_api_test_worker"
    "ApiDocStatusWorker" = "-X utf8 -m tools.api_doc_status_worker"
    "AuditCleanupWorker" = "-X utf8 -m tools.audit_cleanup_worker"
    "FeishuWorker" = "-X utf8 -m tools.feishu_worker"
    "KaipanlaSnapshotWorker" = "-X utf8 -m tools.kaipanla_snapshot_worker"
    "TushareSpecMonitorWorker" = "-X utf8 -m tools.tushare_spec_monitor_worker"
}
$enabledWorkersSpecified = $PSBoundParameters.ContainsKey("EnabledWorkers")
$enabledSet = @{}
foreach ($name in $EnabledWorkers) {
    if (-not $definitions.Contains($name) -or $name -eq "Web") {
        throw "EnabledWorkers 包含无效任务后缀：$name"
    }
    $enabledSet[$name] = $true
}

$identity = "$env:COMPUTERNAME\$ServiceAccount"
Assert-ServiceAccountBatchLogonRight -AccountName $identity

Write-Host "计划任务服务账号密码硬性要求：16-32位；至少包含1个大写英文字母、1个小写英文字母、1个数字、1个英文半角特殊符号；禁止空格、Tab、换行、中文、全角字符及其他非ASCII字符。"
Write-Host "本步骤输入的是现有${ServiceAccount}密码；不会修改账号密码。两次输入必须完全一致。"
$first = Read-Host "请输入${ServiceAccount}服务账号密码，用于注册开机任务" -AsSecureString
$second = Read-Host "请再次输入同一服务账号密码" -AsSecureString
$firstPtr = [IntPtr]::Zero
$secondPtr = [IntPtr]::Zero
$plainPassword = $null
$secondText = $null
$firstPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($first)
$secondPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($second)
try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($firstPtr)
    $secondText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secondPtr)

    if ($plainPassword -cne $secondText) { throw "两次输入的服务账号密码不一致，已取消计划任务注册" }
    if ($plainPassword.Length -lt 16 -or $plainPassword.Length -gt 32) { throw "服务账号密码必须为16-32位" }
    if ($plainPassword -match '\s') { throw "服务账号密码禁止包含空格、Tab或换行" }
    if ($plainPassword.ToCharArray() | Where-Object { ([int][char]$_ -lt 33) -or ([int][char]$_ -gt 126) }) {
        throw "服务账号密码只能使用ASCII英文半角可见字符，禁止中文、全角字符或其他非ASCII字符"
    }
    if ($plainPassword -cnotmatch '[A-Z]') { throw "服务账号密码必须至少包含1个大写英文字母" }
    if ($plainPassword -cnotmatch '[a-z]') { throw "服务账号密码必须至少包含1个小写英文字母" }
    if ($plainPassword -notmatch '[0-9]') { throw "服务账号密码必须至少包含1个数字" }
    if ($plainPassword -notmatch '[^A-Za-z0-9]') { throw "服务账号密码必须至少包含1个英文半角特殊符号" }

    $credentialError = Test-LocalServiceAccountPassword -AccountName $identity -PlainPassword $plainPassword
    if ($credentialError -ne 0) {
        throw "StockServerSvc凭据验证失败，Windows错误码=$credentialError。请确认输入的是当前服务账号密码；脚本不会继续注册任务。"
    }
    Write-Host "PASS：StockServerSvc凭据已验证。"
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $webSettings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Days 3650)
    $workerSettings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Days 3650)

    foreach ($item in $definitions.GetEnumerator()) {
        $taskName = "$TaskPrefix-$($item.Key)"
        $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

        if ($SkipOptionalWorkers -and $item.Key -in @("FeishuWorker", "KaipanlaSnapshotWorker")) {
            if ($existingTask) {
                if ([string]$existingTask.State -eq "Running") {
                    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
                }
                Disable-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue | Out-Null
                Write-Host "已停止并禁用现有可选任务：$taskName"
            }
            else {
                Write-Host "已跳过未存在的可选任务：$taskName"
            }
            continue
        }

        $isWeb = $item.Key -eq "Web"
        if ($isWeb) {
            $shouldEnable = $true
        }
        elseif ($enabledWorkersSpecified) {
            $shouldEnable = $enabledSet.ContainsKey($item.Key)
        }
        elseif ($existingTask) {
            # 未显式传 EnabledWorkers 时保留旧任务的启用/禁用状态，避免重注册意外停掉生产 Worker。
            $shouldEnable = [string]$existingTask.State -ne "Disabled"
        }
        else {
            # 新建 Worker 没有明确白名单时默认禁用。
            $shouldEnable = $false
        }

        $settings = if ($isWeb) { $webSettings } else { $workerSettings }
        $action = New-ScheduledTaskAction -Execute $python -Argument $item.Value -WorkingDirectory $ProjectRoot
        Register-ScheduledTask `
            -TaskName $taskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -User $identity `
            -Password $plainPassword `
            -RunLevel Highest `
            -Force | Out-Null
        if ($shouldEnable) {
            Enable-ScheduledTask -TaskName $taskName | Out-Null
        }
        else {
            Disable-ScheduledTask -TaskName $taskName | Out-Null
        }
    }

    if ($SkipReverseProxyTask) {
        Write-Host "已按参数跳过反向代理计划任务注册。"
    }
    else {
        switch ($ReverseProxyType) {
            "Nginx" {
                $nginxExe = Join-Path $NginxRoot "nginx.exe"
                if (Test-Path $nginxExe) {
                    $nginxPrefix = ($NginxRoot -replace '\\', '/').TrimEnd('/') + '/'
                    $nginxArguments = '-p "{0}" -c conf/nginx.conf -g "daemon off;"' -f $nginxPrefix
                    $nginxAction = New-ScheduledTaskAction `
                        -Execute $nginxExe `
                        -Argument $nginxArguments `
                        -WorkingDirectory $NginxRoot
                    Register-ScheduledTask `
                        -TaskName "$TaskPrefix-Nginx" `
                        -Action $nginxAction `
                        -Trigger $trigger `
                        -Settings $webSettings `
                        -User $identity `
                        -Password $plainPassword `
                        -RunLevel Highest `
                        -Force | Out-Null
                }
                else {
                    Write-Warning "未找到Nginx，可执行文件：$nginxExe；未注册Nginx任务。"
                }
            }
            "Caddy" {
                $caddyExe = Join-Path $CaddyRoot "caddy.exe"
                if (-not (Test-Path $caddyExe)) {
                    Write-Warning "未找到Caddy，可执行文件：$caddyExe；未注册Caddy任务。"
                }
                elseif (-not (Test-Path $CaddyConfig)) {
                    Write-Warning "未找到Caddy配置文件：$CaddyConfig；未注册Caddy任务。"
                }
                else {
                    $caddyArguments = 'run --config "{0}" --adapter caddyfile' -f $CaddyConfig
                    $caddyAction = New-ScheduledTaskAction `
                        -Execute $caddyExe `
                        -Argument $caddyArguments `
                        -WorkingDirectory $CaddyRoot
                    Register-ScheduledTask `
                        -TaskName "$TaskPrefix-Caddy" `
                        -Action $caddyAction `
                        -Trigger $trigger `
                        -Settings $webSettings `
                        -User $identity `
                        -Password $plainPassword `
                        -RunLevel Highest `
                        -Force | Out-Null
                }
            }
            "None" {
                Write-Host "ReverseProxyType=None，未注册反向代理计划任务。"
            }
        }
    }
}
finally {
    if ($firstPtr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($firstPtr)
    }
    if ($secondPtr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secondPtr)
    }
    $plainPassword = $null
    $secondText = $null
}

$registeredTasks = Get-ScheduledTask -TaskName "$TaskPrefix-*"
$registeredTasks | Select-Object TaskName, State
if ($enabledWorkersSpecified) {
    Write-Host "PASS：Web 与显式 EnabledWorkers 计划任务已注册并启用；其余 Worker 已禁用。"
}
else {
    Write-Host "PASS：Web 计划任务已注册并启用；现有 Worker 保留原启用状态，新建 Worker 默认禁用。"
}

$webTaskName = "$TaskPrefix-Web"
$webTask = $registeredTasks | Where-Object { $_.TaskName -eq $webTaskName } | Select-Object -First 1
if ($webTask) {
    $webState = [string]$webTask.State
    if ($webState -eq "Running") {
        Write-Warning "${webTaskName} 当前已经 Running。不要再次执行 Start-ScheduledTask，否则 Task Scheduler 会忽略或排队重复启动请求。"
        Write-Warning "本脚本不会自动重启正在运行的 Web；如果本次覆盖了 Python/应用代码，现有进程仍可能加载旧代码，必须使用环境切换脚本的 -RestartTarget 做受控重启后，再验收端口与 /ping。"
    }
    elseif ($webState -eq "Ready") {
        Write-Host "INFO：${webTaskName} 当前为 Ready（已注册/启用但未运行）。首次部署请显式启动一次，再验证 State、端口、/ping 和进程所有者。"
    }
    else {
        Write-Host "INFO：${webTaskName} 当前状态=$webState。Enabled不等于Running，请按部署手册完成实际运行验收。"
    }
}
