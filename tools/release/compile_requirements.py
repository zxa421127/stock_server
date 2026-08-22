# -*- coding: utf-8 -*-
"""Compile reproducible production dependencies with hashes."""
from __future__ import annotations
import subprocess
import sys


def main() -> int:
    command = [sys.executable, "-m", "piptools", "compile", "--generate-hashes", "--resolver=backtracking", "--output-file=requirements.lock", "requirements.txt"]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
