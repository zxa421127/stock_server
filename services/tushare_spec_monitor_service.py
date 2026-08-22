# -*- coding: utf-8 -*-
"""Detect Tushare official-contract changes without mutating active specs."""
from __future__ import annotations

import logging
import os
import socket
import uuid
from datetime import datetime, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from services.market_interface_spec_service import MarketInterfaceSpecService
from services.tushare_spec_monitor_repository import TushareSpecMonitorRepository
from services.tushare_spec_sync_service import (
    TushareSpecSyncService,
    diff_interface_specs,
)

_PENDING_ALERT_STATUSES = {
    "new", "viewed", "syncing", "candidate_ready", "published",
    "verification_failed", "failed",
}


def _owner_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def _severity(diffs: list[dict[str, Any]]) -> str:
    values = {str(row.get("severity") or "info") for row in diffs}
    if "blocking" in values:
        return "blocking"
    if "warning" in values:
        return "warning"
    return "info"


def next_monitor_run(
    now: datetime | None = None, *, timezone_name: str = "Asia/Shanghai",
    weekdays: Iterable[int] = (2, 6), hour: int = 2, minute: int = 30,
) -> datetime:
    zone = ZoneInfo(timezone_name)
    current = now.astimezone(zone) if now and now.tzinfo else (now.replace(tzinfo=zone) if now else datetime.now(zone))
    allowed = {int(value) for value in weekdays}
    for offset in range(0, 8):
        day = (current + timedelta(days=offset)).date()
        candidate = datetime(day.year, day.month, day.day, int(hour), int(minute), tzinfo=zone)
        if candidate.weekday() in allowed and candidate > current:
            return candidate
    raise RuntimeError("无法计算下一次Tushare官网规格检查时间")


class TushareSpecMonitorService:
    LEASE_KEY = "tushare-official-spec-monitor"

    def __init__(
        self, *, spec_service: MarketInterfaceSpecService | None = None,
        repository: TushareSpecMonitorRepository | None = None,
        sync_service: TushareSpecSyncService | None = None,
    ):
        self.spec_service = spec_service or MarketInterfaceSpecService()
        self.spec_service.ensure_seed_release()
        self.repository = repository or TushareSpecMonitorRepository()
        self.sync_service = sync_service or TushareSpecSyncService(self.spec_service)

    @staticmethod
    def configured_next_run(now: datetime | None = None) -> datetime:
        import config
        weekday_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        configured = [
            weekday_map[value.strip().lower()]
            for value in str(config.TUSHARE_SPEC_MONITOR_WEEKDAYS).split(",")
            if value.strip().lower() in weekday_map
        ] or [2, 6]
        return next_monitor_run(
            now, timezone_name=str(config.TUSHARE_SPEC_MONITOR_TIMEZONE),
            weekdays=configured, hour=int(config.TUSHARE_SPEC_MONITOR_HOUR),
            minute=int(config.TUSHARE_SPEC_MONITOR_MINUTE),
        )

    def dashboard(self) -> dict[str, Any]:
        next_run = self.configured_next_run().strftime("%Y-%m-%d %H:%M:%S %Z")
        value = self.repository.dashboard(next_scheduled_at=next_run)
        value["schedule"] = {
            "timezone": "Asia/Shanghai",
            "weekdays": ["周三", "周日"],
            "time": "02:30",
        }
        return value

    def scan(self, api_names: Iterable[str] | None = None, *, trigger: str = "scheduled") -> dict[str, Any]:
        import config
        selected = {str(value).strip().lower() for value in api_names or [] if str(value).strip()}
        targets = [
            row for row in self.spec_service.list_effective_specs(provider="tushare")
            if not selected or str(row.get("api_name") or "").lower() in selected
        ]
        owner = _owner_id()
        if not self.repository.acquire_lease(
            self.LEASE_KEY, owner=owner,
            lease_seconds=int(config.TUSHARE_SPEC_MONITOR_LEASE_SECONDS),
        ):
            raise RuntimeError("Tushare官网规格检查正在由另一个进程执行")
        next_run = self.configured_next_run().strftime("%Y-%m-%d %H:%M:%S %Z")
        run = self.repository.start_scan_run(
            trigger=trigger, target_count=len(targets), next_scheduled_at=next_run,
        )
        success_count = 0
        changed_count = 0
        failures: list[dict[str, str]] = []
        changed_interfaces: list[dict[str, Any]] = []
        try:
            for current in targets:
                api_name = str(current.get("api_name") or "")
                try:
                    raw, document = self.sync_service.fetch_and_parse_official_spec(current)
                    effective = self.sync_service.build_effective_spec(current, raw)
                    diffs = diff_interface_specs(current, effective)
                    if not current.get("official_verified") and not diffs:
                        diffs = [{
                            "section": "interface", "field": "official_verified",
                            "change_type": "initial_official_verification", "severity": "warning",
                            "old": False, "new": True,
                        }]
                    self.repository.upsert_snapshot(
                        provider="tushare", api_name=api_name,
                        official_url=str(current.get("official_url") or ""),
                        raw_content_hash=str(raw.get("raw_content_hash") or ""),
                        semantic_spec_hash=str(raw.get("semantic_spec_hash") or ""),
                        parsed_spec=raw, source_format=str(raw.get("source_format") or ""),
                        fetched_at=str(raw.get("source_fetched_at") or ""), scan_run_id=run["id"],
                    )
                    if diffs:
                        self.repository.supersede_other_alerts(
                            "tushare", api_name, str(raw.get("semantic_spec_hash") or ""),
                        )
                        alert = self.repository.upsert_change_alert(
                            provider="tushare", api_name=api_name,
                            title=str(effective.get("title") or current.get("title") or api_name),
                            semantic_spec_hash=str(raw.get("semantic_spec_hash") or ""),
                            severity=_severity(diffs), diffs=diffs, scan_run_id=run["id"],
                        )
                        changed_count += 1
                        changed_interfaces.append({
                            "api_name": api_name, "title": alert.get("title"),
                            "severity": alert.get("severity"), "alert_id": alert.get("id"),
                            "diff_count": len(diffs),
                        })
                    elif current.get("official_verified"):
                        self.repository.resolve_alerts_for_current_spec("tushare", api_name)
                    success_count += 1
                except Exception as exc:
                    logging.exception("Tushare官网规格检查失败: %s", api_name)
                    failures.append({"api_name": api_name, "error": str(exc)})
            status = "success" if not failures else "partial_failure" if success_count else "failed"
            result = self.repository.finish_scan_run(
                run["id"], status=status, success_count=success_count,
                failure_count=len(failures), changed_count=changed_count,
                unchanged_count=max(0, success_count - changed_count),
                error_summary="；".join(f"{row['api_name']}:{row['error']}" for row in failures)[:4000],
                next_scheduled_at=next_run,
            )
            result.update({
                "changed_interfaces": changed_interfaces,
                "failures": failures,
                "complete_scan": success_count == len(targets) and not failures,
            })
            return result
        finally:
            self.repository.release_lease(self.LEASE_KEY, owner=owner)

    def create_candidate_for_alerts(
        self, alert_ids: Iterable[int], *, candidate_version: str | None = None,
    ) -> dict[str, Any]:
        ids = list(dict.fromkeys(int(value) for value in alert_ids))
        if not ids:
            raise ValueError("请至少选择一个官网变化提醒")
        alerts = [self.repository.get_alert(value) for value in ids]
        alerts = [row for row in alerts if row]
        if len(alerts) != len(ids):
            raise ValueError("部分官网变化提醒不存在")
        invalid = [row for row in alerts if row.get("status") not in _PENDING_ALERT_STATUSES]
        if invalid:
            raise ValueError("包含不可同步状态的官网变化提醒")
        api_names = list(dict.fromkeys(str(row.get("api_name") or "") for row in alerts))
        documents: dict[str, dict[str, str]] = {}
        self.repository.mark_alerts_syncing(ids)
        try:
            for api_name in api_names:
                current = self.spec_service.get_effective_spec("tushare", api_name)
                if not current:
                    raise ValueError(f"当前规格不存在：tushare/{api_name}")
                raw, document = self.sync_service.fetch_and_parse_official_spec(current)
                documents[api_name] = {**document, "raw": raw}
            manifest = self.sync_service.create_candidate_from_document_map(
                documents, candidate_version=candidate_version, target_count=len(api_names),
            )
            if not manifest.get("complete_sync"):
                raise RuntimeError("所选官网变化没有完成同步：" + str(manifest.get("failed_interfaces") or []))
            self.repository.mark_alerts_candidate(ids, str(manifest.get("version") or ""))
            return manifest
        except Exception as exc:
            self.repository.mark_alerts_failed(ids, str(exc), status="failed")
            raise

    def bind_published_release(
        self, *, candidate_version: str, api_names: Iterable[str], release_version: str,
    ) -> list[int]:
        ids = self.repository.alert_ids_for_candidate(candidate_version, api_names)
        self.repository.mark_alerts_published(ids, release_version)
        return ids

    def verify_published_interfaces(
        self, api_names: Iterable[str], *, candidate_version: str = "",
    ) -> dict[str, Any]:
        names = list(dict.fromkeys(str(value).strip().lower() for value in api_names if str(value).strip()))
        alert_ids = self.repository.alert_ids_for_candidate(candidate_version, names) if candidate_version else []
        verified: list[str] = []
        failures: list[dict[str, Any]] = []
        for api_name in names:
            try:
                current = self.spec_service.get_effective_spec("tushare", api_name)
                if not current:
                    raise ValueError(f"正式规格不存在：{api_name}")
                raw, document = self.sync_service.fetch_and_parse_official_spec(current)
                official = self.sync_service.build_effective_spec(current, raw)
                diffs = diff_interface_specs(current, official)
                if diffs:
                    raise ValueError(f"发布后仍有{len(diffs)}项官网差异")
                verified.append(api_name)
            except Exception as exc:
                failures.append({"api_name": api_name, "error": str(exc)})
        if alert_ids:
            if failures:
                self.repository.mark_alerts_failed(
                    alert_ids, "；".join(f"{row['api_name']}:{row['error']}" for row in failures),
                    status="verification_failed",
                )
            else:
                self.repository.mark_alerts_verified(alert_ids)
        return {"verified": verified, "failures": failures, "complete": not failures}


_default_monitor: TushareSpecMonitorService | None = None


def get_tushare_spec_monitor_service() -> TushareSpecMonitorService:
    global _default_monitor
    if _default_monitor is None:
        _default_monitor = TushareSpecMonitorService()
    return _default_monitor
