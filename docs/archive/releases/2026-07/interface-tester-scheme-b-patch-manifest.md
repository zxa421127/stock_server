# 市场接口测试台方案B补丁清单

## 生产代码

- `.env.example`
- `config.py`
- `routes/admin_market_test_routes.py`
- `services/admin_api_test_batch_service.py`
- `services/admin_api_test_repository.py`
- `services/admin_market_test_service.py`
- `services/api_doc_catalog.py`
- `services/api_doc_service.py`
- `services/market_interface_spec_service.py`
- `services/tushare_spec_sync_service.py`
- `templates/admin/interface_tester.html`
- `tools/audit_interface_specs.py`
- `tools/sync_tushare_interface_specs.py`

## 规格文件

- `interface_specs/current.json`
- `interface_specs/releases/spec-20260725-official-bootstrap-v1/effective_specs.json`
- `interface_specs/releases/spec-20260725-official-bootstrap-v1/manifest.json`

## 测试和夹具

- `tests/test_admin_api_test_batch_service.py`
- `tests/test_admin_api_test_cleanup_service.py`
- `tests/test_admin_api_test_repository.py`
- `tests/test_admin_market_test_routes.py`
- `tests/test_admin_market_test_service.py`
- `tests/test_api_doc_service.py`
- `tests/test_interface_spec_audit_tool.py`
- `tests/test_interface_test_params.py`
- `tests/test_market_interface_specs.py`
- `tests/test_sync_tushare_interface_specs_cli.py`
- `tests/test_tushare_spec_sync_service.py`
- `tests/fixtures/tushare_docs/etf_basic_385.md`
- `tests/fixtures/tushare_docs/income_33.md`

## 文档

- `docs/interface-spec-audit-current.json`
- `docs/INTERFACE_TESTER_SCHEME_B_DEPLOYMENT.md`
- `docs/INTERFACE_TESTER_SCHEME_B_TEST_RESULTS.md`
- `docs/INTERFACE_TESTER_SCHEME_B_PATCH_MANIFEST.md`
- `docs/superpowers/specs/2026-07-25-interface-tester-official-specs-design.md`
- `docs/superpowers/plans/2026-07-25-interface-tester-official-specs.md`

## 明确排除

- `.env`
- Token、密码、Cookie、密钥
- 数据库和数据文件
- 日志和测试运行结果目录
- `.venv`、第三方依赖和 IDE 配置
- `__pycache__`、`.pytest_cache`
