# 本次删除、修改和新增文件清单

## 一、必须删除

```text
routes/tushare_routes.py
```

原因：该文件是已经废弃的 Tushare 专用兼容蓝图。统一数据源路由已经完整覆盖其数据查询、目录和健康检查能力。

## 二、功能迁移

原 Tushare 专用缓存管理能力迁移到：

```text
routes/market_data_routes.py
```

新地址：

```text
GET  /api/v1/market/cache/stats
POST /api/v1/market/cache/clear
```

## 三、修改文件

```text
app.py
README.md
db_utils.py
routes/market_data_routes.py
routes/user_routes.py
routes/admin_api_doc_routes.py
services/api_doc_service.py
integrations/market_data/tushare/catalog.py
integrations/market_data/tushare/provider.py
tools/cleanup_obsolete_files.py
docs/CODE_REVIEW_REPORT.md
docs/FILE_CLEANUP_MANIFEST.md
docs/REPLACEMENT_GUIDE.md
FINAL_FILE_TREE.txt
```

## 四、新增文件

```text
cleanup_removed_route.bat
run_interface_test.bat
tools/interface_tester.py
docs/EASY_INTERFACE_TESTER.md
tests/test_unified_market_routes.py
```

## 五、不应放入代码包

```text
.env
.venv/
data/*.db
logs/*.log
__pycache__/
*.pyc
.idea/
.vscode/
```

## 六、必须备份

```text
.env
data/*.db
```

这些是配置、会员、Token、套餐和调用统计数据，不能被代码包覆盖。
