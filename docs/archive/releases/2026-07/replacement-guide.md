# 完整替换指南

## 1. 停止服务

在运行服务的窗口按 `Ctrl+C`。

## 2. 备份业务数据

至少备份：

```text
.env
data/*.db
```

建议把整个旧目录复制一份作为回滚备份。

## 3. 推荐替换方式

1. 将旧目录改名为 `stock_server_backup`；
2. 解压新压缩包；
3. 把旧 `.env` 和 `data/*.db` 复制到新目录；
4. 不要复制旧的 `routes`、`services`、`integrations`、`__pycache__` 或 `.venv`。

这种方式能确保已经删除的文件不会残留。

## 4. 只能覆盖复制时

覆盖完成后双击：

```text
cleanup_removed_route.bat
```

脚本只会清理废弃路由和 Python 缓存，不会删除配置、数据库和日志。

## 5. 依赖

原虚拟环境依赖版本正确时可以继续使用。建议重新安装：

```bash
pip install -r requirements.txt
```

## 6. 启动

Windows：

```bash
python app.py
```

或：

```bash
python run_waitress.py
```

## 7. 启动后检查

无需 Token：

```text
GET /ping
```

需要 `X-API-Token`：

```text
GET /api/v1/market/providers
GET /api/v1/market/tushare/catalog
GET /api/v1/market/tushare/health
GET /api/v1/market/kaipanla/catalog
```

数据请求示例：

```text
POST /api/v1/market/tushare/daily
POST /api/v1/market/kaipanla/morning_bidding
```

管理员缓存接口：

```text
GET  /api/v1/market/cache/stats
POST /api/v1/market/cache/clear
```

## 8. 一键接口测试

服务运行后双击：

```text
run_interface_test.bat
```

可选择测试单条、多条、某个数据源全部接口或全部已注册数据源。

## 9. 数据库文档迁移

启动时程序会自动更新数据库中保存的旧接口文档地址。无需单独运行 SQL，不会修改用户、Token、套餐、订阅或调用统计。

## 10. 验证旧路由已删除

旧地址应返回 HTTP 404；程序不会跳转到新地址。这样可以尽早发现仍未更新的客户端。

## 11. 回滚

1. 停止新服务；
2. 恢复旧目录备份；
3. 恢复旧 `.env` 和数据库；
4. 重新启动旧版本。
