# -*- coding: utf-8 -*-
"""管理员 API 文档管理页面。"""
from html import escape

from flask import Blueprint, jsonify, redirect, request, session

import config
from config import ADMIN_USERNAME
from services.admin_auth import verify_admin_high_risk_confirmation
from services.audit_service import record_operation
from services.site_url import public_url

from services.api_doc_service import (
    create_category,
    create_endpoint,
    delete_endpoint,
    get_category,
    get_endpoint,
    get_api_doc_statistics,
    list_categories,
    list_endpoints,
    sync_full_api_docs,
    update_category,
    update_endpoint,
)

admin_api_doc_bp = Blueprint("admin_api_doc", __name__)


def _require_admin() -> bool:
    return session.get("admin_logged_in") is True


def _audit_doc(
    action_code: str,
    action_name: str,
    success: bool,
    status_code: int,
    *,
    before_data=None,
    after_data=None,
    request_data=None,
    error=None,
    error_code: str = "",
    error_message: str = "",
):
    return record_operation(
        actor_type="admin", actor_id=None, actor_name=ADMIN_USERNAME,
        target_user=None, action_category="api_documentation",
        action_code=action_code, action_name=action_name,
        success=success, status_code=status_code,
        error_code=error_code or ("api_doc_operation_failed" if error else ""),
        error_message=error_message or str(error or ""), before_data=before_data or {},
        after_data=after_data or {}, request_data=request_data or {},
    )


def _nav() -> str:
    user_api_docs_url = escape(public_url("/user/api-docs"), quote=True)
    return f"""
    <nav class="top-nav" aria-label="管理员导航">
        <a href="/admin/members">开通/续费</a>
        <a href="/admin/members/list">用户列表</a>
        <a href="/admin/operation-history">操作历史</a>
        <a href="/admin/data-access-history">数据访问历史</a>
        <a class="current" href="/admin/api-docs">API文档管理</a>
        <a href="/admin/interface-tester">市场接口测试台</a>
        <a href="{user_api_docs_url}" target="_blank" rel="noopener">用户端API文档</a>
        <form method="post" action="/admin/logout" class="csp-r5-6b8b63d565c4986a"><button type="submit">退出登录</button></form>
    </nav>
    """


def _page(title: str, body: str) -> str:
    return f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{escape(title)}</title>
        <link rel="stylesheet" href="/static/csp/r5-inline-attributes.css">
<link rel="stylesheet" href="/static/csp/r5-routes-admin-api-doc-routes-l82-0cb552468e.css">
    </head>
    <body><main class="page-shell">{body}</main></body>
    </html>
    """


def _status_select(value: str) -> str:
    value = value or "active"
    return f"""
    <select name="status">
        <option value="active" {'selected' if value == 'active' else ''}>显示 active</option>
        <option value="hidden" {'selected' if value == 'hidden' else ''}>隐藏 hidden</option>
        <option value="draft" {'selected' if value == 'draft' else ''}>草稿 draft</option>
        <option value="deprecated" {'selected' if value == 'deprecated' else ''}>废弃 deprecated</option>
    </select>
    """


def _status_badge(status: str) -> str:
    safe_status = escape(status or "unknown")
    css_status = status if status in {"active", "hidden", "draft", "deprecated"} else "hidden"
    return f'<span class="status-badge status-{css_status}">{safe_status}</span>'


@admin_api_doc_bp.get("/api-docs/status.json")
def admin_api_docs_status():
    if not _require_admin():
        return jsonify({"success": False, "message": "未登录管理员"}), 401
    statistics = get_api_doc_statistics()
    response = jsonify({
        "success": True,
        "ui_revision": statistics.get("ui_revision") or "",
        "category_count": int(statistics.get("category_count") or 0),
        "document_count": int(statistics.get("document_count") or 0),
        "active_count": int(statistics.get("active_count") or 0),
        "route_count": statistics.get("route_count"),
        "missing_route_count": statistics.get("missing_route_count"),
        "runtime_report_time": statistics.get("runtime_report_time") or "",
        "runtime_callable_count": int(statistics.get("runtime_callable_count") or 0),
        "runtime_data_count": int(statistics.get("runtime_data_count") or 0),
        "runtime_uncallable_count": int(statistics.get("runtime_uncallable_count") or 0),
        "scan_seconds": int(config.API_DOC_STATUS_FILE_SCAN_SECONDS),
        "refresh_interval_seconds": int(config.API_DOC_STATUS_REFRESH_INTERVAL_SECONDS),
        "auto_refresh_enabled": bool(config.API_DOC_STATUS_AUTO_REFRESH_ENABLED),
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@admin_api_doc_bp.route("/api-docs", methods=["GET"])
def admin_api_docs_home():
    if not _require_admin():
        return redirect("/admin/login")

    categories = list_categories(include_hidden=True)
    endpoints = list_endpoints(include_hidden=True)
    statistics = get_api_doc_statistics()
    scan_seconds = int(config.API_DOC_STATUS_FILE_SCAN_SECONDS)
    refresh_interval_seconds = int(config.API_DOC_STATUS_REFRESH_INTERVAL_SECONDS)
    refresh_hours = refresh_interval_seconds / 3600
    auto_refresh_text = "已启用" if config.API_DOC_STATUS_AUTO_REFRESH_ENABLED else "未启用"
    runtime_report_time = str(statistics.get("runtime_report_time") or "暂无有效报告")
    ui_revision = escape(str(statistics.get("ui_revision") or ""), quote=True)

    cat_rows = []
    for category in categories:
        cat_rows.append(f"""
        <tr>
            <td class="nowrap">{category.get('id')}</td>
            <td class="nowrap"><strong>{escape(str(category.get('name') or ''))}</strong></td>
            <td>{escape(str(category.get('description') or ''))}</td>
            <td class="nowrap">{escape(str(category.get('sort_order') or ''))}</td>
            <td class="nowrap">{_status_badge(str(category.get('status') or ''))}</td>
            <td class="nowrap"><a class="btn" href="/admin/api-docs/categories/edit/{category.get('id')}">编辑</a></td>
        </tr>
        """)

    category_options = ['<option value="">全部类目</option>']
    for category_name in sorted({str(item.get("category_name") or "未分类") for item in endpoints}):
        safe_name = escape(category_name, quote=True)
        category_options.append(f'<option value="{safe_name}">{safe_name}</option>')

    status_options = ['<option value="">全部状态</option>']
    for status in sorted({str(item.get("status") or "") for item in endpoints}):
        safe_status = escape(status, quote=True)
        status_options.append(f'<option value="{safe_status}">{safe_status}</option>')

    ep_rows = []
    for endpoint in endpoints:
        category_name = str(endpoint.get("category_name") or "未分类")
        title = str(endpoint.get("title") or "")
        method = str(endpoint.get("method") or "")
        path = str(endpoint.get("path") or "")
        scope = str(endpoint.get("scope") or "")
        status = str(endpoint.get("status") or "")
        search_text = " ".join([category_name, title, method, path, scope, status]).lower()

        ep_rows.append(f"""
        <tr class="endpoint-row"
            data-search="{escape(search_text, quote=True)}"
            data-category="{escape(category_name, quote=True)}"
            data-status="{escape(status, quote=True)}">
            <td class="nowrap">{endpoint.get('id')}</td>
            <td class="nowrap">{escape(category_name)}</td>
            <td class="nowrap"><strong>{escape(title)}</strong></td>
            <td class="nowrap"><span class="method-badge">{escape(method)}</span></td>
            <td title="{escape(path, quote=True)}"><code class="path-code">{escape(path)}</code></td>
            <td title="{escape(scope, quote=True)}"><code class="scope-code">{escape(scope)}</code></td>
            <td class="nowrap">{escape(str(endpoint.get('sort_order') or ''))}</td>
            <td class="nowrap">{_status_badge(status)}</td>
            <td>
                <div class="row-actions">
                    <a class="btn" href="/admin/api-docs/endpoints/edit/{endpoint.get('id')}">编辑</a>
                    <form method="post" action="/admin/api-docs/endpoints/delete/{endpoint.get('id')}" class="csp-r5-6b8b63d565c4986a">
                        <details class="csp-r5-e74fa60fb17e9340">
                            <summary class="btn btn-danger csp-r5-9463ff4798ce317c" >删除</summary>
                            <div class="csp-r5-f2b478cb404ce431">
                                <input type="password" name="admin_password" autocomplete="current-password" required placeholder="当前管理员密码">
                                <input name="confirmation_text" autocomplete="off" required placeholder="DELETE ENDPOINT {endpoint.get('id')}">
                                <small class="muted">精确输入：<code>DELETE ENDPOINT {endpoint.get('id')}</code></small>
                                <button class="btn btn-danger" type="submit" data-confirm="确认删除这个接口文档？">确认删除</button>
                            </div>
                        </details>
                    </form>
                </div>
            </td>
        </tr>
        """)

    category_table_body = "".join(cat_rows) or '<tr><td colspan="6" class="empty-state">暂无类目</td></tr>'
    endpoint_table_body = "".join(ep_rows) or '<tr><td colspan="9" class="empty-state">暂无接口文档</td></tr>'
    user_api_docs_url = escape(public_url("/user/api-docs"), quote=True)

    return _page("API文档管理", f"""
    <div class="page-title-row">
        <div>
            <h2>API文档管理</h2>
            <div class="muted">维护平台接口说明、套餐Scope和用户端展示内容。</div>
        </div>
        <div class="actions">
            <a class="btn" href="{user_api_docs_url}" target="_blank" rel="noopener">打开用户端文档</a>
            <a class="btn btn-primary" href="/admin/api-docs/endpoints/new">新增接口</a>
        </div>
    </div>
    {_nav()}

    <section class="stats" aria-label="API文档统计">
        <div class="stat"><strong>{len(categories)}</strong><span>类目总数</span></div>
        <div class="stat"><strong>{statistics.get('document_count')}</strong><span>接口文档总数</span></div>
        <div class="stat"><strong>{statistics.get('generated_count')}</strong><span>自动生成文档</span></div>
        <div class="stat"><strong>{statistics.get('custom_count')}</strong><span>自定义文档</span></div>
        <div class="stat"><strong>{statistics.get('active_count')}</strong><span>active接口</span></div>
        <div class="stat"><strong>{statistics.get('non_active_count')}</strong><span>其他状态接口</span></div>
        <div class="stat"><strong>{statistics.get('route_count') if statistics.get('route_count') is not None else '未检测'}</strong><span>实际路由存在</span></div>
        <div class="stat"><strong>{statistics.get('missing_route_count') if statistics.get('missing_route_count') is not None else '未检测'}</strong><span>未检测到路由</span></div>
        <div class="stat"><strong>{statistics.get('runtime_callable_count') or 0}</strong><span>最近实测可调用</span></div>
        <div class="stat"><strong>{statistics.get('runtime_data_count') or 0}</strong><span>最近实测取得数据</span></div>
        <div class="stat"><strong>{statistics.get('runtime_uncallable_count') or 0}</strong><span>最近实测不可调用</span></div>
    </section>
    <p class="muted" id="apiDocRefreshExplanation">
        页面每{scan_seconds}秒检查一次目录和实测报告变化，发现变化后自动刷新全部统计、类目、接口目录和实测状态。
        全接口自动实测：{auto_refresh_text}；计划间隔：{refresh_hours:g}小时；最近有效报告：{escape(runtime_report_time)}。
    </p>

    <div class="panel">
        <div class="panel-body">
            <details class="tips">
                <summary>完整{statistics.get('expected_generated_count')}接口文档说明与重建操作</summary>
                <p>这里维护的是“平台API接口文档”。新增文档不会自动创建真实接口，真实接口仍需要在代码里开发。</p>
                <p>完整目录状态：已安装 <b>{statistics.get('installed_generated_count')}</b> / {statistics.get('expected_generated_count')} 个自动生成接口，
                版本 <code>{escape(str(statistics.get('installed_version') or '未安装'))}</code>。</p>
                <p>
                    <form method="post" action="/admin/api-docs/sync-full" class="csp-r5-6b8b63d565c4986a">
                        <input type="password" name="admin_password" autocomplete="current-password" required placeholder="当前管理员密码">
                        <input name="confirmation_text" autocomplete="off" required placeholder="REBUILD API DOCS">
                        <span class="muted">精确输入 <code>REBUILD API DOCS</code></span>
                        <button class="btn" type="submit"
                           data-confirm="将重新生成{statistics.get('expected_generated_count')}个Tushare/开盘啦接口文档。管理员对这些自动生成接口的手工修改会被覆盖，是否继续？">
                           重新生成完整{statistics.get('expected_generated_count')}接口文档
                        </button>
                    </form>
                </p>
                <p>同步会自动删除两条已下线旧文档；其他非Tushare/开盘啦路径的自定义文档继续保留。</p>
            </details>
        </div>
    </div>

    <section class="panel">
        <div class="panel-head">
            <div><h3>类目</h3><div class="muted">接口文档的一级分组。</div></div>
            <a class="btn btn-primary" href="/admin/api-docs/categories/new">新增类目</a>
        </div>
        <div class="panel-body">
            <div class="table-scroll categories" role="region" aria-label="类目列表" tabindex="0">
                <table class="category-table">
                    <thead><tr><th>ID</th><th>类目名称</th><th>说明</th><th>排序</th><th>状态</th><th>操作</th></tr></thead>
                    <tbody>{category_table_body}</tbody>
                </table>
            </div>
        </div>
    </section>

    <section class="panel">
        <div class="panel-head">
            <div><h3>接口</h3><div class="muted">支持搜索、类目筛选、状态筛选和横向/纵向滚动。</div></div>
            <a class="btn btn-primary" href="/admin/api-docs/endpoints/new">新增接口</a>
        </div>
        <div class="panel-body">
            <div class="toolbar" aria-label="接口筛选工具栏">
                <input id="endpointSearch" type="search" placeholder="搜索接口名称、类目、路径或Scope" autocomplete="off">
                <select id="categoryFilter">{''.join(category_options)}</select>
                <select id="statusFilter">{''.join(status_options)}</select>
                <button class="btn" id="clearFilters" type="button">清空筛选</button>
            </div>
            <p class="scroll-hint">
                当前显示 <strong id="visibleEndpointCount">{len(endpoints)}</strong> / {len(endpoints)} 个接口。
                表格区域可上下滚动；路径较长时可左右滑动，表头、ID列和操作列会保持可见。
            </p>
            <div class="table-scroll endpoints" role="region" aria-label="接口文档列表" tabindex="0">
                <table class="endpoint-table">
                    <colgroup>
                        <col class="col-id"><col class="col-category"><col class="col-title"><col class="col-method">
                        <col class="col-path"><col class="col-scope"><col class="col-sort"><col class="col-status"><col class="col-actions">
                    </colgroup>
                    <thead>
                        <tr><th>ID</th><th>类目</th><th>接口名称</th><th>方式</th><th>路径</th><th>Scope</th><th>排序</th><th>状态</th><th>操作</th></tr>
                    </thead>
                    <tbody id="endpointTableBody">
                        {endpoint_table_body}
                        <tr id="noEndpointMatch" hidden><td colspan="9" class="empty-state">没有符合筛选条件的接口。</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </section>

    <script>
    (() => {{
        const search = document.getElementById('endpointSearch');
        const category = document.getElementById('categoryFilter');
        const status = document.getElementById('statusFilter');
        const clear = document.getElementById('clearFilters');
        const count = document.getElementById('visibleEndpointCount');
        const noMatch = document.getElementById('noEndpointMatch');
        const rows = Array.from(document.querySelectorAll('.endpoint-row'));

        function applyFilters() {{
            const keyword = search.value.trim().toLowerCase();
            const categoryValue = category.value;
            const statusValue = status.value;
            let visible = 0;

            rows.forEach((row) => {{
                const matchKeyword = !keyword || row.dataset.search.includes(keyword);
                const matchCategory = !categoryValue || row.dataset.category === categoryValue;
                const matchStatus = !statusValue || row.dataset.status === statusValue;
                const show = matchKeyword && matchCategory && matchStatus;
                row.hidden = !show;
                if (show) visible += 1;
            }});

            count.textContent = String(visible);
            noMatch.hidden = visible !== 0;
        }}

        search.addEventListener('input', applyFilters);
        category.addEventListener('change', applyFilters);
        status.addEventListener('change', applyFilters);
        clear.addEventListener('click', () => {{
            search.value = '';
            category.value = '';
            status.value = '';
            applyFilters();
            search.focus();
        }});

        let currentRevision = '{ui_revision}';
        const pollIntervalMs = Math.max({scan_seconds}, 5) * 1000;
        async function pollApiDocRevision() {{
            try {{
                const response = await fetch('/admin/api-docs/status.json', {{
                    credentials: 'same-origin',
                    cache: 'no-store'
                }});
                if (!response.ok) return;
                const payload = await response.json();
                const nextRevision = String(payload.ui_revision || '');
                if (currentRevision && nextRevision && nextRevision !== currentRevision) {{
                    sessionStorage.setItem('adminApiDocsScrollY', String(window.scrollY || 0));
                    window.location.reload();
                    return;
                }}
                currentRevision = nextRevision || currentRevision;
            }} catch (error) {{
                console.warn('API文档状态检查失败', error);
            }}
        }}
        const savedScrollY = Number(sessionStorage.getItem('adminApiDocsScrollY') || 0);
        if (savedScrollY > 0) {{
            sessionStorage.removeItem('adminApiDocsScrollY');
            window.scrollTo(0, savedScrollY);
        }}
        window.setInterval(pollApiDocRevision, pollIntervalMs);
    }})();
    </script>
    """)


@admin_api_doc_bp.post("/api-docs/sync-full")
def sync_full_api_docs_page():
    if not _require_admin():
        return redirect("/admin/login")
    confirmation = verify_admin_high_risk_confirmation(
        request.form.get("admin_password") or "",
        request.form.get("confirmation_text") or "",
        "REBUILD API DOCS",
    )
    if not confirmation.ok:
        _audit_doc(
            "admin.api_docs_sync",
            "同步完整API文档",
            False,
            403,
            request_data={"force": True},
            error_code=confirmation.code,
            error_message=confirmation.message,
        )
        return _page(
            "同步API文档二次确认失败",
            f"<h2 class='error'>操作已拒绝：{escape(confirmation.message)}</h2>{_nav()}",
        ), 403
    try:
        result = sync_full_api_docs(force=True)
        _audit_doc("admin.api_docs_sync", "同步完整API文档", True, 200, after_data=result or {}, request_data={"force": True})
        return redirect("/admin/api-docs")
    except Exception as exc:
        _audit_doc("admin.api_docs_sync", "同步完整API文档", False, 500, request_data={"force": True}, error=exc)
        return _page("同步API文档失败", f"<h2 class='error'>同步失败：{escape(str(exc))}</h2>{_nav()}"), 500


@admin_api_doc_bp.route("/api-docs/categories/new", methods=["GET", "POST"])
def new_category():
    if not _require_admin():
        return redirect("/admin/login")

    if request.method == "POST":
        try:
            form_data = {
                "name": request.form.get("name", ""),
                "description": request.form.get("description", ""),
                "sort_order": int(request.form.get("sort_order") or 100),
                "status": request.form.get("status") or "active",
            }
            created = create_category(**form_data)
            _audit_doc("admin.api_doc_category_create", "新增API文档类目", True, 200, after_data={"result": created}, request_data=form_data)
        except Exception as exc:
            _audit_doc("admin.api_doc_category_create", "新增API文档类目", False, 400, request_data=request.form.to_dict(flat=True), error=exc)
            return _page("新增类目失败", f"<h2 class='error'>新增失败：{escape(str(exc))}</h2>{_nav()}"), 400
        return redirect("/admin/api-docs")

    return _page("新增API文档类目", f"""
    <h2>新增API文档类目</h2>
    {_nav()}
    <form method="post">
        <p>类目名称：<input name="name" required placeholder="例如：实时行情"></p>
        <p>类目说明：<input name="description" placeholder="例如：实时行情、早盘竞价、盘口数据等接口"></p>
        <p>排序值：<input name="sort_order" value="100"></p>
        <p>状态：{_status_select('active')}</p>
        <button class="btn btn-primary" type="submit">保存类目</button>
    </form>
    """)


@admin_api_doc_bp.route("/api-docs/categories/edit/<int:category_id>", methods=["GET", "POST"])
def edit_category(category_id: int):
    if not _require_admin():
        return redirect("/admin/login")
    category = get_category(category_id)
    if not category:
        return "类目不存在", 404

    if request.method == "POST":
        try:
            form_data = {
                "name": request.form.get("name", ""),
                "description": request.form.get("description", ""),
                "sort_order": int(request.form.get("sort_order") or 100),
                "status": request.form.get("status") or "active",
            }
            update_category(category_id, **form_data)
            _audit_doc("admin.api_doc_category_update", "编辑API文档类目", True, 200, before_data=category, after_data={"id": category_id, **form_data}, request_data=form_data)
        except Exception as exc:
            _audit_doc("admin.api_doc_category_update", "编辑API文档类目", False, 400, before_data=category, request_data=request.form.to_dict(flat=True), error=exc)
            return _page("编辑类目失败", f"<h2 class='error'>保存失败：{escape(str(exc))}</h2>{_nav()}"), 400
        return redirect("/admin/api-docs")

    return _page("编辑API文档类目", f"""
    <h2>编辑API文档类目</h2>
    {_nav()}
    <form method="post">
        <p>类目名称：<input name="name" required value="{escape(str(category.get('name') or ''))}"></p>
        <p>类目说明：<input name="description" value="{escape(str(category.get('description') or ''))}"></p>
        <p>排序值：<input name="sort_order" value="{escape(str(category.get('sort_order') or 100))}"></p>
        <p>状态：{_status_select(str(category.get('status') or 'active'))}</p>
        <button class="btn btn-primary" type="submit">保存修改</button>
    </form>
    """)


def _endpoint_form(endpoint: dict | None = None) -> str:
    endpoint = endpoint or {}
    categories = list_categories(include_hidden=True)
    category_options = []
    current_cat = str(endpoint.get("category_id") or "")
    for category in categories:
        category_id = str(category.get("id"))
        category_options.append(
            f'<option value="{escape(category_id)}" {"selected" if category_id == current_cat else ""}>{escape(str(category.get("name") or ""))}</option>'
        )

    method = (endpoint.get("method") or "GET").upper()
    method_options = "".join(
        f'<option value="{item}" {"selected" if method == item else ""}>{item}</option>'
        for item in ["GET", "POST", "PUT", "DELETE"]
    )

    return f"""
    <form method="post">
        <p>所属类目：<select name="category_id" required>{''.join(category_options)}</select></p>
        <p>接口名称：<input name="title" required value="{escape(str(endpoint.get('title') or ''))}" placeholder="例如：批量实时行情"></p>
        <p>请求方式：<select name="method">{method_options}</select></p>
        <p>接口路径：<input name="path" required value="{escape(str(endpoint.get('path') or ''))}" placeholder="例如：/api/v1/market/tushare/stock_basic?list_status=L"></p>
        <p>权限 Scope：<input name="scope" value="{escape(str(endpoint.get('scope') or ''))}" placeholder="例如：tushare:points15000:read"></p>
        <p>接口说明：</p>
        <textarea name="description" placeholder="说明这个接口用途">{escape(str(endpoint.get('description') or ''))}</textarea>
        <p>请求参数：</p>
        <p class="muted">每行一个参数，格式：参数名|类型|是否必填|示例|说明</p>
        <textarea name="params_text" placeholder="symbols|string|是|000001.SZ,600000.SH|股票代码，多个用英文逗号分隔">{escape(str(endpoint.get('params_text') or ''))}</textarea>
        <p>请求头：</p>
        <textarea name="headers_text" placeholder="X-API-Token: 用户自己的Token">{escape(str(endpoint.get('headers_text') or ''))}</textarea>
        <p>请求示例，可选：</p>
        <textarea name="request_example" placeholder="GET /api/v1/...">{escape(str(endpoint.get('request_example') or ''))}</textarea>
        <p>返回示例：</p>
        <textarea name="response_example" class="csp-r5-8851b427add32e2b" placeholder='{{"success": true, "data": []}}'>{escape(str(endpoint.get('response_example') or ''))}</textarea>
        <p>错误码说明：</p>
        <textarea name="error_codes">{escape(str(endpoint.get('error_codes') or ''))}</textarea>
        <p>排序值：<input name="sort_order" value="{escape(str(endpoint.get('sort_order') or 100))}"></p>
        <p>状态：{_status_select(str(endpoint.get('status') or 'active'))}</p>
        <button class="btn btn-primary" type="submit">保存接口文档</button>
    </form>
    """


def _endpoint_form_data() -> dict:
    return {
        "category_id": request.form.get("category_id"),
        "title": request.form.get("title"),
        "method": request.form.get("method"),
        "path": request.form.get("path"),
        "scope": request.form.get("scope"),
        "description": request.form.get("description"),
        "params_text": request.form.get("params_text"),
        "headers_text": request.form.get("headers_text"),
        "request_example": request.form.get("request_example"),
        "response_example": request.form.get("response_example"),
        "error_codes": request.form.get("error_codes"),
        "sort_order": int(request.form.get("sort_order") or 100),
        "status": request.form.get("status") or "active",
    }


@admin_api_doc_bp.route("/api-docs/endpoints/new", methods=["GET", "POST"])
def new_endpoint():
    if not _require_admin():
        return redirect("/admin/login")

    if request.method == "POST":
        try:
            form_data = _endpoint_form_data()
            created = create_endpoint(**form_data)
            _audit_doc("admin.api_doc_endpoint_create", "新增API接口文档", True, 200, after_data={"result": created}, request_data=form_data)
        except Exception as exc:
            _audit_doc("admin.api_doc_endpoint_create", "新增API接口文档", False, 400, request_data=request.form.to_dict(flat=True), error=exc)
            return _page("新增接口文档失败", f"<h2 class='error'>新增失败：{escape(str(exc))}</h2>{_nav()}{_endpoint_form()}"), 400
        return redirect("/admin/api-docs")

    return _page("新增接口文档", f"""
    <h2>新增接口文档</h2>
    {_nav()}
    {_endpoint_form()}
    """)


@admin_api_doc_bp.route("/api-docs/endpoints/edit/<int:endpoint_id>", methods=["GET", "POST"])
def edit_endpoint(endpoint_id: int):
    if not _require_admin():
        return redirect("/admin/login")
    endpoint = get_endpoint(endpoint_id)
    if not endpoint:
        return "接口文档不存在", 404

    if request.method == "POST":
        try:
            form_data = _endpoint_form_data()
            update_endpoint(endpoint_id, **form_data)
            _audit_doc("admin.api_doc_endpoint_update", "编辑API接口文档", True, 200, before_data=endpoint, after_data={"id": endpoint_id, **form_data}, request_data=form_data)
        except Exception as exc:
            _audit_doc("admin.api_doc_endpoint_update", "编辑API接口文档", False, 400, before_data=endpoint, request_data=request.form.to_dict(flat=True), error=exc)
            return _page("编辑接口文档失败", f"<h2 class='error'>保存失败：{escape(str(exc))}</h2>{_nav()}{_endpoint_form(endpoint)}"), 400
        return redirect("/admin/api-docs")

    return _page("编辑接口文档", f"""
    <h2>编辑接口文档</h2>
    {_nav()}
    {_endpoint_form(endpoint)}
    """)


@admin_api_doc_bp.post("/api-docs/endpoints/delete/<int:endpoint_id>")
def delete_endpoint_page(endpoint_id: int):
    if not _require_admin():
        return redirect("/admin/login")
    endpoint = get_endpoint(endpoint_id)
    confirmation = verify_admin_high_risk_confirmation(
        request.form.get("admin_password") or "",
        request.form.get("confirmation_text") or "",
        f"DELETE ENDPOINT {int(endpoint_id)}",
    )
    if not confirmation.ok:
        _audit_doc(
            "admin.api_doc_endpoint_delete",
            "删除API接口文档",
            False,
            403,
            before_data=endpoint or {},
            request_data={"endpoint_id": endpoint_id},
            error_code=confirmation.code,
            error_message=confirmation.message,
        )
        return _page(
            "删除接口文档二次确认失败",
            f"<h2 class='error'>操作已拒绝：{escape(confirmation.message)}</h2>{_nav()}",
        ), 403
    try:
        delete_endpoint(endpoint_id)
        _audit_doc("admin.api_doc_endpoint_delete", "删除API接口文档", True, 200, before_data=endpoint or {}, after_data={"deleted": True, "id": endpoint_id}, request_data={"endpoint_id": endpoint_id})
        return redirect("/admin/api-docs")
    except Exception as exc:
        _audit_doc("admin.api_doc_endpoint_delete", "删除API接口文档", False, 500, before_data=endpoint or {}, request_data={"endpoint_id": endpoint_id}, error=exc)
        return _page("删除接口文档失败", f"<h2 class='error'>删除失败：{escape(str(exc))}</h2>{_nav()}"), 500
