# -*- coding: utf-8 -*-
"""File storage for complete administrator interface-test results."""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any


class ResultTooLargeError(ValueError):
    """Raised when a full upstream response exceeds the configured safety limit."""


def _safe_segment(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "_").replace("/", "_")
    text = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in text)
    text = text.strip("._")
    if not text or text in {".", ".."}:
        raise ValueError("结果目录名称非法")
    return text[:160]


def _json_bytes(value: Any, *, pretty: bool = False) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, indent=2 if pretty else None,
        separators=None if pretty else (",", ":"), default=str,
    ).encode("utf-8")


class AdminApiTestStorage:
    def __init__(self, root: str | Path | None = None, *, max_result_bytes: int | None = None):
        if root is None or max_result_bytes is None:
            import config
            root = root or config.ADMIN_API_TEST_RESULT_DIR
            max_result_bytes = max_result_bytes or int(config.ADMIN_API_TEST_MAX_RESULT_BYTES)
        self.root = Path(root).resolve()
        self.max_result_bytes = int(max_result_bytes)
        self.root.mkdir(parents=True, exist_ok=True)

    def safe_resolve(self, value: str | Path) -> Path:
        path = Path(value)
        resolved = path.resolve() if path.is_absolute() else (self.root / path).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("结果路径超出允许目录") from exc
        return resolved

    def _batch_dir(self, batch_id: str, *, create: bool = False) -> Path:
        safe_batch = _safe_segment(batch_id)
        matches = [path for path in self.root.glob(f"*/*/*/{safe_batch}") if path.is_dir()]
        if matches:
            return matches[0]
        now = datetime.now()
        directory = self.root / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}" / safe_batch
        if create:
            directory.mkdir(parents=True, exist_ok=True)
        return directory

    def item_dir(self, batch_id: str, item_id: int, provider: str, api_name: str) -> Path:
        directory = self._batch_dir(batch_id, create=True) / _safe_segment(provider) / _safe_segment(api_name) / f"item-{int(item_id)}"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @staticmethod
    def _atomic_plain(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    @staticmethod
    def _atomic_gzip(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        os.close(fd)
        try:
            with open(temporary, "wb") as raw:
                with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, mtime=0) as handle:
                    handle.write(content)
                # Windows may reject fsync() on a descriptor opened read-only.
                # Flush and sync the writable descriptor before it is closed.
                raw.flush()
                os.fsync(raw.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def store_result(
        self, *, batch_id: str, item_id: int, provider: str, api_name: str,
        request_payload: dict[str, Any], response_payload: dict[str, Any],
        schema_report: dict[str, Any],
    ) -> dict[str, Any]:
        directory = self.item_dir(batch_id, item_id, provider, api_name)
        result_bytes = _json_bytes(response_payload)
        if len(result_bytes) > self.max_result_bytes:
            diagnostic = {
                "success": False,
                "code": 413,
                "provider": provider,
                "data_type": api_name,
                "data": [],
                "msg": "完整结果超过管理员测试安全上限，未静默截断",
                "uncompressed_size_bytes": len(result_bytes),
                "configured_max_result_bytes": self.max_result_bytes,
            }
            self._atomic_plain(directory / "result_too_large.json", _json_bytes(diagnostic, pretty=True))
            raise ResultTooLargeError(
                f"完整结果{len(result_bytes)}字节超过上限{self.max_result_bytes}字节"
            )
        request_file = directory / "request.json"
        result_file = directory / "result.json.gz"
        schema_file = directory / "schema_report.json"
        self._atomic_plain(request_file, _json_bytes(request_payload, pretty=True))
        self._atomic_gzip(result_file, result_bytes)
        self._atomic_plain(schema_file, _json_bytes(schema_report, pretty=True))
        data = response_payload.get("data") if isinstance(response_payload, dict) else None
        rows = data if isinstance(data, list) else []
        expected_columns = [
            str(value).strip()
            for value in (schema_report.get("expected_fields") or [])
            if str(value).strip()
        ]
        csv_file: Path | None = None
        if (rows and all(isinstance(row, dict) for row in rows)) or expected_columns:
            csv_file = directory / "result.csv.gz"
            self._write_csv_gzip(csv_file, rows, columns=expected_columns)
        digest = hashlib.sha256(result_file.read_bytes()).hexdigest()
        columns = list(expected_columns)
        for row in rows:
            if isinstance(row, dict):
                for key in row:
                    if key not in columns:
                        columns.append(key)
        return {
            "result_dir": str(directory),
            "request_file_path": str(request_file),
            "result_file_path": str(result_file),
            "schema_file_path": str(schema_file),
            "csv_file_path": str(csv_file) if csv_file is not None else "",
            "result_size_bytes": result_file.stat().st_size,
            "result_uncompressed_size_bytes": len(result_bytes),
            "result_sha256": digest,
            "row_count": len(rows),
            "column_count": len(columns),
        }

    def _write_csv_gzip(
        self, path: Path, rows: list[dict[str, Any]], *, columns: list[str] | None = None,
    ) -> None:
        from services.audit_security import safe_csv_cell

        ordered_columns: list[str] = []
        for key in columns or []:
            name = str(key)
            if name and name not in ordered_columns:
                ordered_columns.append(name)
        for row in rows:
            for key in row:
                name = str(key)
                if name not in ordered_columns:
                    ordered_columns.append(name)
        columns = ordered_columns
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            normalized = {}
            for key in columns:
                value = row.get(key)
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                normalized[key] = safe_csv_cell(value)
            writer.writerow(normalized)
        self._atomic_gzip(path, buffer.getvalue().encode("utf-8-sig"))

    def read_response(self, result_file_path: str | Path) -> dict[str, Any]:
        path = self.safe_resolve(result_file_path)
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("结果文件不是JSON对象")
        return payload

    def read_rows(self, result_file_path: str | Path, *, page: int, page_size: int) -> dict[str, Any]:
        payload = self.read_response(result_file_path)
        rows = payload.get("data") if isinstance(payload.get("data"), list) else []
        page = max(1, int(page))
        page_size = max(1, int(page_size))
        start = (page - 1) * page_size
        return {
            "page": page,
            "page_size": page_size,
            "total": len(rows),
            "pages": (len(rows) + page_size - 1) // page_size if rows else 0,
            "rows": rows[start:start + page_size],
        }

    def write_batch_manifest(self, batch_id: str, payload: dict[str, Any]) -> str:
        directory = self._batch_dir(batch_id, create=True)
        path = directory / "manifest.json"
        content = dict(payload)
        content.setdefault("batch_id", batch_id)
        content.setdefault("generated_at", datetime.now().isoformat(timespec="seconds"))
        self._atomic_plain(path, _json_bytes(content, pretty=True))
        return str(path)

    def build_batch_zip(self, batch_id: str) -> str:
        directory = self._batch_dir(batch_id, create=False)
        if not directory.exists():
            raise FileNotFoundError(f"批次结果目录不存在：{batch_id}")
        path = directory / f"{_safe_segment(batch_id)}-complete-results.zip"
        fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=directory)
        os.close(fd)
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                for file_path in sorted(directory.rglob("*")):
                    if not file_path.is_file() or file_path == path or file_path == Path(temporary):
                        continue
                    archive.write(file_path, file_path.relative_to(directory))
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        return str(path)

    def delete_batch(self, batch_id: str) -> None:
        directory = self._batch_dir(batch_id, create=False)
        if not directory.exists():
            return
        resolved = self.safe_resolve(directory)
        if resolved.name != _safe_segment(batch_id):
            raise ValueError("批次目录与批次ID不匹配")
        shutil.rmtree(resolved)

    def disk_status(self) -> dict[str, Any]:
        usage = shutil.disk_usage(self.root)
        used_percent = round((usage.used / usage.total) * 100, 2) if usage.total else 0.0
        total_size = sum(path.stat().st_size for path in self.root.rglob("*") if path.is_file())
        return {
            "root": str(self.root),
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_percent": used_percent,
            "result_files_bytes": total_size,
        }
