# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.market_interface_spec_service import MarketInterfaceSpecService


class MarketInterfaceSpecServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name) / "interface_specs"
        self.service = MarketInterfaceSpecService(self.root)

    def test_seed_release_covers_current_140_interfaces(self):
        version = self.service.ensure_seed_release()
        specs = self.service.list_effective_specs()
        self.assertEqual(len(specs), 140)
        self.assertTrue(version)
        self.assertEqual({row["provider"] for row in specs}, {"tushare", "kaipanla"})
        stats = self.service.coverage_statistics()
        self.assertEqual(stats["total"], 140)
        self.assertEqual(stats["missing_spec"], 0)

    def test_daily_exposes_all_seed_inputs_and_outputs(self):
        self.service.ensure_seed_release()
        spec = self.service.get_effective_spec("tushare", "daily")
        self.assertIsNotNone(spec)
        names = {row["name"] for row in spec["input_params"]}
        self.assertTrue({"ts_code", "trade_date", "start_date", "end_date"}.issubset(names))
        output_names = {row["name"] for row in spec["output_fields"]}
        self.assertTrue({"ts_code", "trade_date", "open", "close", "vol", "amount"}.issubset(output_names))
        self.assertEqual(spec["official_doc_id"], 27)

    def test_kaipanla_history_has_triple_snapshot_enum(self):
        self.service.ensure_seed_release()
        spec = self.service.get_effective_spec("kaipanla", "morning_bidding_history")
        snapshot = next(row for row in spec["input_params"] if row["name"] == "snapshot_type")
        self.assertEqual(snapshot["enum_values"], ["auction", "post_open", "close"])
        self.assertEqual(snapshot["source"], "project_code")

    def test_parameter_validation_and_template_resolution(self):
        self.service.ensure_seed_release()
        converted = self.service.validate_params(
            "kaipanla", "morning_bidding_history",
            {"snapshot_type": "close", "limit": "500"},
        )
        self.assertEqual(converted["limit"], 500)
        with self.assertRaises(ValueError):
            self.service.validate_params("kaipanla", "morning_bidding_history", {"snapshot_type": "bad"})
        with self.assertRaises(ValueError):
            self.service.validate_params("tushare", "daily", {"not_a_param": "x"})
        resolved = self.service.resolve_templates({"trade_date": "${today}", "ts_code": "${sample_stock}"})
        self.assertEqual(len(resolved["trade_date"]), 8)
        self.assertEqual(resolved["ts_code"], "000001.SZ")

    def test_admin_can_save_batch_default_params_as_new_version(self):
        self.service.ensure_seed_release()
        before = self.service.current_version()
        release = self.service.save_interface_preset(
            "tushare", "daily",
            {"trade_date": "20260724"},
            name="管理员默认参数", updated_by="admin",
        )
        self.assertNotEqual(release["version"], before)
        self.assertEqual(
            self.service.default_test_params("tushare", "daily"),
            {"trade_date": "20260724"},
        )
        spec = self.service.get_effective_spec("tushare", "daily")
        self.assertEqual(spec["presets"][0]["name"], "管理员默认参数")

    def test_candidate_required_param_blocks_publish_until_admin_saves_valid_preset(self):
        self.service.ensure_seed_release()
        candidate_version = "candidate-required-preset"
        candidate_dir = self.root / "candidates" / candidate_version
        candidate_dir.mkdir(parents=True)
        daily = dict(self.service.get_effective_spec("tushare", "daily"))
        daily["input_params"] = [dict(row) for row in daily["input_params"]]
        daily["input_params"][0]["required"] = True
        daily["official_verified"] = True
        daily["parse_warnings"] = []
        daily["publish_eligible"] = False
        daily["presets"] = [{"name": "invalid", "params": {"trade_date": "20260724"}}]
        (candidate_dir / "effective_specs.json").write_text(
            json.dumps([daily], ensure_ascii=False), encoding="utf-8"
        )
        (candidate_dir / "diffs.json").write_text("[]", encoding="utf-8")
        (candidate_dir / "manifest.json").write_text(
            json.dumps({"version": candidate_version}), encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            self.service.publish_candidate_selection(
                candidate_version, [("tushare", "daily")],
                published_by="admin", note="invalid preset",
            )
        updated = self.service.update_candidate_preset(
            candidate_version, "tushare", "daily",
            {"ts_code": "000001.SZ"}, name="有效参数", updated_by="admin",
        )
        self.assertTrue(updated["publish_eligible"])
        release = self.service.publish_candidate_selection(
            candidate_version, [("tushare", "daily")],
            published_by="admin", note="valid preset",
        )
        self.assertEqual(release["selected_count"], 1)
        self.assertEqual(
            self.service.default_test_params("tushare", "daily"),
            {"ts_code": "000001.SZ"},
        )

    def test_admin_can_complete_candidate_normalization_rules_without_altering_official_fields(self):
        self.service.ensure_seed_release()
        candidate_version = "candidate-overrides"
        candidate_dir = self.root / "candidates" / candidate_version
        candidate_dir.mkdir(parents=True)
        daily = dict(self.service.get_effective_spec("tushare", "daily"))
        daily["input_params"] = [dict(row) for row in daily["input_params"]]
        daily["output_fields"] = [dict(row) for row in daily["output_fields"]]
        daily["official_verified"] = True
        daily["parse_warnings"] = []
        daily["blocking_change"] = False
        daily["presets"] = [{"name": "valid", "params": {"trade_date": "20260724"}}]
        (candidate_dir / "effective_specs.json").write_text(
            json.dumps([daily], ensure_ascii=False), encoding="utf-8"
        )
        (candidate_dir / "diffs.json").write_text("[]", encoding="utf-8")
        (candidate_dir / "manifest.json").write_text(
            json.dumps({"version": candidate_version}), encoding="utf-8"
        )

        original_type = next(
            row["official_type"] for row in daily["input_params"] if row["name"] == "ts_code"
        )
        updated = self.service.update_candidate_overrides(
            candidate_version, "tushare", "daily",
            input_overrides={
                "ts_code": {
                    "normalized_type": "string", "multiple": False,
                    "pattern": r"[0-9]{6}\.(SZ|SH|BJ)", "widget": "text",
                }
            },
            output_overrides={"amount": {"unit": "千元", "nullable": "unknown"}},
            validation_rules=[{
                "type": "at_least_one",
                "fields": ["ts_code", "trade_date", "start_date", "end_date"],
                "message": "代码或日期条件至少填写一个",
            }],
            updated_by="admin",
        )
        ts_code = next(row for row in updated["input_params"] if row["name"] == "ts_code")
        amount = next(row for row in updated["output_fields"] if row["name"] == "amount")
        self.assertEqual(ts_code["official_type"], original_type)
        self.assertEqual(ts_code["pattern"], r"[0-9]{6}\.(SZ|SH|BJ)")
        self.assertEqual(amount["unit"], "千元")
        self.assertEqual(updated["validation_rules"][0]["type"], "at_least_one")
        self.assertTrue(updated["publish_eligible"])
        with self.assertRaisesRegex(ValueError, "官方字段"):
            self.service.update_candidate_overrides(
                candidate_version, "tushare", "daily",
                input_overrides={"ts_code": {"official_type": "int"}},
                output_overrides={}, validation_rules=updated["validation_rules"],
                updated_by="admin",
            )

    def test_extended_parameter_rule_types_are_enforced(self):
        rules = [
            {
                "type": "required_if", "field": "end_date",
                "condition_field": "mode", "condition_values": ["range"],
                "message": "范围模式必须填写结束日期",
            },
            {"type": "single_value_only", "field": "ts_code", "message": "只允许一个代码"},
            {"type": "max_items", "field": "codes", "max_items": 2, "message": "最多两个代码"},
            {
                "type": "datetime_range", "start_field": "start_time",
                "end_field": "end_time", "message": "开始时间不能晚于结束时间",
            },
        ]
        with self.assertRaisesRegex(ValueError, "结束日期"):
            self.service._validate_rules(rules, {"mode": "range"})
        with self.assertRaisesRegex(ValueError, "只允许一个代码"):
            self.service._validate_rules(rules, {"ts_code": "000001.SZ,000002.SZ"})
        with self.assertRaisesRegex(ValueError, "最多两个代码"):
            self.service._validate_rules(rules, {"codes": ["a", "b", "c"]})
        with self.assertRaisesRegex(ValueError, "开始时间"):
            self.service._validate_rules(
                rules, {"start_time": "2026-07-24 10:00:00", "end_time": "2026-07-24 09:00:00"}
            )

    def test_selected_candidate_publish_is_atomic_and_keeps_unselected_current(self):
        self.service.ensure_seed_release()
        current = self.service.get_effective_spec("tushare", "daily")
        candidate_version = "candidate-test"
        candidate_dir = self.root / "candidates" / candidate_version
        candidate_dir.mkdir(parents=True)
        daily = dict(current)
        daily["title"] = "A股日线行情（候选）"
        daily["official_verified"] = True
        daily["parse_warnings"] = []
        daily["publish_eligible"] = True
        stock = dict(self.service.get_effective_spec("tushare", "stock_basic"))
        stock["title"] = "股票列表（候选）"
        stock["official_verified"] = True
        stock["parse_warnings"] = []
        stock["publish_eligible"] = True
        (candidate_dir / "effective_specs.json").write_text(
            json.dumps([daily, stock], ensure_ascii=False), encoding="utf-8"
        )
        release = self.service.publish_candidate_selection(
            candidate_version, [("tushare", "daily")], published_by="admin", note="test"
        )
        self.assertNotEqual(release["version"], self.service.SEED_VERSION)
        self.assertEqual(self.service.get_effective_spec("tushare", "daily")["title"], "A股日线行情（候选）")
        self.assertNotEqual(self.service.get_effective_spec("tushare", "stock_basic")["title"], "股票列表（候选）")
        self.assertEqual(release["selected_count"], 1)


    def test_etf_basic_bootstrap_matches_current_official_contract(self):
        spec = self.service.get_effective_spec("tushare", "etf_basic")
        self.assertEqual([row["name"] for row in spec["input_params"]], [
            "ts_code", "index_code", "list_date", "list_status", "exchange", "mgr",
        ])
        self.assertEqual([row["name"] for row in spec["output_fields"]], [
            "ts_code", "csname", "extname", "cname", "index_code", "index_name",
            "setup_date", "list_date", "list_status", "exchange", "mgr_name",
            "custod_name", "mgt_fee", "etf_type",
        ])
        self.assertTrue(all(not row["required"] for row in spec["input_params"]))
        self.assertIn("8000", spec["permission_label"])
        self.assertTrue(spec["official_verified"])


    def test_etf_index_bootstrap_matches_current_official_contract(self):
        spec = self.service.get_effective_spec("tushare", "etf_index")
        self.assertEqual([row["name"] for row in spec["input_params"]], [
            "ts_code", "pub_date", "base_date",
        ])
        self.assertEqual([row["name"] for row in spec["output_fields"]], [
            "ts_code", "indx_name", "indx_csname", "pub_party_name",
            "pub_date", "base_date", "bp", "adj_circle",
        ])
        self.assertEqual(spec["output_fields"][6]["official_type"], "float")
        self.assertIn("8000", spec["permission_text"] or spec["permission_label"])
        self.assertIn("5000", spec["limit_text"] or spec["description"])
        self.assertTrue(spec["official_verified"])

    def test_incomplete_candidate_cannot_be_published(self):
        self.service.ensure_seed_release()
        candidate_version = "candidate-incomplete-sync"
        candidate_dir = self.root / "candidates" / candidate_version
        candidate_dir.mkdir(parents=True)
        daily = dict(self.service.get_effective_spec("tushare", "daily"))
        daily["official_verified"] = True
        daily["parse_warnings"] = []
        daily["publish_eligible"] = True
        (candidate_dir / "effective_specs.json").write_text(
            json.dumps([daily], ensure_ascii=False), encoding="utf-8"
        )
        (candidate_dir / "diffs.json").write_text("[]", encoding="utf-8")
        (candidate_dir / "manifest.json").write_text(
            json.dumps({
                "version": candidate_version,
                "complete_sync": False,
                "target_count": 138,
                "success_count": 113,
                "error_count": 25,
            }),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "同步未完整"):
            self.service.publish_candidate_selection(
                candidate_version, [("tushare", "daily")],
                published_by="admin", note="must block partial sync",
            )

    def test_fields_is_not_a_user_business_parameter(self):
        with self.assertRaisesRegex(ValueError, "未定义参数.*fields"):
            self.service.validate_params(
                "tushare", "daily",
                {"trade_date": "20260724", "fields": "ts_code"},
            )



def test_seed_specs_never_expose_tushare_fields_as_business_input(tmp_path):
    service = MarketInterfaceSpecService(tmp_path / "specs")
    rows = service._build_seed_specs()
    for spec in rows:
        if spec.get("provider") != "tushare":
            continue
        assert "fields" not in [row.get("name") for row in spec.get("input_params", [])]
        for preset in spec.get("presets", []):
            assert "fields" not in (preset.get("params") or {})


if __name__ == "__main__":
    unittest.main()


def test_strict_batch_eligibility_requires_official_tushare_but_accepts_kaipanla(tmp_path):
    service = MarketInterfaceSpecService(tmp_path / "specs")
    service.ensure_seed_release()
    ok, issues = service.batch_eligibility("tushare", "daily")
    assert not ok
    assert any("官网" in issue for issue in issues)
    ok, issues = service.batch_eligibility("kaipanla", "morning_bidding_history")
    assert ok
    assert issues == []
    report = service.validate_all_specs(require_official_tushare=True)
    assert report["total"] == 140
    assert report["invalid_count"] == 135

def test_ci_daily_bootstrap_matches_current_official_contract(tmp_path):
    service = MarketInterfaceSpecService(tmp_path / "specs")
    service.ensure_seed_release()
    spec = service.get_effective_spec("tushare", "ci_daily")
    assert [row["name"] for row in spec["input_params"]] == [
        "ts_code", "trade_date", "start_date", "end_date",
    ]
    assert [row["name"] for row in spec["output_fields"]] == [
        "ts_code", "trade_date", "open", "low", "high", "close",
        "pre_close", "change", "pct_change", "vol", "amount",
    ]
    assert all(row["official_type"] == "float" for row in spec["output_fields"][2:])
    assert spec["description"] == "获取中信行业指数日线行情"
    assert "5000" in spec["permission_text"]
    assert "4000" in spec["limit_text"]
    assert spec["official_verified"] is True
