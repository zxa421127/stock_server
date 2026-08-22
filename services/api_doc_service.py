# -*- coding: utf-8 -*-
"""
API 文档管理服务。

说明：
- 这里管理的是“接口文档说明”，不会自动创建真实 API 路由。
- 真实接口仍需要在 routes/*.py 里开发。
- 管理员在 /admin/api-docs 维护文档，用户在 /user/api-docs 查看文档。
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
from typing import Any

from flask import current_app, has_app_context
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import RequestRedirect

from services.api_doc_catalog_runtime import (
    FULL_API_DOCS,
    FULL_API_DOCS_VERSION,
)

from services.api_doc_runtime_status import (
    get_runtime_status_snapshot,
    runtime_report_is_stale,
    runtime_status_for_path,
)

from db_utils import get_conn, row_to_dict, rows_to_dicts


DEFAULT_ERROR_CODES = """401 Token缺失或无效
402 套餐未开通或已过期
403 当前套餐无权限
429 调用额度或刷新频率受限
502 上游数据源调用失败
500 服务异常"""


DEFAULT_HEADERS = "X-API-Token: 用户自己的Token"


DEFAULT_RESPONSE = """{
  "success": true,
  "data": [],
  "msg": "ok"
}"""


_GENERATED_PATH_PREFIXES = (
    "/api/v1/market/tushare/",
    "/api/v1/market/kaipanla/",
)
_OBSOLETE_API_DOC_PATHS = (
    "/api/data/stock/basic?list_status=L",
    "/api/data/trade/cal?exchange=SSE&start_date=20260701&end_date=20260731",
)

def _catalog_fingerprint(docs: list[dict[str, Any]] | None = None) -> str:
    """Hash the complete generated catalog so same-count edits are detected."""
    payload = docs if docs is not None else FULL_API_DOCS
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()



def _is_generated_path(path: str) -> bool:
    value = str(path or "")
    return value.startswith(_GENERATED_PATH_PREFIXES)


def _cleanup_legacy_generated_catalog(cur) -> int:
    """Replace the old 140-row catalog shape shown by legacy deployments.

    Older databases can contain the complete generated catalog under legacy
    paths/status values, so every row is misclassified as custom/inactive.
    We only remove those rows when the candidate set is exactly the generated
    catalog size and nearly every category/title pair matches the code catalog.
    Unrelated custom categories and endpoints are never selected.
    """
    expected_categories = sorted({str(doc["category"]) for doc in FULL_API_DOCS})
    expected_pairs = {(str(doc["category"]), str(doc["title"])) for doc in FULL_API_DOCS}
    if not expected_categories or not expected_pairs:
        return 0

    cur.execute(
        "SELECT COUNT(*) AS cnt FROM api_doc_endpoints "
        "WHERE path LIKE '/api/v1/market/tushare/%' "
        "OR path LIKE '/api/v1/market/kaipanla/%'"
    )
    generated_count = int((cur.fetchone() or {"cnt": 0})["cnt"] or 0)
    if generated_count >= len(FULL_API_DOCS):
        return 0

    placeholders = ",".join("?" for _ in expected_categories)
    cur.execute(
        f"""
        SELECT e.id,c.name AS category_name,e.title
        FROM api_doc_endpoints e
        JOIN api_doc_categories c ON c.id=e.category_id
        WHERE c.name IN ({placeholders})
        """,
        expected_categories,
    )
    rows = cur.fetchall()
    if len(rows) != len(FULL_API_DOCS):
        return 0

    actual_pairs = {
        (str(row["category_name"] or ""), str(row["title"] or ""))
        for row in rows
    }
    minimum_matches = max(len(FULL_API_DOCS) - 5, int(len(FULL_API_DOCS) * 0.95))
    if len(actual_pairs & expected_pairs) < minimum_matches:
        return 0

    endpoint_ids = [int(row["id"]) for row in rows]
    id_placeholders = ",".join("?" for _ in endpoint_ids)
    cur.execute(
        f"DELETE FROM api_doc_endpoints WHERE id IN ({id_placeholders})",
        endpoint_ids,
    )
    deleted = max(int(cur.rowcount or 0), 0)
    if deleted:
        logging.warning(
            "[API文档] 检测到旧版目录结构并自动替换: legacy_rows=%s",
            deleted,
        )
    return deleted


def cleanup_obsolete_api_docs(cur) -> dict[str, int]:
    """Delete only the two explicitly retired documents and orphaned categories."""
    placeholders = ",".join("?" for _ in _OBSOLETE_API_DOC_PATHS)
    cur.execute(
        f"DELETE FROM api_doc_endpoints WHERE path IN ({placeholders})",
        _OBSOLETE_API_DOC_PATHS,
    )
    obsolete_docs_deleted = max(int(cur.rowcount or 0), 0)
    cur.execute(
        """
        DELETE FROM api_doc_categories
        WHERE NOT EXISTS (
            SELECT 1 FROM api_doc_endpoints e WHERE e.category_id=api_doc_categories.id
        )
        """
    )
    empty_categories_deleted = max(int(cur.rowcount or 0), 0)
    return {
        "obsolete_docs_deleted": obsolete_docs_deleted,
        "empty_categories_deleted": empty_categories_deleted,
    }


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ensure_sync_meta_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS api_doc_sync_meta (
            meta_key TEXT PRIMARY KEY,
            meta_value TEXT,
            updated_at TEXT
        )
        """
    )


def _params_text(doc: dict[str, Any]) -> str:
    lines: list[str] = []
    for item in doc.get("params") or []:
        values = [
            str(item.get("name") or ""),
            str(item.get("type") or "string"),
            str(item.get("required") or "参考官网"),
            str(item.get("example") or ""),
            str(item.get("description") or ""),
        ]
        values = [value.replace("|", "／").replace("\r", " ").replace("\n", " ") for value in values]
        lines.append("|".join(values))
    return "\n".join(lines)


def full_api_docs_status() -> dict[str, Any]:
    """Return synchronization status without opening a write transaction."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type='table' AND name='api_doc_sync_meta'"
    )
    meta_table_exists = cur.fetchone() is not None
    meta: dict[str, str] = {}
    if meta_table_exists:
        cur.execute(
            "SELECT meta_key,meta_value FROM api_doc_sync_meta "
            "WHERE meta_key IN ('full_api_docs_version','full_api_docs_fingerprint')"
        )
        meta = {str(row["meta_key"]): str(row["meta_value"] or "") for row in cur.fetchall()}
    cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM api_doc_endpoints
        WHERE path LIKE '/api/v1/market/tushare/%'
           OR path LIKE '/api/v1/market/kaipanla/%'
        """
    )
    count_row = cur.fetchone()
    return {
        "expected_version": FULL_API_DOCS_VERSION,
        "installed_version": meta.get("full_api_docs_version", ""),
        "expected_fingerprint": _catalog_fingerprint(),
        "installed_fingerprint": meta.get("full_api_docs_fingerprint", ""),
        "expected_count": len(FULL_API_DOCS),
        "installed_count": int(count_row["cnt"] or 0) if count_row else 0,
    }


def sync_full_api_docs(*, force: bool = False) -> dict[str, Any]:
    """Synchronize the complete generated interface-document catalog.

    The synchronization owns only the two real market-data route prefixes:
    ``/api/v1/market/tushare/`` and ``/api/v1/market/kaipanla/``.
    Other administrator-created documents are preserved.

    Every successful exit commits the transaction, including the idempotent
    no-change path. Any exception rolls back before it is propagated.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        _ensure_sync_meta_table(cur)
        legacy_generated_docs_deleted = _cleanup_legacy_generated_catalog(cur)
        cleanup_result = {
            "legacy_generated_docs_deleted": legacy_generated_docs_deleted,
            **cleanup_obsolete_api_docs(cur),
        }

        cur.execute(
            "SELECT meta_key,meta_value FROM api_doc_sync_meta "
            "WHERE meta_key IN ('full_api_docs_version','full_api_docs_fingerprint')"
        )
        installed_meta = {
            str(row["meta_key"]): str(row["meta_value"] or "")
            for row in cur.fetchall()
        }
        installed_version = installed_meta.get("full_api_docs_version", "")
        installed_fingerprint = installed_meta.get("full_api_docs_fingerprint", "")
        expected_fingerprint = _catalog_fingerprint()

        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM api_doc_endpoints
            WHERE path LIKE '/api/v1/market/tushare/%'
               OR path LIKE '/api/v1/market/kaipanla/%'
            """
        )
        count_row = cur.fetchone()
        installed_count = int(count_row["cnt"] or 0) if count_row else 0

        if (
            not force
            and installed_version == FULL_API_DOCS_VERSION
            and installed_count == len(FULL_API_DOCS)
            and installed_fingerprint == expected_fingerprint
        ):
            # cleanup_obsolete_api_docs() executes DELETE statements. SQLite
            # starts a write transaction even when those DELETEs affect zero
            # rows, so this commit is mandatory on every successful return.
            conn.commit()
            if (
                cleanup_result["obsolete_docs_deleted"]
                or cleanup_result["empty_categories_deleted"]
            ):
                logging.info("[API文档] 已清理旧文档: %s", cleanup_result)
            return {
                "changed": False,
                "version": installed_version,
                "endpoint_count": installed_count,
                "category_count": len({doc["category"] for doc in FULL_API_DOCS}),
                "fingerprint": expected_fingerprint,
                **cleanup_result,
            }

        now = _now()
        category_ids: dict[str, int] = {}
        category_docs: dict[str, dict[str, Any]] = {}
        for doc in FULL_API_DOCS:
            category_docs.setdefault(doc["category"], doc)

        for category_name, sample in sorted(
            category_docs.items(),
            key=lambda item: (
                int(item[1].get("category_sort_order") or 100),
                item[0],
            ),
        ):
            cur.execute(
                "SELECT id FROM api_doc_categories "
                "WHERE name=? ORDER BY id LIMIT 1",
                (category_name,),
            )
            row = cur.fetchone()
            if row:
                category_id = int(row["id"])
                cur.execute(
                    """
                    UPDATE api_doc_categories
                    SET description=?, sort_order=?, status='active', updated_at=?
                    WHERE id=?
                    """,
                    (
                        sample.get("category_description") or "",
                        int(sample.get("category_sort_order") or 100),
                        now,
                        category_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO api_doc_categories
                        (name, description, sort_order, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'active', ?, ?)
                    """,
                    (
                        category_name,
                        sample.get("category_description") or "",
                        int(sample.get("category_sort_order") or 100),
                        now,
                        now,
                    ),
                )
                category_id = int(cur.lastrowid)
            category_ids[category_name] = category_id

        cur.execute(
            """
            DELETE FROM api_doc_endpoints
            WHERE path LIKE '/api/v1/market/tushare/%'
               OR path LIKE '/api/v1/market/kaipanla/%'
            """
        )

        for doc in FULL_API_DOCS:
            cur.execute(
                """
                INSERT INTO api_doc_endpoints (
                    category_id, title, method, path, scope, description,
                    params_text, headers_text, request_example, response_example,
                    error_codes, sort_order, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    category_ids[doc["category"]],
                    doc["title"],
                    doc.get("method") or "GET",
                    doc["path"],
                    doc.get("scope") or "",
                    doc.get("description") or "",
                    _params_text(doc),
                    DEFAULT_HEADERS,
                    doc.get("request_example") or "",
                    doc.get("response_example") or DEFAULT_RESPONSE,
                    DEFAULT_ERROR_CODES,
                    int(doc.get("sort_order") or 100),
                    now,
                    now,
                ),
            )

        # A same-count catalog edit can move all endpoints out of an old
        # generated category. Remove that now-empty category in the same
        # transaction so category totals and filters follow the catalog.
        post_sync_cleanup = cleanup_obsolete_api_docs(cur)
        cleanup_result = {
            key: int(cleanup_result.get(key, 0)) + int(post_sync_cleanup.get(key, 0))
            for key in {**cleanup_result, **post_sync_cleanup}
        }

        cur.execute(
            """
            INSERT INTO api_doc_sync_meta (meta_key, meta_value, updated_at)
            VALUES ('full_api_docs_version', ?, ?)
            ON CONFLICT(meta_key) DO UPDATE SET
                meta_value=excluded.meta_value,
                updated_at=excluded.updated_at
            """,
            (FULL_API_DOCS_VERSION, now),
        )
        cur.execute(
            """
            INSERT INTO api_doc_sync_meta (meta_key, meta_value, updated_at)
            VALUES ('full_api_docs_fingerprint', ?, ?)
            ON CONFLICT(meta_key) DO UPDATE SET
                meta_value=excluded.meta_value,
                updated_at=excluded.updated_at
            """,
            (expected_fingerprint, now),
        )
        conn.commit()

        logging.info(
            "[API文档] 完整目录同步完成 "
            "version=%s categories=%s endpoints=%s force=%s",
            FULL_API_DOCS_VERSION,
            len(category_ids),
            len(FULL_API_DOCS),
            force,
        )
        return {
            "changed": True,
            "version": FULL_API_DOCS_VERSION,
            "endpoint_count": len(FULL_API_DOCS),
            "category_count": len(category_ids),
            "fingerprint": expected_fingerprint,
            **cleanup_result,
        }
    except Exception:
        conn.rollback()
        raise


def get_api_doc_statistics(
    *,
    include_route_stats: bool = True,
    public_only: bool = False,
) -> dict[str, Any]:
    """Return the single database-derived count model used by all UIs and tools."""
    ensure_default_api_docs()
    conn = get_conn()
    cur = conn.cursor()
    where_sql = ""
    if public_only:
        where_sql = (
            " WHERE e.status='active' AND EXISTS ("
            "SELECT 1 FROM api_doc_categories c "
            "WHERE c.id=e.category_id AND c.status='active')"
        )
    cur.execute(
        f"""
        SELECT
            COUNT(*) AS document_count,
            SUM(CASE WHEN e.status='active' THEN 1 ELSE 0 END) AS active_count,
            SUM(CASE WHEN e.status<>'active' THEN 1 ELSE 0 END) AS non_active_count,
            SUM(CASE WHEN e.path LIKE '/api/v1/market/tushare/%'
                       OR e.path LIKE '/api/v1/market/kaipanla/%' THEN 1 ELSE 0 END) AS generated_count,
            SUM(CASE WHEN NOT (e.path LIKE '/api/v1/market/tushare/%'
                           OR e.path LIKE '/api/v1/market/kaipanla/%') THEN 1 ELSE 0 END) AS custom_count,
            SUM(CASE WHEN e.scope LIKE 'tushare:points%:read' THEN 1 ELSE 0 END) AS general_count,
            SUM(CASE WHEN e.scope LIKE 'tushare:independent:%'
                       OR e.scope='market:kaipanla:read' THEN 1 ELSE 0 END) AS special_count,
            SUM(CASE WHEN e.scope NOT LIKE 'tushare:points%:read'
                       AND e.scope NOT LIKE 'tushare:independent:%'
                       AND e.scope<>'market:kaipanla:read' THEN 1 ELSE 0 END) AS other_scope_count,
            SUM(CASE WHEN e.description LIKE '%最新实测状态：正常可用%' THEN 1 ELSE 0 END) AS catalog_available_count
        FROM api_doc_endpoints e
        {where_sql}
        """
    )
    row = cur.fetchone()
    numeric_keys = (
        "document_count",
        "active_count",
        "non_active_count",
        "generated_count",
        "custom_count",
        "general_count",
        "special_count",
        "other_scope_count",
        "catalog_available_count",
    )
    result: dict[str, Any] = {
        key: int((row[key] if row else 0) or 0) for key in numeric_keys
    }
    runtime_snapshot = get_runtime_status_snapshot()
    runtime_valid = bool(runtime_snapshot.get("valid"))
    runtime_data_count = int(runtime_snapshot.get("data_count") or 0) if runtime_valid else 0
    runtime_callable_count = int(runtime_snapshot.get("callable_count") or 0) if runtime_valid else 0
    runtime_coverage_count = int(runtime_snapshot.get("coverage_count") or 0) if runtime_valid else 0

    # Backward-compatible keys now follow the latest valid runtime report when
    # one exists.  The catalog-derived value remains available separately.
    result["available_count"] = (
        runtime_data_count if runtime_valid else result["catalog_available_count"]
    )
    result["unavailable_count"] = max(
        result["document_count"] - result["available_count"], 0
    )
    result.update({
        "runtime_report_valid": runtime_valid,
        "runtime_report_name": runtime_snapshot.get("report_name") or "",
        "runtime_report_time": runtime_snapshot.get("report_time") or "",
        "runtime_report_age_seconds": runtime_snapshot.get("report_age_seconds"),
        "runtime_report_stale": runtime_report_is_stale(runtime_snapshot),
        "runtime_coverage_count": runtime_coverage_count,
        "runtime_callable_count": runtime_callable_count,
        "runtime_data_count": runtime_data_count,
        "runtime_direct_count": int(runtime_snapshot.get("direct_count") or 0) if runtime_valid else 0,
        "runtime_fallback_count": int(runtime_snapshot.get("fallback_count") or 0) if runtime_valid else 0,
        "runtime_callable_empty_count": int(runtime_snapshot.get("callable_empty_count") or 0) if runtime_valid else 0,
        "runtime_uncallable_count": int(runtime_snapshot.get("uncallable_count") or 0) if runtime_valid else 0,
        "runtime_problem_counts": dict(runtime_snapshot.get("problem_counts") or {}) if runtime_valid else {},
    })
    sync_status = full_api_docs_status()
    result.update({
        "expected_generated_count": len(FULL_API_DOCS),
        "installed_generated_count": int(sync_status.get("installed_count") or 0),
        "expected_version": sync_status.get("expected_version") or "",
        "installed_version": sync_status.get("installed_version") or "",
        "catalog_fingerprint": sync_status.get("expected_fingerprint") or "",
        "installed_catalog_fingerprint": sync_status.get("installed_fingerprint") or "",
        "route_count": None,
        "missing_route_count": None,
    })

    category_where = ""
    if public_only:
        category_where = (
            " WHERE c.status='active' AND EXISTS ("
            "SELECT 1 FROM api_doc_endpoints e2 "
            "WHERE e2.category_id=c.id AND e2.status='active')"
        )
    cur.execute(
        "SELECT COUNT(*) AS category_count, MAX(COALESCE(updated_at,'')) AS category_updated "
        "FROM api_doc_categories c" + category_where
    )
    category_row = cur.fetchone()
    cur.execute(
        "SELECT MAX(COALESCE(e.updated_at,'')) AS endpoint_updated "
        "FROM api_doc_endpoints e" + where_sql
    )
    endpoint_row = cur.fetchone()
    result["category_count"] = int((category_row["category_count"] if category_row else 0) or 0)
    if include_route_stats and has_app_context():
        cur.execute(
            "SELECT method,path FROM api_doc_endpoints e" + where_sql
        )
        adapter = current_app.url_map.bind("localhost")
        route_count = 0
        for endpoint in cur.fetchall():
            path = str(endpoint["path"] or "").split("?", 1)[0] or "/"
            method = str(endpoint["method"] or "GET").upper()
            try:
                adapter.match(path, method=method)
                route_count += 1
            except RequestRedirect:
                route_count += 1
            except (NotFound, MethodNotAllowed):
                continue
        result["route_count"] = route_count
        result["missing_route_count"] = max(result["document_count"] - route_count, 0)

    revision_payload = {
        "catalog": result["catalog_fingerprint"],
        "installed_catalog": result["installed_catalog_fingerprint"],
        "document_count": result["document_count"],
        "category_count": result["category_count"],
        "active_count": result["active_count"],
        "category_updated": category_row["category_updated"] if category_row else "",
        "endpoint_updated": endpoint_row["endpoint_updated"] if endpoint_row else "",
        "route_count": result["route_count"],
        "missing_route_count": result["missing_route_count"],
        "runtime_report": result["runtime_report_name"],
        "runtime_report_time": result["runtime_report_time"],
        "runtime_callable_count": result["runtime_callable_count"],
        "runtime_data_count": result["runtime_data_count"],
        "runtime_uncallable_count": result["runtime_uncallable_count"],
    }
    result["ui_revision"] = hashlib.sha256(
        json.dumps(revision_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return result

def ensure_default_api_docs() -> None:
    """Install generated docs only when the read-only status check is stale."""
    status = full_api_docs_status()
    if (
        status["installed_version"] == status["expected_version"]
        and status["installed_count"] == status["expected_count"]
        and status["installed_fingerprint"] == status["expected_fingerprint"]
    ):
        return
    sync_full_api_docs(force=False)


def list_categories(include_hidden: bool = False) -> list[dict[str, Any]]:
    ensure_default_api_docs()
    conn = get_conn()
    cur = conn.cursor()
    sql = "SELECT * FROM api_doc_categories"
    params: list[Any] = []
    if not include_hidden:
        sql += " WHERE status='active'"
    sql += " ORDER BY sort_order ASC, id ASC"
    cur.execute(sql, params)
    return rows_to_dicts(cur.fetchall())


def get_category(category_id: int) -> dict[str, Any] | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM api_doc_categories WHERE id=?", (category_id,))
    return row_to_dict(cur.fetchone())


def create_category(name: str, description: str = "", sort_order: int = 100, status: str = "active") -> int:
    name = (name or "").strip()
    if not name:
        raise ValueError("类目名称不能为空")
    now = _now()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO api_doc_categories (name, description, sort_order, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, description, int(sort_order or 100), status or "active", now, now),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_category(category_id: int, name: str, description: str = "", sort_order: int = 100, status: str = "active") -> None:
    name = (name or "").strip()
    if not name:
        raise ValueError("类目名称不能为空")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE api_doc_categories
        SET name=?, description=?, sort_order=?, status=?, updated_at=?
        WHERE id=?
        """,
        (name, description, int(sort_order or 100), status or "active", _now(), int(category_id)),
    )
    conn.commit()


def list_endpoints(include_hidden: bool = True) -> list[dict[str, Any]]:
    ensure_default_api_docs()
    conn = get_conn()
    cur = conn.cursor()
    sql = """
        SELECT e.*, c.name AS category_name
        FROM api_doc_endpoints e
        LEFT JOIN api_doc_categories c ON c.id = e.category_id
    """
    if not include_hidden:
        sql += " WHERE e.status='active' AND c.status='active'"
    sql += " ORDER BY c.sort_order ASC, c.id ASC, e.sort_order ASC, e.id ASC"
    cur.execute(sql)
    return rows_to_dicts(cur.fetchall())


def get_endpoint(endpoint_id: int) -> dict[str, Any] | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM api_doc_endpoints WHERE id=?", (endpoint_id,))
    return row_to_dict(cur.fetchone())


def create_endpoint(**kwargs: Any) -> int:
    category_id = int(kwargs.get("category_id") or 0)
    title = (kwargs.get("title") or "").strip()
    path = (kwargs.get("path") or "").strip()
    if not category_id:
        raise ValueError("必须选择所属类目")
    if not title:
        raise ValueError("接口名称不能为空")
    if not path:
        raise ValueError("接口路径不能为空")
    now = _now()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO api_doc_endpoints (
            category_id, title, method, path, scope, description,
            params_text, headers_text, request_example, response_example,
            error_codes, sort_order, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            category_id,
            title,
            (kwargs.get("method") or "GET").upper(),
            path,
            kwargs.get("scope") or "",
            kwargs.get("description") or "",
            kwargs.get("params_text") or "",
            kwargs.get("headers_text") or DEFAULT_HEADERS,
            kwargs.get("request_example") or "",
            kwargs.get("response_example") or DEFAULT_RESPONSE,
            kwargs.get("error_codes") or DEFAULT_ERROR_CODES,
            int(kwargs.get("sort_order") or 100),
            kwargs.get("status") or "active",
            now,
            now,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_endpoint(endpoint_id: int, **kwargs: Any) -> None:
    category_id = int(kwargs.get("category_id") or 0)
    title = (kwargs.get("title") or "").strip()
    path = (kwargs.get("path") or "").strip()
    if not category_id:
        raise ValueError("必须选择所属类目")
    if not title:
        raise ValueError("接口名称不能为空")
    if not path:
        raise ValueError("接口路径不能为空")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE api_doc_endpoints
        SET category_id=?, title=?, method=?, path=?, scope=?, description=?,
            params_text=?, headers_text=?, request_example=?, response_example=?,
            error_codes=?, sort_order=?, status=?, updated_at=?
        WHERE id=?
        """,
        (
            category_id,
            title,
            (kwargs.get("method") or "GET").upper(),
            path,
            kwargs.get("scope") or "",
            kwargs.get("description") or "",
            kwargs.get("params_text") or "",
            kwargs.get("headers_text") or DEFAULT_HEADERS,
            kwargs.get("request_example") or "",
            kwargs.get("response_example") or DEFAULT_RESPONSE,
            kwargs.get("error_codes") or DEFAULT_ERROR_CODES,
            int(kwargs.get("sort_order") or 100),
            kwargs.get("status") or "active",
            _now(),
            int(endpoint_id),
        ),
    )
    conn.commit()


def delete_endpoint(endpoint_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM api_doc_endpoints WHERE id=?", (int(endpoint_id),))
    conn.commit()


def list_public_docs() -> list[dict[str, Any]]:
    """用户端展示用：只返回 active 类目和 active 接口。"""
    ensure_default_api_docs()
    categories = list_categories(include_hidden=False)
    endpoints = list_endpoints(include_hidden=False)
    by_cat: dict[int, list[dict[str, Any]]] = {}
    runtime_snapshot = get_runtime_status_snapshot()
    for ep in endpoints:
        ep = dict(ep)
        ep["runtime_status"] = runtime_status_for_path(
            str(ep.get("path") or ""), runtime_snapshot
        )
        by_cat.setdefault(int(ep["category_id"]), []).append(ep)
    result = []
    for cat in categories:
        endpoints_for_category = by_cat.get(int(cat["id"]), [])
        if not endpoints_for_category:
            continue
        cat = dict(cat)
        cat["endpoints"] = endpoints_for_category
        result.append(cat)
    return result
