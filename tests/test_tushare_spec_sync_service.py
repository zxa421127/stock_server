# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.market_interface_spec_service import MarketInterfaceSpecService
from services.tushare_spec_sync_service import (
    TushareSpecSyncService,
    parse_tushare_document_html,
    parse_tushare_official_document,
    diff_interface_specs,
)

DAILY_HTML = """
<html><body>
<h2>A股日线行情</h2>
<p>接口：daily，可以通过数据工具调试和查看数据</p>
<p>数据说明：交易日每天15点～16点之间入库。</p>
<p>调取说明：每次6000条数据。</p>
<h3>输入参数</h3>
<table><tr><th>名称</th><th>类型</th><th>必选</th><th>描述</th></tr>
<tr><td>ts_code</td><td>str</td><td>N</td><td>股票代码</td></tr>
<tr><td>trade_date</td><td>str</td><td>N</td><td>交易日期（YYYYMMDD）</td></tr>
<tr><td>start_date</td><td>str</td><td>N</td><td>开始日期</td></tr>
<tr><td>end_date</td><td>str</td><td>N</td><td>结束日期</td></tr></table>
<h3>输出参数</h3>
<table><tr><th>名称</th><th>类型</th><th>默认显示</th><th>描述</th></tr>
<tr><td>ts_code</td><td>str</td><td>Y</td><td>股票代码</td></tr>
<tr><td>trade_date</td><td>str</td><td>Y</td><td>交易日期</td></tr>
<tr><td>open</td><td>float</td><td>Y</td><td>开盘价</td></tr>
<tr><td>close</td><td>float</td><td>Y</td><td>收盘价</td></tr>
<tr><td>ah_amount</td><td>float</td><td>N</td><td>盘后成交额</td></tr></table>
</body></html>
"""


ETF_INDEX_COMPACT_MARKDOWN = """## ETF基准指数列表 ---- 接口：etf_index 描述：获取ETF基准指数列表信息 限量：单次请求最大返回5000行数据（当前未超过2000个） 权限：用户积累8000积分可调取，具体请参阅积分获取办法
**输入参数** 名称 | 类型 | 必选 | 描述 ---- | ----- | ---- | ---- ts_code | str | N | 指数代码 pub_date | str | N | 发布日期（格式：YYYYMMDD） base_date | str | N | 指数基期（格式：YYYYMMDD）
**输出参数** 名称 | 类型 | 默认显示 | 描述 --- | ---- | ---- | ---- ts_code | str | Y | 指数代码 indx_name | str | Y | 指数全称 indx_csname | str | Y | 指数简称 pub_party_name | str | Y | 指数发布机构 pub_date | str | Y | 指数发布日期 base_date | str | Y | 指数基日 bp | float | Y | 指数基点(点) adj_circle | str | Y | 指数成份证券调整周期
**接口示例** pro.etf_index()
"""

class FakeResponse:
    def __init__(self, text, status_code=200, content_type="text/markdown"):
        self.text = text
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []
        self.headers = {}

    def get(self, url, timeout=None):
        self.urls.append(url)
        if not self.responses:
            raise AssertionError("unexpected request")
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class TushareSpecSyncServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.specs = MarketInterfaceSpecService(Path(self.tempdir.name) / "specs")
        self.specs.ensure_seed_release()
        self.sync = TushareSpecSyncService(self.specs)


    def test_markdown_parser_extracts_etf_official_contract(self):
        text = (Path(__file__).parent / "fixtures" / "tushare_docs" / "etf_basic_385.md").read_text(encoding="utf-8")
        raw = parse_tushare_official_document(text, "https://tushare.pro/wctapi/documents/385.md")
        self.assertEqual(raw["api_name"], "etf_basic")
        self.assertEqual(raw["official_doc_id"], 385)
        self.assertEqual(len(raw["inputs"]), 6)
        self.assertEqual(len(raw["outputs"]), 14)
        self.assertEqual([row["name"] for row in raw["inputs"]], [
            "ts_code", "index_code", "list_date", "list_status", "exchange", "mgr",
        ])
        self.assertEqual([row["name"] for row in raw["outputs"]], [
            "ts_code", "csname", "extname", "cname", "index_code", "index_name",
            "setup_date", "list_date", "list_status", "exchange", "mgr_name",
            "custod_name", "mgt_fee", "etf_type",
        ])
        self.assertIn("8000", raw["permission_text"])
        self.assertIn("5000", raw["limit_text"])
        self.assertEqual(raw["parse_warnings"], [])

    def test_markdown_parser_preserves_long_output_order(self):
        text = (Path(__file__).parent / "fixtures" / "tushare_docs" / "income_33.md").read_text(encoding="utf-8")
        raw = parse_tushare_official_document(text, "https://tushare.pro/wctapi/documents/33.md")
        self.assertEqual([row["name"] for row in raw["outputs"]], [
            "ts_code", "ann_date", "revenue", "total_cogs", "n_income", "update_flag",
        ])
        self.assertTrue(raw["inputs"][0]["required"])
        self.assertEqual(raw["outputs"][2]["official_type"], "float")

    def test_markdown_parser_rejects_duplicate_output_fields(self):
        text = """## 重复字段\n接口：demo\n**输入参数**\n|名称|类型|必选|描述|\n|---|---|---|---|\n**输出参数**\n|名称|类型|默认显示|描述|\n|---|---|---|---|\n|ts_code|str|Y|代码|\n|ts_code|str|Y|重复|"""
        with self.assertRaisesRegex(ValueError, "重复输出字段"):             parse_tushare_official_document(text, "https://tushare.pro/wctapi/documents/999.md")

    def test_official_markdown_url_uses_document_id(self):
        spec = self.specs.get_effective_spec("tushare", "etf_basic")
        self.assertEqual(
            self.sync.official_markdown_url(spec),
            "https://tushare.pro/wctapi/documents/385.md",
        )

    def test_sync_prefers_markdown_and_records_complete_manifest(self):
        text = (Path(__file__).parent / "fixtures" / "tushare_docs" / "etf_basic_385.md").read_text(encoding="utf-8")
        session = FakeSession([FakeResponse(text)])
        service = TushareSpecSyncService(self.specs, session=session)
        result = service.sync_official_specs(["etf_basic"], candidate_version="candidate-etf")
        self.assertEqual(result["target_count"], 1)
        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["fetch_error_count"], 0)
        self.assertEqual(result["parse_error_count"], 0)
        self.assertEqual(result["failed_interfaces"], [])
        self.assertTrue(result["complete_sync"])
        self.assertEqual(result["coverage_percent"], 100.0)
        self.assertIn("/wctapi/documents/385.md", session.urls[0])
        candidate = self.specs.load_candidate("candidate-etf")["specs"][0]
        self.assertEqual(len(candidate["input_params"]), 6)
        self.assertEqual(len(candidate["output_fields"]), 14)

    def test_sync_falls_back_to_html_after_markdown_failure(self):
        session = FakeSession([RuntimeError("markdown unavailable"), RuntimeError("markdown unavailable"), FakeResponse(DAILY_HTML, content_type="text/html")])
        service = TushareSpecSyncService(self.specs, session=session)
        result = service.sync_official_specs(["daily"], candidate_version="candidate-daily-fallback")
        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["fetch_error_count"], 0)
        self.assertEqual(len(session.urls), 3)
        self.assertIn("/wctapi/documents/", session.urls[0])
        self.assertIn("/document/2?doc_id=", session.urls[-1])

    def test_sync_isolates_parse_errors(self):
        bad = """## bad\n接口：etf_basic\n**输入参数**\n|名称|类型|必选|描述|\n|---|---|---|---|\n**输出参数**\n|名称|类型|默认显示|描述|\n|---|---|---|---|\n|x|str|Y|x|\n|x|str|Y|dup|"""
        session = FakeSession([FakeResponse(bad)])
        service = TushareSpecSyncService(self.specs, session=session)
        result = service.sync_official_specs(["etf_basic"], candidate_version="candidate-bad")
        self.assertEqual(result["success_count"], 0)
        self.assertEqual(result["parse_error_count"], 1)
        self.assertFalse(result["complete_sync"])
        self.assertEqual(result["coverage_percent"], 0.0)
        self.assertEqual(result["failed_interfaces"][0]["api_name"], "etf_basic")


    def test_markdown_parser_accepts_official_empty_input_table(self):
        text = """## 无输入接口
接口：no_input_demo
描述：无需业务输入参数
**输入参数**
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
**输出参数**
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 代码 |
"""
        raw = parse_tushare_official_document(
            text, "https://tushare.pro/wctapi/documents/999.md",
        )
        self.assertEqual(raw["inputs"], [])
        self.assertEqual([row["name"] for row in raw["outputs"]], ["ts_code"])
        self.assertNotIn("未识别输入参数表", raw["parse_warnings"])

    def test_markdown_parser_handles_compact_single_line_tables(self):
        raw = parse_tushare_official_document(
            ETF_INDEX_COMPACT_MARKDOWN,
            "https://tushare.pro/wctapi/documents/386.md",
        )
        self.assertEqual(raw["api_name"], "etf_index")
        self.assertEqual([row["name"] for row in raw["inputs"]], [
            "ts_code", "pub_date", "base_date",
        ])
        self.assertEqual([row["name"] for row in raw["outputs"]], [
            "ts_code", "indx_name", "indx_csname", "pub_party_name",
            "pub_date", "base_date", "bp", "adj_circle",
        ])
        self.assertEqual(raw["outputs"][6]["official_type"], "float")
        self.assertEqual(raw["parse_warnings"], [])

    def test_fetch_and_parse_falls_back_when_markdown_parsing_fails(self):
        bad_markdown = "## broken\n接口：daily\n**输入参数**\nno table\n**输出参数**\nno table"
        session = FakeSession([
            FakeResponse(bad_markdown),
            FakeResponse(DAILY_HTML, content_type="text/html"),
        ])
        service = TushareSpecSyncService(self.specs, session=session)
        current = self.specs.get_effective_spec("tushare", "daily")
        raw, document = service.fetch_and_parse_official_spec(current)
        self.assertEqual(raw["api_name"], "daily")
        self.assertEqual(len(raw["inputs"]), 4)
        self.assertEqual(document["content_type"], "text/html")
        self.assertEqual(len(session.urls), 2)

    def test_parser_extracts_complete_official_tables(self):
        raw = parse_tushare_document_html(DAILY_HTML, "https://tushare.pro/document/2?doc_id=27")
        self.assertEqual(raw["api_name"], "daily")
        self.assertEqual(raw["official_title"], "A股日线行情")
        self.assertEqual([row["name"] for row in raw["inputs"]], ["ts_code", "trade_date", "start_date", "end_date"])
        self.assertEqual([row["name"] for row in raw["outputs"]], ["ts_code", "trade_date", "open", "close", "ah_amount"])
        self.assertFalse(raw["inputs"][0]["required"])
        self.assertFalse(raw["outputs"][-1]["default_display"])

    def test_diff_classifies_blocking_and_nonblocking_changes(self):
        old = self.specs.get_effective_spec("tushare", "daily")
        raw = parse_tushare_document_html(DAILY_HTML, old["official_url"])
        new = self.sync.build_effective_spec(old, raw)
        diffs = diff_interface_specs(old, new)
        self.assertTrue(any(row["change_type"] == "input_added" and row["field"] == "trade_date" for row in diffs) is False)
        modified = dict(new)
        modified["input_params"] = [dict(row) for row in new["input_params"]]
        modified["input_params"][0]["required"] = True
        severe = diff_interface_specs(new, modified)
        self.assertTrue(any(row["severity"] == "blocking" for row in severe))
        added = dict(new)
        added["output_fields"] = [*new["output_fields"], {"name": "new_field", "official_type": "str", "normalized_type": "string", "default_display": False, "description": "x"}]
        warning = diff_interface_specs(new, added)
        self.assertTrue(any(row["change_type"] == "output_added" and row["severity"] == "warning" for row in warning))

    def test_initial_official_verification_creates_candidate_even_without_field_diffs(self):
        import json
        seed = self.specs.get_effective_spec("tushare", "daily")
        raw = parse_tushare_document_html(DAILY_HTML, seed["official_url"])
        matching = self.sync.build_effective_spec(seed, raw)
        matching["official_verified"] = False
        matching["change_status"] = "current"
        rows = self.specs._load_specs()
        for index, row in enumerate(rows):
            if row.get("provider") == "tushare" and row.get("api_name") == "daily":
                rows[index] = matching
                break
        version = "matching-unverified"
        release_dir = self.specs.releases_dir / version
        release_dir.mkdir(parents=True)
        (release_dir / "effective_specs.json").write_text(
            json.dumps(rows, ensure_ascii=False), encoding="utf-8"
        )
        (release_dir / "manifest.json").write_text(
            json.dumps({"version": version}), encoding="utf-8"
        )
        self.specs.current_file.write_text(
            json.dumps({"version": version}), encoding="utf-8"
        )
        self.specs._cache_version = ""

        result = self.sync.create_candidate_from_html_map(
            {"daily": DAILY_HTML}, candidate_version="candidate-initial-verification"
        )
        self.assertEqual(result["changed_count"], 1)
        candidate = self.specs.load_candidate(result["version"])["specs"][0]
        self.assertTrue(candidate["official_verified"])
        self.assertEqual(candidate["api_name"], "daily")

    def test_official_candidate_strips_legacy_fields_from_presets(self):
        text = (Path(__file__).parent / "fixtures" / "tushare_docs" / "etf_basic_385.md").read_text(encoding="utf-8")
        current = self.specs.get_effective_spec("tushare", "etf_basic")
        current["presets"] = [{"name": "legacy", "params": {"list_status": "L", "fields": "ts_code"}}]
        raw = parse_tushare_official_document(text, "https://tushare.pro/wctapi/documents/385.md")
        effective = self.sync.build_effective_spec(current, raw)
        self.assertEqual(effective["presets"][0]["params"], {"list_status": "L"})

    def test_candidate_generation_does_not_change_current_release(self):
        before = self.specs.current_version()
        result = self.sync.create_candidate_from_html_map({"daily": DAILY_HTML})
        self.assertEqual(self.specs.current_version(), before)
        self.assertEqual(result["changed_count"], 1)
        candidate = self.specs.load_candidate(result["version"])
        self.assertEqual(len(candidate["specs"]), 1)
        row = candidate["specs"][0]
        self.assertTrue(row["official_verified"])
        self.assertTrue(row["publish_eligible"])
        self.assertEqual(row["official_doc_id"], 27)


if __name__ == "__main__":
    unittest.main()

class TushareCiDailyOfficialContractTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.specs = MarketInterfaceSpecService(Path(self.tempdir.name) / "specs")
        self.specs.ensure_seed_release()
        self.sync = TushareSpecSyncService(self.specs)
        self.text = (Path(__file__).parent / "fixtures" / "tushare_docs" / "ci_daily_308.md").read_text(encoding="utf-8")

    def test_ci_daily_parser_matches_official_contract(self):
        raw = parse_tushare_official_document(self.text, "https://tushare.pro/wctapi/documents/308.md")
        self.assertEqual(raw["api_name"], "ci_daily")
        self.assertEqual([row["name"] for row in raw["inputs"]], [
            "ts_code", "trade_date", "start_date", "end_date",
        ])
        self.assertEqual([row["name"] for row in raw["outputs"]], [
            "ts_code", "trade_date", "open", "low", "high", "close",
            "pre_close", "change", "pct_change", "vol", "amount",
        ])
        self.assertTrue(all(row["official_type"] == "float" for row in raw["outputs"][2:]))
        self.assertEqual(raw["outputs"][2]["description"], "开盘点位")
        self.assertIn("5000", raw["permission_text"])
        self.assertIn("4000", raw["limit_text"])
        effective = self.sync.build_effective_spec(
            self.specs.get_effective_spec("tushare", "ci_daily"), raw,
        )
        self.assertEqual(
            [row["normalized_type"] for row in effective["output_fields"]],
            ["string", "string", *(["number"] * 9)],
        )

    def test_document_hashes_are_stable_and_semantic(self):
        first = parse_tushare_official_document(self.text, "https://tushare.pro/wctapi/documents/308.md")
        second = parse_tushare_official_document(self.text, "https://tushare.pro/wctapi/documents/308.md")
        self.assertEqual(first["raw_content_hash"], second["raw_content_hash"])
        self.assertEqual(first["semantic_spec_hash"], second["semantic_spec_hash"])
        self.assertEqual(first["source_hash"], first["semantic_spec_hash"])
        public = parse_tushare_official_document(
            self.text, "https://tushare.pro/document/2?doc_id=308",
        )
        self.assertEqual(first["semantic_spec_hash"], public["semantic_spec_hash"])

    def test_diff_detects_metadata_order_and_default_display_changes(self):
        current = self.sync.build_effective_spec(
            self.specs.get_effective_spec("tushare", "ci_daily"),
            parse_tushare_official_document(self.text, "https://tushare.pro/wctapi/documents/308.md"),
        )
        changed = dict(current)
        changed["permission_text"] = "积分：6000积分"
        changed["limit_text"] = "限量：单次最大3000条"
        changed["output_fields"] = [dict(row) for row in current["output_fields"]]
        changed["output_fields"][0]["default_display"] = False
        changed["output_fields"] = [changed["output_fields"][1], changed["output_fields"][0], *changed["output_fields"][2:]]
        diffs = diff_interface_specs(current, changed)
        types = {row["change_type"] for row in diffs}
        self.assertIn("permission_text_changed", types)
        self.assertIn("limit_text_changed", types)
        self.assertIn("output_order_changed", types)
        self.assertIn("output_default_display_changed", types)

class TushareLegacyOfficialFormatTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.specs = MarketInterfaceSpecService(Path(self.tempdir.name) / "specs")
        self.specs.ensure_seed_release()
        self.sync = TushareSpecSyncService(self.specs)

    def test_markdown_parser_accepts_three_column_output_table(self):
        text = """## 指数日线行情
接口：index_daily
描述：获取各类指数每日行情
**输入参数**
名称 | 类型 | 必选 | 描述
--- | --- | --- | ---
ts_code | str | Y | 指数代码
trade_date | str | N | 交易日期
**输出参数**
名称 | 类型 | 描述
--- | --- | ---
ts_code | str | TS指数代码
trade_date | str | 交易日
close | float | 收盘点位
**接口使用**
"""
        raw = parse_tushare_official_document(text, "https://tushare.pro/wctapi/documents/95.md")
        self.assertEqual(raw["api_name"], "index_daily")
        self.assertEqual([row["name"] for row in raw["outputs"]], ["ts_code", "trade_date", "close"])
        self.assertTrue(all(row["default_display"] for row in raw["outputs"]))
        self.assertTrue(all(row["default_display_inferred"] for row in raw["outputs"]))
        self.assertEqual(raw["outputs"][2]["description"], "收盘点位")
        self.assertEqual(raw["parse_warnings"], [])

    def test_markdown_parser_accepts_default_output_header_alias(self):
        text = """## 股票曾用名
接口：namechange
**输入参数**
名称 | 类型 | 必选 | 描述
--- | --- | --- | ---
ts_code | str | N | TS代码
**输出参数**
名称 | 类型 | 默认输出 | 描述
--- | --- | --- | ---
ts_code | str | Y | TS代码
name | str | Y | 证券名称
"""
        raw = parse_tushare_official_document(text, "https://tushare.pro/wctapi/documents/100.md")
        self.assertEqual([row["name"] for row in raw["outputs"]], ["ts_code", "name"])
        self.assertTrue(raw["outputs"][0]["default_display"])
        self.assertFalse(raw["outputs"][0]["default_display_inferred"])
        self.assertEqual(raw["parse_warnings"], [])

    def test_compact_parser_accepts_must_header(self):
        text = """## 上市公司基本信息 ---- 接口：stock_company 描述：获取上市公司基础信息 **输入参数** 名称 | 类型 | 必须 | 描述 --- | ---- | ---- | ---- ts_code | str | N | 股票代码 exchange | str | N | 交易所代码 **输出参数** 名称 | 类型 | 默认显示 | 描述 --- | ---- | ---- | ---- ts_code | str | Y | 股票代码 com_name | str | Y | 公司全称 **接口示例**"""
        raw = parse_tushare_official_document(text, "https://tushare.pro/wctapi/documents/112.md")
        self.assertEqual([row["name"] for row in raw["inputs"]], ["ts_code", "exchange"])
        self.assertEqual([row["name"] for row in raw["outputs"]], ["ts_code", "com_name"])
        self.assertEqual(raw["parse_warnings"], [])

    def test_html_parser_accepts_three_column_output_table(self):
        html = """<html><body><h2>复权因子</h2><p>接口：adj_factor</p>
        <h3>输入参数</h3><table><tr><th>名称</th><th>类型</th><th>必选</th><th>描述</th></tr>
        <tr><td>ts_code</td><td>str</td><td>N</td><td>股票代码</td></tr></table>
        <h3>输出参数</h3><table><tr><th>名称</th><th>类型</th><th>描述</th></tr>
        <tr><td>ts_code</td><td>str</td><td>股票代码</td></tr>
        <tr><td>adj_factor</td><td>float</td><td>复权因子</td></tr></table></body></html>"""
        raw = parse_tushare_document_html(html, "https://tushare.pro/document/2?doc_id=28")
        self.assertEqual([row["name"] for row in raw["outputs"]], ["ts_code", "adj_factor"])
        self.assertTrue(raw["outputs"][0]["default_display_inferred"])
        self.assertEqual(raw["parse_warnings"], [])

    def test_pro_bar_is_official_dynamic_output_contract(self):
        text = """## A股复权行情
**接口名称** ：pro_bar
**接口说明** ：复权行情通过通用行情接口实现，输出字段随资产类别、频率和ma参数变化。
**接口参数**
名称 | 类型 | 必选 | 描述
--- | --- | --- | ---
ts_code | str | Y | 证券代码
start_date | str | N | 开始日期
end_date | str | N | 结束日期
asset | str | Y | 资产类别
adj | str | N | 复权类型
freq | str | Y | 数据频度
ma | list | N | 均线
**接口用例**
"""
        raw = parse_tushare_official_document(text, "https://tushare.pro/wctapi/documents/146.md")
        self.assertEqual(raw["api_name"], "pro_bar")
        self.assertEqual(len(raw["inputs"]), 7)
        self.assertEqual(raw["outputs"], [])
        self.assertEqual(raw["output_schema_mode"], "dynamic")
        self.assertNotIn("未识别输出参数表", raw["parse_warnings"])
        effective = self.sync.build_effective_spec(self.specs.get_effective_spec("tushare", "pro_bar"), raw)
        self.assertTrue(effective["official_verified"])
        self.assertEqual(effective["output_schema_mode"], "dynamic")
        self.assertEqual(effective["spec_status"], "complete")
        self.assertEqual(effective["output_fields"], [])
        self.assertEqual(effective["publish_issues"], [])

class TushareCompactThreeColumnOutputTests(unittest.TestCase):
    def test_compact_single_line_three_column_output_table(self):
        text = """## 港股通十大成交股 ---- 接口：ggt_top10 描述：获取港股通每日成交数据 **输入参数** 名称 | 类型 | 必选 | 描述 ---- | ----- | ---- | ---- ts_code | str | N | 股票代码 trade_date | str | N | 交易日期 **输出参数** 名称 | 类型 | 描述 --- | ---- | ---- trade_date | str | 交易日期 ts_code | str | 股票代码 name | str | 股票名称 close | float | 收盘价 **接口用法**"""
        raw = parse_tushare_official_document(
            text, "https://tushare.pro/wctapi/documents/49.md",
        )
        self.assertEqual([row["name"] for row in raw["inputs"]], ["ts_code", "trade_date"])
        self.assertEqual([row["name"] for row in raw["outputs"]], ["trade_date", "ts_code", "name", "close"])
        self.assertEqual(raw["outputs"][3]["official_type"], "float")
        self.assertEqual(raw["outputs"][3]["description"], "收盘价")
        self.assertTrue(all(row["default_display_inferred"] for row in raw["outputs"]))
        self.assertEqual(raw["parse_warnings"], [])
