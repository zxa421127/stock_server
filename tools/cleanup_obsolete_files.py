# -*- coding: utf-8 -*-
"""Remove known obsolete files from the pre-refactor project tree.

Dry-run by default. From the project root:
    python -m tools.cleanup_obsolete_files
    python -m tools.cleanup_obsolete_files --apply

The script never deletes .env, data/, logs/, or database files.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

OBSOLETE_DIRS = (
    ".venv",
    ".idea",
    "api_proxy",
    "providers",
    "tasks",
    "tushare_provider",
    "kaipanla_provider",
    "scripts",
    "test",
)

OBSOLETE_FILES = (
    "add_record_time_field.py",
    "check_token.py",
    "fix_all_times.py",
    "raw_http_debug.py",
    "test_feishu_sync.py",
    "test_token.py",
    "token_generator.py",
    "token_record.txt",
    "middleware/config.py",
    "middleware/.env.example",
    "middleware/.gitignore",
    "routes/tushare_routes.py",
)


def discover(root: Path) -> list[Path]:
    if not (root / "app.py").is_file() or not (root / "config.py").is_file():
        raise SystemExit(f"目录不像项目根目录：{root}")

    targets: set[Path] = set()
    for relative in OBSOLETE_DIRS + OBSOLETE_FILES:
        path = root / relative
        if path.exists():
            targets.add(path)

    obsolete_roots = [root / relative for relative in OBSOLETE_DIRS]
    for path in root.rglob("__pycache__"):
        if not any(parent == path or parent in path.parents for parent in obsolete_roots):
            targets.add(path)
    targets.update(path for path in root.glob("#U*.md") if path.is_file())

    # If a directory is already scheduled, do not list its descendants separately.
    compact = [
        path for path in targets
        if not any(parent in targets for parent in path.parents)
    ]
    return sorted(compact, key=lambda item: str(item))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="项目根目录")
    parser.add_argument("--apply", action="store_true", help="实际删除；不加时仅预览")
    args = parser.parse_args()
    root = args.root.resolve()
    targets = discover(root)

    if not targets:
        print("未发现已知旧文件。")
        return

    mode = "DELETE" if args.apply else "DRY-RUN"
    for path in targets:
        print(f"[{mode}] {path.relative_to(root)}")
        if not args.apply:
            continue
        if path == root / ".venv":
            executable = Path(sys.executable).resolve()
            try:
                running_inside = executable == path or path in executable.parents
            except OSError:
                running_inside = False
            if running_inside:
                print("[SKIP] 当前 Python 正运行在 .venv 中；退出虚拟环境后手工删除并重建")
                continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)

    if not args.apply:
        print("\n仅预览，确认后执行：python -m tools.cleanup_obsolete_files --apply")
    else:
        print("\n旧源码/缓存已清理；.env、data、logs、数据库均未删除。")


if __name__ == "__main__":
    main()
