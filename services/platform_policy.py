# -*- coding: utf-8 -*-
"""Load and validate the checked-in shared platform policy.

This module must never contain environment secrets.
Environment identity, paths, Redis endpoints and credentials remain in .env.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.platform_policy_semantics import (
    CONFIG_RULES,
    validate_config_values,
    validate_plan_policy,
    validate_policy_shape,
    validate_waitress_section,
)


ROOT = Path(__file__).resolve().parents[1]

POLICY_FILE = (
    ROOT
    / "settings"
    / "platform_policy.json"
)

ALLOWED_CONFIG_KEYS = frozenset(CONFIG_RULES)


def policy_file() -> Path:
    return POLICY_FILE


def load_platform_policy(
    path: str | Path | None = None,
) -> dict[str, Any]:

    target = (
        Path(path).resolve()
        if path is not None
        else POLICY_FILE
    )

    if not target.is_file():
        raise RuntimeError(
            "platform policy file missing: "
            + str(target)
        )

    with target.open(
        "r",
        encoding="utf-8-sig",
    ) as fh:
        policy = json.load(fh)

    if not isinstance(policy, dict):
        raise RuntimeError(
            "platform policy must be an object"
        )

    if int(
        policy.get(
            "schema_version",
            0,
        )
    ) != 1:
        raise RuntimeError(
            "unsupported platform policy schema"
        )

    validate_policy_shape(policy)

    managed_config(policy)

    waitress_backlog(policy)

    expand_plans(policy)

    return policy


def managed_config(
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:

    if policy is None:

        with POLICY_FILE.open(
            "r",
            encoding="utf-8-sig",
        ) as fh:
            policy = json.load(fh)

    values = policy.get(
        "config"
    )

    if not isinstance(values, dict):
        raise RuntimeError(
            "policy.config must be an object"
        )

    actual = set(values)

    unknown = (
        actual
        - ALLOWED_CONFIG_KEYS
    )

    missing = (
        ALLOWED_CONFIG_KEYS
        - actual
    )

    if unknown:
        raise RuntimeError(
            "unknown shared config keys: "
            + ",".join(
                sorted(unknown)
            )
        )

    if missing:
        raise RuntimeError(
            "missing shared config keys: "
            + ",".join(
                sorted(missing)
            )
        )

    validate_config_values(values)

    return dict(values)


def waitress_backlog(
    policy: dict[str, Any] | None = None,
) -> int:

    if policy is None:

        with POLICY_FILE.open(
            "r",
            encoding="utf-8-sig",
        ) as fh:
            policy = json.load(fh)

    section = policy.get(
        "waitress"
    )

    if not isinstance(section, dict):
        raise RuntimeError(
            "policy.waitress must be an object"
        )

    validate_waitress_section(section)

    value = section.get(
        "backlog"
    )

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
        or value > 100000
    ):
        raise RuntimeError(
            "invalid waitress backlog"
        )

    return int(value)


def expand_plans(
    policy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:

    if policy is None:

        with POLICY_FILE.open(
            "r",
            encoding="utf-8-sig",
        ) as fh:
            policy = json.load(fh)

    plans = policy.get(
        "plans"
    )

    if not isinstance(plans, dict):
        raise RuntimeError(
            "policy.plans must be an object"
        )

    validate_plan_policy(plans)

    result: list[
        dict[str, Any]
    ] = []


    for family_name in (
        "general",
        "special",
    ):

        family = plans.get(
            family_name
        )

        if not isinstance(
            family,
            dict,
        ):
            raise RuntimeError(
                "missing plan family: "
                + family_name
            )

        shared = family.get(
            "shared"
        )

        variants = family.get(
            "variants"
        )

        if not isinstance(
            shared,
            dict,
        ):
            raise RuntimeError(
                "invalid shared plan fields: "
                + family_name
            )

        if (
            not isinstance(
                variants,
                list,
            )
            or len(variants) != 3
        ):
            raise RuntimeError(
                "invalid plan variants: "
                + family_name
            )


        for variant in variants:

            if not isinstance(
                variant,
                dict,
            ):
                raise RuntimeError(
                    "plan variant must be an object"
                )

            row = dict(
                variant
            )

            row["plan_type"] = (
                family_name
            )

            row.update(
                shared
            )

            result.append(
                row
            )


    admin = plans.get(
        "admin"
    )

    if not isinstance(
        admin,
        dict,
    ):
        raise RuntimeError(
            "missing admin plan"
        )

    if str(
        admin.get(
            "plan_type",
            "",
        )
    ).lower() != "admin":
        raise RuntimeError(
            "admin plan type invalid"
        )

    result.append(
        dict(admin)
    )

    codes = [
        str(
            row.get(
                "plan_code",
                "",
            )
        )
        for row in result
    ]

    if (
        len(codes) != 7
        or len(set(codes)) != 7
    ):
        raise RuntimeError(
            "expanded plan codes invalid"
        )

    return result
