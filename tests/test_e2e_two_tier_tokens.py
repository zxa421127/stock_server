# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_CORE = ROOT / "e2e_tests" / "core"
if str(TEST_CORE) not in sys.path:
    sys.path.insert(0, str(TEST_CORE))

from auto_tests import common


class E2ETwoTierTokenTests(unittest.TestCase):
    def _load(self, payload: dict[str, str]) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as tempdir:
            token_file = Path(tempdir) / "membership_test_tokens.json"
            token_file.write_text(json.dumps(payload), encoding="utf-8")
            old_path = common.TOKEN_FILE
            common.TOKEN_FILE = token_file
            try:
                return common.load_tokens()
            finally:
                common.TOKEN_FILE = old_path

    def test_new_general_special_file_exposes_legacy_aliases(self):
        tokens = self._load({
            "general": "general-token",
            "special": "special-token",
            "admin": "admin-token",
            "expired": "expired-token",
            "disabled": "disabled-token",
            "unsubscribed": "unsubscribed-token",
        })
        self.assertEqual(tokens["history"], "general-token")
        self.assertEqual(tokens["realtime"], "special-token")

    def test_legacy_history_realtime_file_exposes_current_aliases(self):
        tokens = self._load({
            "history": "history-token",
            "realtime": "realtime-token",
            "admin": "admin-token",
            "expired": "expired-token",
            "disabled": "disabled-token",
            "unsubscribed": "unsubscribed-token",
        })
        self.assertEqual(tokens["general"], "history-token")
        self.assertEqual(tokens["special"], "realtime-token")

    def test_current_test_modules_do_not_require_old_role_keys(self):
        paths = [
            ROOT / "e2e_tests/core/auto_tests/permission_matrix_test.py",
            ROOT / "e2e_tests/core/auto_tests/catalog_count_test.py",
            ROOT / "e2e_tests/core/auto_tests/cache_test.py",
            ROOT / "e2e_tests/core/auto_tests/full_interface_test.py",
            ROOT / "e2e_tests/core/all_data_interfaces_test.py",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotIn('tokens["history"]', text)
                self.assertNotIn('tokens["realtime"]', text)


if __name__ == "__main__":
    unittest.main()
