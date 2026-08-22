# -*- coding: utf-8 -*-
from pathlib import Path
import os

ALLOWED_ROOTS = {
r'C:\stockdata\stock_server_test',
r'C:\stockdata\production\blue\stock_server',
r'C:\stockdata\production\green\stock_server'
}

def collect_environment_errors(settings, require_enabled=False):
    if not bool(getattr(settings,'ENVIRONMENT_GUARD_ENABLED',False)):
        return ['ENVIRONMENT_GUARD_ENABLED must be True'] if require_enabled else []

    base=str(Path(getattr(settings,'BASE_DIR','')).resolve())
    ok=any(os.path.normcase(base)==os.path.normcase(str(Path(x).resolve())) for x in ALLOWED_ROOTS)

    return [] if ok else [f'project root mismatch: actual={base}']

def assert_environment_ready(settings):
    errors=collect_environment_errors(settings, True)
    if errors:
        raise RuntimeError('environment guard failed: '+ '; '.join(errors))
