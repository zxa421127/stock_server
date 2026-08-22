from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "windows" / "Publish-StockCodeToProduction.ps1"


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8-sig")


def test_publish_script_is_fail_closed_for_live_production():
    text = _text()
    assert "Assert-ProductionOffline" in text
    assert "Get-NetTCPConnection -LocalPort 8899" in text
    assert 'Get-ScheduledTask -TaskName "StockData-*"' in text


def test_publish_script_uses_clean_package_manifest_and_preflights():
    text = _text()
    assert "tools.release.build_source_package" in text
    assert "SOURCE_MANIFEST.json" in text
    assert "Assert-ZipSafe" in text
    assert "Assert-SourceManifest" in text
    assert "tools.environment_preflight" in text
    assert "tools.production_preflight" in text


def test_publish_script_protects_runtime_assets():
    text = _text()
    assert "永不从 Test 发布/覆盖：.env、.venv、data、logs、security" in text
    assert '(Join-Path $ProductionRoot ".venv")' in text
    assert '(Join-Path $ProductionRoot "data")' in text
    assert '(Join-Path $ProductionRoot "logs")' in text
    assert '(Join-Path $ProductionRoot "security")' in text
    assert '(Join-Path $ProductionRoot ".env")' in text
    assert "Copy-Item C:\\stockdata\\stock_server_test" not in text


def test_publish_script_hash_protects_production_env():
    text = _text()
    assert "$envHashBefore" in text
    assert "Production .env 在发布过程中发生变化" in text
    assert "Assert-ProtectedRuntimeAssets" in text


def test_publish_script_does_not_start_or_register_production():
    text = _text()
    assert "production_started = $false" in text
    assert "caddy_modified = $false" in text
    assert "Start-ScheduledTask" not in text
    assert "Register-ScheduledTask" not in text


def test_publish_script_can_bootstrap_independent_prod_venv():
    text = _text()
    assert "[switch]$BootstrapProductionVenv" in text
    assert "sys._base_executable" in text
    assert "-m venv" in text


def test_publish_script_has_validate_only_mode():
    text = _text()
    assert "[switch]$ValidateOnly" in text
    assert "VALIDATE-ONLY PASS" in text



def test_publish_script_gates_test_plan_catalog_before_pytest():

    text = _text()

    gate = text.index(
        "FIX3C_TEST_PLAN_GATE_V1"
    )

    pytest_call = text.index(
        "-m pytest -q"
    )

    assert gate < pytest_call


def test_publish_script_cross_checks_stage_before_prod_write():

    text = _text()

    gate = text.index(
        "FIX3C_STAGE_PLAN_GATE_V1"
    )

    project_root = text.index(
        "--project-root $ProductionRoot"
    )

    backup_step = text.index(
        'Write-Step "7/11'
    )

    sync_step = text.index(
        'Write-Step "8/11'
    )

    assert gate < project_root < backup_step
    assert project_root < sync_step


def test_validate_only_runs_after_stage_plan_gate():

    text = _text()

    gate = text.index(
        "--project-root $ProductionRoot"
    )

    validate_only = text.index(
        "if ($ValidateOnly)"
    )

    assert gate < validate_only
