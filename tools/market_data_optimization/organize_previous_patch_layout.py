# -*- coding: utf-8 -*-
"""Move obsolete root-level files from the previous patch into docs backup.

Only files introduced by the earlier market-data optimization patch are moved.
Existing project entry points and legacy project scripts are never touched.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "patches" / "market_data_optimization"

OBSOLETE_ROOT_FILES = (
    "apply_market_data_optimization_env.bat",
    "verify_market_data_optimization.bat",
    "README_行情缓存与接口测试优化补丁.txt",
    "PATCH_FILE_LIST_行情优化.txt",
    "SOURCE_DIFF_行情优化.patch",
    "SHA256SUMS.txt",
)


def main() -> int:
    existing = [ROOT / name for name in OBSOLETE_ROOT_FILES if (ROOT / name).is_file()]
    if not existing:
        print("未发现上一版补丁遗留的根目录文件，无需整理。")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = DOCS_DIR / f"legacy_root_files_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    for source in existing:
        target = backup_dir / source.name
        shutil.move(str(source), str(target))
        print(f"已移动：{source.name} -> {target.relative_to(ROOT)}")

    print(f"整理完成，旧文件备份目录：{backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
