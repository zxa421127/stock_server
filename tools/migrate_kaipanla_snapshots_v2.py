# -*- coding: utf-8 -*-
"""Rebuild legacy Kaipanla normalized snapshots from immutable raw payloads.

Default mode is dry-run. Pass ``--apply`` to write, after an SQLite backup.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import config
from integrations.kaipanla.morning_bidding import _map_bidding_fields
from integrations.market_data.kaipanla.adapter import normalize_kaipanla_bidding
from integrations.market_data.kaipanla.schema import SCHEMA_VERSION
from services.kaipanla_snapshot_repository import KaipanlaSnapshotRepository


def _walk_payload(value: Any):
    if isinstance(value, dict):
        for key in ("response", "payload", "data"):
            if key in value:
                yield from _walk_payload(value[key])
        for key in ("pages", "raw_pages"):
            if key in value:
                yield from _walk_payload(value[key])
        for key in ("info", "list", "Data"):
            candidate=value.get(key)
            if isinstance(candidate,list):
                yield candidate
    elif isinstance(value,list):
        if value and all(isinstance(item,(list,tuple,dict)) for item in value):
            if all(isinstance(item,(list,tuple)) for item in value):
                yield value
            else:
                for item in value:
                    yield from _walk_payload(item)


def raw_payload_to_frame(raw_payload: Any) -> pd.DataFrame:
    frames=[]
    for rows in _walk_payload(raw_payload):
        if rows:
            frames.append(pd.DataFrame(rows))
    if not frames:
        return pd.DataFrame()
    combined=pd.concat(frames,ignore_index=True)
    combined=_map_bidding_fields(combined)
    code_col="股票代码" if "股票代码" in combined.columns else "0" if "0" in combined.columns else None
    if code_col:
        combined=combined.drop_duplicates(subset=[code_col],keep="first")
    return combined.reset_index(drop=True)


def _needs_migration(snapshot) -> bool:
    if snapshot.schema_version != SCHEMA_VERSION or not snapshot.normalized_data:
        return True
    first = snapshot.normalized_data[0]
    required = {
        "auction_net_amount", "auction_match_amount", "main_net_amount",
        "main_buy_amount", "main_sell_amount", "snapshot_type",
    }
    obsolete = {
        "10", "13", "14", "15", "auction_buy_amount", "auction_sell_amount",
        "main_sell_amount_signed", "main_amount_relation_valid",
        "field_validation_warning", "limit_step_nums", "limit_up_days_source",
        "kpl_list_status", "kpl_list_limit_up_days",
    }
    return not required.issubset(first) or bool(obsolete.intersection(first))


def _backup_repository(repo: KaipanlaSnapshotRepository, backup_path: str) -> str:
    target=Path(backup_path)
    target.parent.mkdir(parents=True,exist_ok=True)
    source=repo._conn()  # repository-owned connection; SQLite online backup keeps a consistent copy
    import sqlite3
    destination=sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
    return str(target)


def migrate_repository(repo: KaipanlaSnapshotRepository, *, apply: bool=False, backup_path: str | None=None) -> dict[str,Any]:
    snapshots=repo.iter_snapshots()
    candidates=[snap for snap in snapshots if _needs_migration(snap)]
    report={
        "mode":"apply" if apply else "dry-run",
        "scanned":len(snapshots),
        "would_migrate":len(candidates),
        "migrated":0,
        "skipped":len(snapshots)-len(candidates),
        "failed":0,
        "backup_path":None,
        "items":[],
    }
    if apply and candidates:
        if not backup_path:
            stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path=f"{config.DB_FILE}.kaipanla_v2_{stamp}.bak"
        report["backup_path"]=_backup_repository(repo,backup_path)
    for snapshot in candidates:
        item={"snapshot_id":snapshot.snapshot_id,"trade_date":snapshot.trade_date,"status":"would_migrate"}
        try:
            frame=raw_payload_to_frame(snapshot.raw_payload)
            if frame.empty:
                raise ValueError("raw_payload中未找到可恢复的info/list二维数组")
            normalized=normalize_kaipanla_bidding(frame,trade_date=snapshot.trade_date,snapshot_type=snapshot.snapshot_type,
                snapshot_time=snapshot.snapshot_time,snapshot_id=snapshot.snapshot_id,historical=True,source_provider=snapshot.source_provider,
                source_api=snapshot.source_api,data_quality=snapshot.data_quality)
            if apply:
                repo.update_normalized_payload(snapshot.snapshot_id,normalized.to_dict(orient="records"),schema_version=SCHEMA_VERSION)
                report["migrated"] += 1
                item["status"]="migrated"
            item["record_count"]=len(normalized)
        except Exception as exc:
            report["failed"] += 1
            item["status"]="failed"
            item["error"]=str(exc)
        report["items"].append(item)
    return report


def main() -> int:
    parser=argparse.ArgumentParser(description="迁移开盘啦历史快照到kaipanla_bidding.v2；默认dry-run")
    parser.add_argument("--apply",action="store_true",help="显式写入迁移结果")
    parser.add_argument("--backup",help="备份数据库路径；--apply时默认自动生成")
    parser.add_argument("--report",default="kaipanla_snapshot_migration_v2_report.json",help="迁移报告JSON路径")
    args=parser.parse_args()
    repo=KaipanlaSnapshotRepository()
    report=migrate_repository(repo,apply=args.apply,backup_path=args.backup)
    Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
