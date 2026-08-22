from __future__ import annotations

import ast
import json
from pathlib import Path

from services.plan_catalog import (
    DEFAULT_PLANS,
)

from services.platform_policy import (
    expand_plans,
    policy_file,
)


ROOT = Path(
    __file__
).resolve().parents[1]


def test_default_plans_exactly_equal_policy_expansion():

    assert (
        DEFAULT_PLANS
        == expand_plans()
    )


def test_plan_catalog_default_plans_assignment_is_policy_call():

    source_file = (
        ROOT
        / "services"
        / "plan_catalog.py"
    )

    source = source_file.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source,
        filename=str(source_file),
    )

    matches = []

    for node in tree.body:

        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if any(
            isinstance(
                target,
                ast.Name,
            )
            and
            target.id == "DEFAULT_PLANS"

            for target in node.targets
        ):
            matches.append(node)


    assert len(matches) == 1

    value = matches[0].value

    assert isinstance(
        value,
        ast.Call,
    )

    assert isinstance(
        value.func,
        ast.Name,
    )

    assert (
        value.func.id
        == "_expand_platform_plans"
    )


def test_plan_catalog_has_single_policy_marker():

    source = (
        ROOT
        .joinpath(
            "services",
            "plan_catalog.py",
        )
        .read_text(
            encoding="utf-8-sig"
        )
    )

    assert (
        source.count(
            "PLATFORM_POLICY_PLAN_CATALOG_V1"
        )
        == 1
    )


def test_general_and_special_shared_policy_values_exist_once():

    policy = json.loads(
        policy_file().read_text(
            encoding="utf-8-sig"
        )
    )

    plans = policy["plans"]

    for family_name in (
        "general",
        "special",
    ):

        family = plans[
            family_name
        ]

        shared = family[
            "shared"
        ]

        variants = family[
            "variants"
        ]


        assert len(variants) == 3

        assert (
            "quota_per_minute"
            in shared
        )

        assert (
            "quota_daily"
            in shared
        )

        assert (
            "max_symbols_per_request"
            in shared
        )

        assert (
            "min_refresh_interval_sec"
            in shared
        )


        for variant in variants:

            assert (
                "quota_per_minute"
                not in variant
            )

            assert (
                "quota_daily"
                not in variant
            )

            assert (
                "max_symbols_per_request"
                not in variant
            )

            assert (
                "min_refresh_interval_sec"
                not in variant
            )


def test_public_plan_codes_are_exactly_six():

    public_codes = {
        str(plan["plan_code"])
        for plan in DEFAULT_PLANS
        if plan.get("public")
    }

    assert public_codes == {
        "general_month",
        "general_quarter",
        "general_year",
        "special_month",
        "special_quarter",
        "special_year",
    }


def test_admin_plan_remains_single_and_private():

    admin = [
        plan
        for plan in DEFAULT_PLANS
        if (
            str(
                plan.get(
                    "plan_type",
                    "",
                )
            ).lower()
            == "admin"
        )
    ]

    assert len(admin) == 1

    assert (
        admin[0]["plan_code"]
        == "admin_internal"
    )

    assert (
        admin[0]["public"]
        is False
    )
