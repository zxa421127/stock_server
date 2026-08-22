# 数据源 Provider 架构

## 1. 核心原则

外部行情来源只负责三件事：

1. 描述自己支持的接口；
2. 执行数据请求；
3. 将结果转换为 pandas DataFrame。

鉴权、套餐、限流、缓存、HTTP 返回和调用日志由公共层处理。

## 2. 调用链

```text
客户端
  ↓
routes/market_data_routes.py
  ↓ middleware/auth.py
services/market_data_service.py
  ↓
ProviderRegistry
  ↓
TushareProvider / KaipanlaProvider / MiniQmtProvider
  ↓
外部SDK或HTTP接口
```

## 3. 新增一个数据源

例如增加 `akshare`：

```text
integrations/market_data/akshare/
├── __init__.py
├── client.py
├── adapter.py
└── provider.py
```

`provider.py` 实现：

```python
from integrations.market_data.base import MarketDataProvider, ProviderResponse

class AkshareProvider(MarketDataProvider):
    code = "akshare"
    display_name = "AkShare"

    def health_check(self):
        return {"available": True}

    def catalog(self):
        return [{"provider": self.code, "api_name": "daily", "title": "日线"}]

    def query(self, data_type, params):
        # 调用 client，并返回 ProviderResponse(DataFrame)
        ...

    def scope_for(self, data_type):
        return "market:akshare:read"
```

然后在 `integrations/market_data/registry.py` 注册：

```python
registry.register(AkshareProvider())
```

并在 `services/plan_catalog.py` 给对应套餐增加：

```text
market:akshare:read
```

其余缓存、限流、日志和统一路由不需要复制。

## 4. MiniQMT 设计边界

当前仅开放行情读取：

- 历史行情；
- 最新快照；
- 历史数据下载；
- 后续实时订阅管理器。

交易下单应单独建立：

```text
integrations/trading/miniqmt/
```

不能直接把 `xttrader` 下单接口暴露在公共行情路由中。

## 5. 数据格式

公共层接受 Provider 返回 DataFrame，并统一序列化为 JSON records。Provider 可以在 `adapter.py` 内将不同 SDK 的字典、DataFrame、嵌套结构转换为稳定表格。

当前没有强行把所有数据源字段改成同一组 OHLC 字段，因为 Tushare 的财务、指数、ETF 等 100 多个接口字段差异很大。对于真正需要跨数据源自动切换的 `daily`、`quote` 等能力，后续可再增加标准模型层。
