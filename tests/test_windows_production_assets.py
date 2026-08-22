from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_windows_nginx_template_enforces_mtls_and_hides_admin_on_public_host():
    text = _read("deploy/windows/nginx/stock-server.conf")
    assert "ssl_verify_client on;" in text
    assert "ssl_client_certificate" in text
    assert "X-Admin-Proxy-Auth" in text
    assert "X-Admin-Client-Cert $ssl_client_escaped_cert" in text
    assert "location ^~ /admin/" in text
    assert "return 404;" in text
    assert "127.0.0.1:8899" in text
    assert "/etc/" not in text


def test_windows_dependency_installer_uses_python_module_pip_and_verifies_imports():
    text = _read("deploy/windows/install-dependencies.ps1")
    assert "-m pip" in text
    assert "requirements.txt" in text
    assert "https://pypi.org/simple" in text
    assert "PIL" in text and "cryptography" in text
    assert "Invoke-Expression" not in text


def test_windows_permissions_script_grants_each_write_directory_separately():
    text = _read("deploy/windows/set-ntfs-permissions.ps1")
    assert "foreach ($path in $writeDirs)" in text
    assert "icacls $path" in text
    assert "C:\\stockdata\\data C:\\stockdata\\logs" not in text
    assert "cacls " not in text.lower().replace("icacls ", "")


def test_windows_task_registration_contains_web_and_required_workers():
    text = _read("deploy/windows/register-scheduled-tasks.ps1")
    for module in (
        "run_waitress.py",
        "tools.admin_api_test_worker",
        "tools.api_doc_status_worker",
        "tools.audit_cleanup_worker",
        "tools.feishu_worker",
        "tools.kaipanla_snapshot_worker",
        "tools.tushare_spec_monitor_worker",
    ):
        assert module in text
    assert "Register-ScheduledTask" in text
    assert "Assert-ServiceAccountBatchLogonRight" in text
    assert text.count("Read-Host") >= 2
    assert text.count("-AsSecureString") >= 2
    assert "Get-Credential" not in text
    assert "Test-LocalServiceAccountPassword" in text
    assert "当前已经 Running" in text
    assert "不要再次执行 Start-ScheduledTask" in text
    assert "-RestartTarget" in text
    assert "当前为 Ready" in text


def test_pytest_configuration_excludes_runtime_and_patch_backup_directories():
    text = _read("pytest.ini")
    assert "testpaths = tests" in text
    assert "patch_backups" in text
    assert ".venv" in text


def test_windows_service_account_script_uses_hidden_password_prompts_and_batch_logon_right():
    text = _read("deploy/windows/create-service-account.ps1")
    assert text.count("Read-Host") >= 2
    assert text.count("-AsSecureString") >= 2
    assert "New-LocalUser" in text
    assert "Add-LocalGroupMember" in text
    assert "Ensure-ServiceAccountBatchLogonRight" in text
    assert "service-account-rights.ps1" in text
    assert "S-1-5-32-544" in text
    assert "powershell $pwd" not in text.lower()


def test_windows_service_account_rights_helper_grants_only_batch_logon_and_fails_closed_on_deny():
    text = _read("deploy/windows/service-account-rights.ps1")
    assert "LsaAddAccountRights" in text
    assert "LsaEnumerateAccountRights" in text
    assert "SeBatchLogonRight" in text
    assert "SeDenyBatchLogonRight" in text
    assert "LogonUser" in text
    assert "不会自动移除拒绝权限" in text


def test_windows_verifier_supports_explicit_nginx_caddy_or_none():
    text = _read("deploy/windows/verify-production.ps1")
    assert '[ValidateSet("Nginx", "Caddy", "None")]' in text
    assert '$ReverseProxyType' in text
    assert '$CaddyRoot' in text
    assert '$CaddyConfig' in text
    assert 'validate --config' in text
    assert '--adapter caddyfile' in text
    assert 'Assert-CaddyAdminTrustedHeaders' in text
    assert 'Caddy管理员mTLS可信头结构与代理密钥一致' in text
    assert 'ADMIN_CLIENT_CERT_PROXY_SECRET' in text
    assert 'nginx.exe' in text


def test_windows_task_registration_can_register_or_skip_caddy():
    text = _read("deploy/windows/register-scheduled-tasks.ps1")
    assert '[ValidateSet("Nginx", "Caddy", "None")]' in text
    assert '$SkipReverseProxyTask' in text
    assert '$CaddyRoot' in text
    assert '$CaddyConfig' in text
    assert 'run --config' in text
    assert '--adapter caddyfile' in text
    assert '"$TaskPrefix-Caddy"' in text
    assert '"$TaskPrefix-Nginx"' in text


def test_windows_permissions_handle_caddy_files_only_with_explicit_account():
    text = _read("deploy/windows/set-ntfs-permissions.ps1")
    assert '[ValidateSet("Nginx", "Caddy", "None")]' in text
    assert '$CaddyServiceAccount' in text
    assert '$CaddyConfig' in text
    assert '$CaddyCaFiles' in text
    assert '跳过Caddy文件权限设置' in text
    assert 'Caddy根目录所有权' not in text
    assert '收紧Caddy敏感文件权限并授予运行账号读取权限' in text
    assert 'icacls $filePath /inheritance:r' in text
    assert '$caddyGrantArgs' in text


def test_windows_readme_documents_nginx_and_caddy_without_auto_reloading():
    text = _read("deploy/windows/README.md")
    assert "Nginx 或 Caddy" in text
    assert "stock-server-four-hosts.Caddyfile" in text
    assert "-ReverseProxyType Caddy" in text
    assert "-SkipReverseProxyTask" in text
    assert "不会自动重载" in text
    assert "如果已经为 `Running`，不要再次执行 `Start-ScheduledTask`" in text
    assert "-RestartTarget" in text

def test_environment_switch_scripts_are_windows_powershell_51_safe_and_verify_service_identity():
    for relative in (
        "deploy/windows/environment-switch/Switch-StockEnvironment.ps1",
        "deploy/windows/environment-switch/Get-StockEnvironmentStatus.ps1",
    ):
        text = _read(relative)
        assert '[string]$EnvironmentMap = ""' in text
        assert 'Join-Path -Path $resolvedScriptRoot -ChildPath "environment-map.psd1"' in text
        assert '[string]$ServiceAccount = "StockServerSvc"' in text
        assert "GetOwner" in text
        assert "Principal.UserId" in text

