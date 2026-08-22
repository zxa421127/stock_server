# -*- coding: utf-8 -*-
from pathlib import Path


def test_runtime_counting_code_has_no_stale_manual_interface_totals():
    checked = {
        "e2e_tests/core/auto_tests/catalog_count_test.py": (
            'expected = {"tushare": 138, "kaipanla": 2}',
            "target = 143 if \"miniqmt\" in providers else 140",
        ),
        "tools/sync_full_api_docs.py": ("== 139", "完整139接口"),
        "routes/user_routes.py": ("完整收录140个接口",),
        "routes/admin_api_doc_routes.py": ("完整139接口",),
        "services/api_doc_catalog.py": ("FULL_API_DOCS_TOTAL = 140",),
        "tests/test_full_api_docs.py": (
            "self.assertEqual(FULL_API_DOCS_TOTAL, 140)",
            "self.assertEqual(len(FULL_API_DOCS), 140)",
            "self.assertEqual(points, 119)",
            "self.assertEqual(independent, 19)",
            "self.assertEqual(kaipanla, 2)",
        ),
        "tests/test_tushare_catalog.py": ("self.assertEqual(len(names), 138)",),
        "tests/test_developer_plan_permissions.py": (
            "self.assertEqual(len(rows), 138)",
            "self.assertEqual(len(points), 119)",
            "self.assertEqual(len(independent), 19)",
        ),
        "tools/check_two_tier_plans.py": (
            "assert len(rows) == 138",
            "assert len(point_rows) == 119",
            "assert len(independent_rows) == 19",
        ),
    }
    for filename, forbidden_values in checked.items():
        source = Path(filename).read_text(encoding="utf-8")
        for value in forbidden_values:
            assert value not in source, f"{filename} still contains {value!r}"
