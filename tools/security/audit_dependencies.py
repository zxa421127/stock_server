# -*- coding: utf-8 -*-
from __future__ import annotations
import subprocess
import sys


def main() -> int:
    return subprocess.call([sys.executable, "-m", "pip_audit", "-r", "requirements.lock", "--strict"])


if __name__ == "__main__":
    raise SystemExit(main())
