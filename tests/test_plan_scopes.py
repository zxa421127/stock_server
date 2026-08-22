# -*- coding: utf-8 -*-
import unittest

from services.plan_catalog import GENERAL_SCOPES, SPECIAL_SCOPES, scope_allowed


class PlanScopeTests(unittest.TestCase):
    def test_general_does_not_include_independent_or_kaipanla(self):
        self.assertIn("tushare:points15000:read", GENERAL_SCOPES)
        self.assertNotIn("tushare:independent:*", GENERAL_SCOPES)
        self.assertNotIn("market:kaipanla:read", GENERAL_SCOPES)

    def test_special_includes_general_independent_and_kaipanla(self):
        self.assertIn("tushare:points15000:read", SPECIAL_SCOPES)
        self.assertIn("tushare:independent:*", SPECIAL_SCOPES)
        self.assertIn("market:kaipanla:read", SPECIAL_SCOPES)
        self.assertNotIn("market:miniqmt:read", SPECIAL_SCOPES)
        self.assertNotIn("admin:sync", SPECIAL_SCOPES)

    def test_wildcards(self):
        self.assertTrue(scope_allowed("admin:sync", ["admin:*"]))
        self.assertTrue(scope_allowed("anything", ["*"]))
        self.assertTrue(scope_allowed("tushare:independent:realtime:read", ["tushare:independent:*"]))
        self.assertFalse(scope_allowed("market:kaipanla:read", GENERAL_SCOPES))


if __name__ == "__main__":
    unittest.main()
