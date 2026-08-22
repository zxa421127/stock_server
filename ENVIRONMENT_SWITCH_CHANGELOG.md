# Production/Test Environment Switch Patch

## Purpose

Add fail-closed deployment-slot identity checks and Windows operator scripts for
running the production and Tencent Cloud test environments side by side without
rewriting one `.env` file or creating a second reverse proxy.

## Added

- `services/environment_guard.py`
- `tools/environment_preflight.py`
- `deploy/windows/environment-switch/environment-map.psd1`
- `deploy/windows/environment-switch/Get-StockEnvironmentStatus.ps1`
- `deploy/windows/environment-switch/Switch-StockEnvironment.ps1`
- `deploy/windows/environment-switch/env-overlays/*.example`
- `docs/operations/production-test-environment-switch.md`
- environment guard and Windows asset tests

## Modified

- `config.py`: deployment-slot guard settings
- `.env.example`: documented non-secret guard fields
- `app.py`: run the guard before database/Web startup
- all dedicated Worker entry points: run the same guard
- `tools/production_preflight.py`: include environment identity result
- `tools/release/build_production_package.py`: include the shared preflight CLI
- `deploy/windows/README.md`: link to the new operating procedure

## Compatibility

`ENVIRONMENT_GUARD_ENABLED` defaults to `False`, so existing installations keep
their previous behavior until the new `DEPLOYMENT_SLOT` and `EXPECTED_*` values
are deliberately configured. Real production and cloud-test `.env` files
should enable the guard after their values have been verified.
