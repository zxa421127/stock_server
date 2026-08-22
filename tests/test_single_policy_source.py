from __future__ import annotations

import ast
import json

from pathlib import Path

import config

from services.plan_catalog import (
    DEFAULT_PLANS,
)

from services.platform_policy import (
    expand_plans,
    managed_config,
    policy_file,
    waitress_backlog,
)


ROOT = Path(
    __file__
).resolve().parents[1]

CONFIG_MARKER = (
    "PLATFORM_POLICY_RUNTIME_OVERLAY_V1"
)

ENV_MARKER = (
    "PLATFORM_POLICY_ENV_EXAMPLE_SINGLE_SOURCE_V1"
)

PLAN_MARKER = (
    "PLATFORM_POLICY_PLAN_CATALOG_V1"
)

DOC = (
    "managed in settings/platform_policy.json"
)


def read(path):

    return path.read_text(
        encoding="utf-8-sig"
    )


def names(target):

    if isinstance(
        target,
        ast.Name,
    ):

        return {
            target.id
        }

    if isinstance(
        target,
        (
            ast.Tuple,
            ast.List,
        ),
    ):

        result = set()

        for item in target.elts:

            result |= names(
                item
            )

        return result

    return set()


def assigned(node):

    result = set()

    if isinstance(
        node,
        ast.Assign,
    ):

        for target in node.targets:

            result |= names(
                target
            )

    elif isinstance(
        node,
        ast.AnnAssign,
    ):

        result |= names(
            node.target
        )

    return result


def test_policy_mapping_and_runtime_match():

    policy = json.loads(
        policy_file().read_text(
            encoding="utf-8-sig"
        )
    )

    managed = (
        managed_config()
    )

    assert (
        managed
        ==
        policy[
            "config"
        ]
    )

    for key, value in (
        managed.items()
    ):

        assert (
            getattr(
                config,
                key,
            )
            ==
            value
        )

    assert (
        config.WAITRESS_BACKLOG
        ==
        waitress_backlog()
    )


def test_config_has_no_pre_overlay_managed_assignment_or_read():

    managed = set(
        managed_config()
    )

    source = read(
        ROOT
        / "config.py"
    )

    tree = ast.parse(
        source
    )

    assert (
        source.count(
            CONFIG_MARKER
        )
        == 1
    )

    marker_line = next(
        index
        for index, line
        in enumerate(
            source.splitlines(),
            1,
        )
        if (
            CONFIG_MARKER
            in line
        )
    )

    bad_assignments = [
        (
            node.lineno,
            sorted(
                assigned(
                    node
                )
                & managed
            ),
        )
        for node
        in tree.body
        if (
            isinstance(
                node,
                (
                    ast.Assign,
                    ast.AnnAssign,
                ),
            )
            and node.lineno
            < marker_line
            and assigned(
                node
            )
            & managed
        )
    ]

    bad_reads = sorted(
        {
            (
                node.id,
                node.lineno,
            )
            for node
            in ast.walk(
                tree
            )
            if (
                isinstance(
                    node,
                    ast.Name,
                )
                and isinstance(
                    node.ctx,
                    ast.Load,
                )
                and node.id
                in managed
                and node.lineno
                < marker_line
            )
        }
    )

    assert (
        bad_assignments
        == []
    )

    assert (
        bad_reads
        == []
    )


def test_env_example_has_docs_but_no_active_managed_values():

    managed = set(
        managed_config()
    )

    source = read(
        ROOT
        / ".env.example"
    )

    assert (
        source.count(
            ENV_MARKER
        )
        == 1
    )

    active = []
    documented = []

    for line_no, raw in enumerate(
        source.splitlines(),
        1,
    ):

        line = raw.strip()

        if not line:
            continue

        if line.startswith(
            "#"
        ):

            body = (
                line[
                    1:
                ]
                .strip()
            )

            if "=" in body:

                key, value = (
                    body.split(
                        "=",
                        1,
                    )
                )

                if (
                    key.strip()
                    in managed
                    and value.strip()
                    == DOC
                ):

                    documented.append(
                        key.strip()
                    )

            continue

        if "=" in line:

            key = (
                line
                .split(
                    "=",
                    1,
                )[0]
                .strip()
            )

            if key in managed:

                active.append(
                    (
                        line_no,
                        key,
                    )
                )

    assert (
        active
        == []
    )

    assert (
        len(
            documented
        )
        ==
        len(
            managed
        )
    )

    assert (
        set(
            documented
        )
        ==
        managed
    )


def test_waitress_and_plan_catalog_are_policy_wired():

    for filename in (
        "run_waitress.py",
        "run_waitress_web_only.py",
    ):

        tree = ast.parse(
            read(
                ROOT
                / filename
            )
        )

        backlog_values = [
            keyword.value
            for node
            in ast.walk(
                tree
            )
            if isinstance(
                node,
                ast.Call,
            )
            for keyword
            in node.keywords
            if (
                keyword.arg
                ==
                "backlog"
            )
        ]

        assert (
            len(
                backlog_values
            )
            == 1
        )

        value = (
            backlog_values[
                0
            ]
        )

        assert isinstance(
            value,
            ast.Attribute,
        )

        assert (
            value.attr
            ==
            "WAITRESS_BACKLOG"
        )

        assert isinstance(
            value.value,
            ast.Name,
        )

        assert (
            value.value.id
            ==
            "config"
        )

    assert (
        DEFAULT_PLANS
        ==
        expand_plans()
    )

    source = read(
        ROOT
        / "services"
        / "plan_catalog.py"
    )

    assert (
        source.count(
            PLAN_MARKER
        )
        == 1
    )


def test_tests_do_not_restore_numeric_catalog_truth():

    offenders = []

    for path in sorted(
        (
            ROOT
            / "tests"
        ).glob(
            "test_*.py"
        )
    ):

        if (
            path.resolve()
            ==
            Path(
                __file__
            ).resolve()
        ):

            continue

        tree = ast.parse(
            read(
                path
            )
        )

        for node in ast.walk(
            tree
        ):

            if not isinstance(
                node,
                ast.Compare,
            ):

                continue

            values = [
                node.left,
                *node.comparators,
            ]

            has_catalog = any(
                (
                    isinstance(
                        value,
                        ast.Subscript,
                    )
                    and isinstance(
                        value.slice,
                        ast.Constant,
                    )
                    and value.slice.value
                    ==
                    "catalog"
                )
                for value
                in values
            )

            has_number = any(
                (
                    isinstance(
                        value,
                        ast.Constant,
                    )
                    and isinstance(
                        value.value,
                        (
                            int,
                            float,
                        ),
                    )
                    and not isinstance(
                        value.value,
                        bool,
                    )
                )
                for value
                in values
            )

            if (
                has_catalog
                and has_number
            ):

                offenders.append(
                    (
                        str(
                            path.relative_to(
                                ROOT
                            )
                        ),
                        node.lineno,
                    )
                )

    assert (
        offenders
        == []
    )


def test_policy_workflow_runs_single_source_guard():

    source = read(
        ROOT
        / "deploy"
        / "windows"
        / "Apply-TestPlatformPolicy.ps1"
    ).replace(
        "\\",
        "/",
    )

    assert (
        source.count(
            "tests/test_single_policy_source.py"
        )
        == 1
    )
