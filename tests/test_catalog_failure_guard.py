# -*- coding: utf-8 -*-
from pathlib import Path


def test_all_interface_test_rejects_zero_provider_run_and_supports_auto_confirm():
    source = Path("e2e_tests/core/all_data_interfaces_test.py").read_text(encoding="utf-8")
    assert "STOCK_TEST_AUTO_CONFIRM" in source
    assert "if not providers:" in source
    assert "if not refs:" in source
    assert '"生成时间"' in source


def test_catalog_count_does_not_report_zero_as_success_after_provider_500():
    source = Path("e2e_tests/core/auto_tests/catalog_count_test.py").read_text(encoding="utf-8")
    assert "if status != 200" in source
    assert "无法统计" in source
