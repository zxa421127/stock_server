# -*- coding: utf-8 -*-
"""Synchronize the built-in catalog, migrate legacy plans, then verify exact DB alignment."""

from tools.db.apply_two_tier_plans import main as apply_main
from tools.db.verify_plan_catalog import main as verify_main


if __name__ == "__main__":
    apply_main()
    raise SystemExit(
        verify_main()
    )
