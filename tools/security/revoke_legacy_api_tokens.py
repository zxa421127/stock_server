# -*- coding: utf-8 -*-
"""Convenience entry point for revoking the obsolete plaintext token table."""
from tools.db.migrate_legacy_tokens import main

if __name__ == "__main__":
    raise SystemExit(main())
