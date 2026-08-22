# 统一行情路径改造报告

## 1. 改造目标

本次在多数据源 Provider 版本上继续收口接口地址：

- 删除 Tushare 专用兼容蓝图；
- 只保留统一行情入口 `/api/v1/market/<provider>/<data_type>`；
- Tushare、开盘啦、MiniQMT 使用同一套路由、鉴权、限流、缓存和日志；
- 将原先 Tushare 专用缓存管理接口移动为数据源无关的统一缓存接口；
- 自动更新已有数据库中的 API 文档示例，避免用户中心继续显示过期地址。

## 2. 修改前

修改前同时存在两套路由层：

```text
routes/tushare_routes.py       # Tushare 专用兼容入口
routes/market_data_routes.py   # 多数据源统一入口
```

这会带来以下问题：

- 同一个 Tushare 接口有两个 URL；
- 两套参数解析方式存在差异；
- 文档、用户中心和测试脚本容易继续使用兼容地址；
- 缓存管理接口挂在 Tushare 路由下，不符合多数据源架构；
- 后续新增数据源时，维护者难以判断应使用哪一路径。

## 3. 修改后

正式行情路由只剩一套：

```text
routes/market_data_routes.py
        ↓
services/market_data_service.py
        ↓
integrations/market_data/registry.py
        ↓
Tushare / 开盘啦 / MiniQMT Provider
```

正式地址：

```text
GET  /api/v1/market/providers
GET  /api/v1/market/<provider>/catalog
GET  /api/v1/market/<provider>/health
GET/POST /api/v1/market/<provider>/<data_type>
```

示例：

```text
POST /api/v1/market/tushare/daily
POST /api/v1/market/kaipanla/morning_bidding
POST /api/v1/market/miniqmt/history
```

缓存管理也统一为：

```text
GET  /api/v1/market/cache/stats
POST /api/v1/market/cache/clear
```

## 4. 代码改动

### 删除

```text
routes/tushare_routes.py
```

### 修改 `app.py`

- 删除 `tushare_bp` 导入；
- 删除 Tushare 专用蓝图注册；
- 首页文档地址全部改为统一行情入口。

### 修改 `routes/market_data_routes.py`

- 继续负责数据源列表、目录、健康检查和数据查询；
- 新增统一缓存状态与清理接口；
- JSON 平铺参数和 `params` 嵌套参数都由同一个入口处理。

### 修改 Tushare Provider

- Tushare 接口目录中的 `url` 只输出统一地址；
- 删除与 `url` 内容重复的 `market_url` 字段；
- Tushare SDK、官方接口和中转接口底层调用没有改变。

### 修改用户端和后台文档

已更新：

```text
routes/user_routes.py
routes/admin_api_doc_routes.py
services/api_doc_service.py
README.md
```

用户中心、管理员接口文档占位符、默认接口文档和调用示例现在都只显示统一地址。

### 数据库中的历史文档自动迁移

`db_utils.init_db()` 启动时会检查 `api_doc_endpoints`，将已有接口文档中的 Tushare 专用地址改为统一地址。该逻辑只迁移数据库文本，不会重新注册被删除的 HTTP 路由。

## 5. 行为变化

- 新地址继续正常工作；
- 被删除的 Tushare 专用地址不再重定向，也不再兼容，访问时返回 404；
- Tushare、开盘啦和 MiniQMT 的数据源实现未被删除；
- 套餐权限、每分钟限流、每日额度、Redis、缓存、日志和并发设计保持不变；
- 开盘啦 `MorningBiddingList` 请求与字段解析保持不变。

## 6. 替换建议

最稳妥的方式是：备份 `.env` 和 `data/*.db`，然后用新压缩包中的整个 `stock_server` 文件夹替换旧代码目录。不要把新旧源码混合保留。

如果只能覆盖复制，请在覆盖后双击：

```text
cleanup_removed_route.bat
```

它只删除已经废弃的路由文件和 Python 缓存，不会删除 `.env`、数据库或日志。

## 7. 验证结果

```text
Python compileall：通过
自动化测试：27项全部通过
GET /ping：200
已删除的Tushare专用地址：404
新统一Tushare地址（未带Token）：401
新统一缓存地址（未带Token）：401
```

401 表示路由存在且鉴权生效；404 表示被删除的路由没有注册。
