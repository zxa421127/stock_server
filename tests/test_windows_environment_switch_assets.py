from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def test_environment_map_keeps_independent_roots_ports_and_task_prefixes():
    text = _read("deploy/windows/environment-switch/environment-map.psd1")
    assert 'C:\\stockdata\\stock_server"' in text
    assert 'C:\\stockdata\\stock_server_test"' in text
    assert 'TaskPrefix  = "StockData"' in text
    assert 'TaskPrefix  = "StockDataTest"' in text
    assert "Port        = 8899" in text
    assert "Port        = 8898" in text


def test_switch_script_never_reloads_or_rewrites_caddy():
    text = _read("deploy/windows/environment-switch/Switch-StockEnvironment.ps1")
    assert " validate --config " in text
    assert "reload --config" not in text.lower()
    assert "caddy reload" not in text.lower()
    assert "Set-Content" not in text
    assert "Copy-Item" not in text


def test_switch_script_validates_actual_caddy_process_and_listener_owners():
    text = _read("deploy/windows/environment-switch/Switch-StockEnvironment.ps1")
    assert "ExecutablePath" in text
    assert "CommandLine" in text
    assert "OwningProcess -ne $caddy.ProcessId" in text
    assert "必须且只能存在一个 Caddy" in text


def test_switch_script_uses_exact_python_path_and_arguments_not_root_substring():
    text = _read("deploy/windows/environment-switch/Switch-StockEnvironment.ps1")
    assert "Test-PathEquals" in text
    assert ".venv\\Scripts\\python.exe" in text
    assert "run_waitress.py" in text
    assert "-notlike \"*$($Definition.ProjectRoot)*\"" not in text


def test_switch_script_supports_controlled_restart_and_no_whatif_false_pass():
    text = _read("deploy/windows/environment-switch/Switch-StockEnvironment.ps1")
    assert "RestartTarget" in text
    assert "Wait-PortReleased" in text
    assert "PID 未变化" in text
    assert "WHATIF：" in text
    assert "if ($WhatIfPreference)" in text
    assert "Wait-WorkerHealthy" in text
    assert "Restore-TaskStateSnapshots" in text
    assert "LastTaskResult" in text


def test_switch_script_requires_explicit_confirmation_before_stopping_production():
    text = _read("deploy/windows/environment-switch/Switch-StockEnvironment.ps1")
    assert "STOP-PRODUCTION" in text
    assert "StopOtherEnvironment" in text
    assert "Stop-ScheduledTask" in text
    assert "Disable-ScheduledTask" in text
    assert "environment_preflight" in text
    assert "production_preflight" in text


def test_status_script_checks_task_actions_process_identity_and_can_fail():
    text = _read("deploy/windows/environment-switch/Get-StockEnvironmentStatus.ps1")
    assert "FailOnError" in text
    assert "TaskActionsOk" in text
    assert "WebTaskActionOk" in text
    assert "已验证 $($tasks.Count) 个 Web/Worker 任务 Action" in text
    assert "ProcessIdentityOk" in text
    assert "require_enabled=True" in text
    # Windows PowerShell 5.1 can strip quotes from native -c arguments.
    # Keep the inline Python free of quoted dict keys so status checks do not
    # degrade into NameError: name 'ok' is not defined.
    assert "dict(ok=not errors, errors=errors, actual=describe_environment(config))" in text
    assert '{"ok": not errors' not in text
    assert "exit 1" in text
    assert "WorkerStatesOk" in text
    assert "Test-WorkerTaskStates" in text


def test_environment_overlays_use_separate_redis_namespaces_without_external_fingerprint_fields():
    production = _read("deploy/windows/environment-switch/env-overlays/production.env.overlay.example")
    test = _read("deploy/windows/environment-switch/env-overlays/test.env.overlay.example")
    assert "EXPECTED_REDIS_DB=0" in production
    assert "REDIS_KEY_PREFIX=stock_server" in production
    assert "EXPECTED_REDIS_DB=3" in test
    assert "REDIS_KEY_PREFIX=stock_server_test" in test
    assert "SERVER_PORT=8899" in production
    assert "SERVER_PORT=8898" in test
    assert "EXTERNAL_ENVIRONMENT_TAG" not in production
    assert "EXPECTED_EXTERNAL_RESOURCE_FINGERPRINT" not in production
    assert "EXTERNAL_ENVIRONMENT_TAG" not in test
    assert "EXPECTED_EXTERNAL_RESOURCE_FINGERPRINT" not in test


def test_environment_switch_ping_checks_require_exact_plain_text_pong():
    switch_text = _read("deploy/windows/environment-switch/Switch-StockEnvironment.ps1")
    status_text = _read("deploy/windows/environment-switch/Get-StockEnvironmentStatus.ps1")
    for text in (switch_text, status_text):
        assert '-ceq "pong"' in text
        assert 'text/plain*' in text
        assert '-match "pong"' not in text

def test_environment_switch_scripts_resolve_default_map_after_parameter_binding():
    for relative in (
        "deploy/windows/environment-switch/Switch-StockEnvironment.ps1",
        "deploy/windows/environment-switch/Get-StockEnvironmentStatus.ps1",
    ):
        text = _read(relative)
        assert '[string]$EnvironmentMap = ""' in text
        assert 'Join-Path -Path $resolvedScriptRoot -ChildPath "environment-map.psd1"' in text
        assert '$MyInvocation.MyCommand.Path' in text
        assert '(Join-Path $PSScriptRoot "environment-map.psd1")' not in text
        assert 'Test-Path -LiteralPath $EnvironmentMap' in text


def test_environment_switch_runtime_identity_uses_task_action_principal_owner_and_commandline():
    switch_text = _read("deploy/windows/environment-switch/Switch-StockEnvironment.ps1")
    status_text = _read("deploy/windows/environment-switch/Get-StockEnvironmentStatus.ps1")
    for text in (switch_text, status_text):
        assert '[string]$ServiceAccount = "StockServerSvc"' in text
        assert "Principal.UserId" in text
        assert "Principal.LogonType" in text
        assert 'Equals("Password"' in text
        assert "Invoke-CimMethod" in text
        assert "GetOwner" in text
        assert "run_waitress.py" in text
        assert "Test-LocalServiceAccountIdentity" in text
        # Runtime Win32_Process may report the base interpreter for a venv.
        # The scheduled-task Action is still checked strictly against .venv.
        assert 'Test-PathEquals ([string]$process.ExecutablePath) $expectedPython' not in text
        assert 'Test-PathEquals ([string]$action.Execute) $expectedPython' in text

def test_switch_whatif_keeps_readonly_owner_query_real_and_validates_method_result():
    switch_text = _read("deploy/windows/environment-switch/Switch-StockEnvironment.ps1")
    status_text = _read("deploy/windows/environment-switch/Get-StockEnvironmentStatus.ps1")
    assert '-WhatIf:$false' in switch_text
    for text in (switch_text, status_text):
        assert '$owner.PSObject.Properties["ReturnValue"]' in text
        assert '$owner.PSObject.Properties["User"]' in text
        assert 'GetOwner 未返回结果' in text
        assert 'GetOwner 返回结构异常' in text


def test_switch_whatif_restart_surfaces_both_stop_and_start_halves():
    text = _read("deploy/windows/environment-switch/Switch-StockEnvironment.ps1")
    assert '$RestartTarget -and $WhatIfPreference' in text
    assert '启动并验证 $EnvironmentKey Web（重启计划）' in text
    assert '启动 $EnvironmentKey Worker（重启计划）' in text



def test_restart_waits_for_task_port_and_old_pid_before_starting_replacement():
    text = _read("deploy/windows/environment-switch/Switch-StockEnvironment.ps1")
    assert "function Wait-WebTaskStopped" in text
    assert "Wait-PortReleased -Definition $Definition" in text
    assert 'Get-Process -Id $OldPid -ErrorAction SilentlyContinue' in text
    assert '$taskSettled = ([string]$task.State -in @("Ready", "Disabled"))' in text
    assert '$portReleased = ($listeners.Count -eq 0)' in text
    assert '$oldProcessGone = ($OldPid -le 0 -or $null -eq $oldProcess)' in text
    assert "Wait-WebTaskStopped -TaskName $webName -Definition $Definition -OldPid $OldWebPid" in text
    assert "-OldWebPid $oldPid" in text


def test_restart_refuses_blind_start_until_task_is_ready():
    text = _read("deploy/windows/environment-switch/Switch-StockEnvironment.ps1")
    assert "function Wait-ScheduledTaskReadyForStart" in text
    assert 'if ($state -eq "Ready") { return $task }' in text
    assert 'throw "拒绝重复启动：计划任务 $TaskName 当前仍为 Running"' in text
    assert "Wait-ScheduledTaskReadyForStart -TaskName $webName -Definition $Definition" in text
    assert "Wait-ScheduledTaskReadyForStart -TaskName $taskName -Definition $Definition" in text


def test_stopped_workers_wait_for_scheduler_state_to_settle_before_restart():
    text = _read("deploy/windows/environment-switch/Switch-StockEnvironment.ps1")
    assert "function Wait-ScheduledTaskSettled" in text
    assert '$state -in @("Ready", "Disabled")' in text
    assert "Wait-ScheduledTaskSettled -TaskName $taskName -Definition $Definition" in text
