from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.platform_policy import (
    ALLOWED_CONFIG_KEYS,
    load_platform_policy,
    managed_config,
)
from services.platform_policy_semantics import (
    CONFIG_RULES,
    validate_config_values,
)


ROOT = Path(__file__).resolve().parents[1]


def _base_policy():
    return json.loads(
        (ROOT / "settings" / "platform_policy.json").read_text(
            encoding="utf-8-sig"
        )
    )


def _invalid_for_rule(rule):
    kind = rule[0]

    if kind == "int":
        return int(rule[1]) - 1
    if kind == "bool":
        return "true"
    if kind == "str_list":
        return "not-a-list"
    if kind == "int_map":
        return {"x": int(rule[1]) - 1}
    if kind == "enum":
        return "NOT_SUPPORTED"
    if kind == "timezone":
        return "bad timezone"
    if kind == "weekdays":
        return "funday"

    raise AssertionError("unknown rule: " + repr(rule))


def test_current_policy_passes_semantic_validation():
    policy = load_platform_policy()
    assert policy["schema_version"] == 1
    assert managed_config() == policy["config"]


def test_config_rule_coverage_is_exact():
    assert len(CONFIG_RULES) == 82
    assert set(CONFIG_RULES) == set(ALLOWED_CONFIG_KEYS)


def test_every_managed_config_rule_rejects_invalid_value():
    baseline = managed_config()

    for key, rule in CONFIG_RULES.items():
        candidate = copy.deepcopy(baseline)
        candidate[key] = _invalid_for_rule(rule)

        with pytest.raises(RuntimeError):
            validate_config_values(candidate)


def test_config_cross_field_constraints_fail_closed():
    baseline = managed_config()

    cases = []

    candidate = copy.deepcopy(baseline)
    candidate["ADMIN_API_TEST_DISK_WARNING_PERCENT"] = 90
    candidate["ADMIN_API_TEST_DISK_CRITICAL_PERCENT"] = 90
    cases.append(candidate)

    candidate = copy.deepcopy(baseline)
    candidate["ADMIN_API_TEST_PREVIEW_PAGE_SIZE"] = 501
    candidate["ADMIN_API_TEST_MAX_PREVIEW_PAGE_SIZE"] = 500
    cases.append(candidate)

    candidate = copy.deepcopy(baseline)
    candidate["MIN_REQUESTS_PER_MINUTE"] = 1001
    candidate["DEFAULT_REQUESTS_PER_MINUTE"] = 1000
    cases.append(candidate)

    candidate = copy.deepcopy(baseline)
    candidate["MARKET_DATA_CACHE_MAX_ITEM_BYTES"] = 2048
    candidate["MARKET_DATA_CACHE_MAX_TOTAL_BYTES"] = 1024
    cases.append(candidate)

    candidate = copy.deepcopy(baseline)
    candidate["MARKET_DATA_REDIS_MAX_COMPRESSED_BYTES"] = 2048
    candidate["MARKET_DATA_REDIS_MAX_DECOMPRESSED_BYTES"] = 1024
    cases.append(candidate)

    for candidate in cases:
        with pytest.raises(RuntimeError):
            validate_config_values(candidate)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda p: p.__setitem__("schema_version", "1"),
        lambda p: p.__setitem__("unexpected_top_level", True),
        lambda p: p["waitress"].__setitem__("backlog", 0),
        lambda p: p["waitress"].__setitem__("unexpected", 1),
        lambda p: p["plans"]["general"]["shared"].__setitem__(
            "quota_per_minute", 0
        ),
        lambda p: p["plans"]["general"]["variants"][0].__setitem__(
            "duration_type", "week"
        ),
        lambda p: p["plans"]["admin"].__setitem__("public", True),
    ],
)
def test_end_to_end_invalid_policy_file_is_rejected(tmp_path, mutator):
    policy = _base_policy()
    mutator(policy)

    path = tmp_path / "invalid-policy.json"
    path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError):
        load_platform_policy(path)

