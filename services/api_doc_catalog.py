# -*- coding: utf-8 -*-
"""Auto-generated full platform API-document catalog.

Source snapshot:
- Provider interface counts are derived from FULL_API_DOCS at runtime.
- Production snapshot integration: 2026-07-19
- Total public API documents: derived from FULL_API_DOCS.

This module contains document metadata only. It does not create HTTP routes.
"""
from __future__ import annotations

FULL_API_DOCS_VERSION = "20260724_kaipanla_triple_snapshot_v1"
FULL_API_DOCS_GENERATED_AT = "2026-07-23 00:00:00"
FULL_API_DOCS = \
[{'provider': 'kaipanla',
  'api_name': 'morning_bidding',
  'title': '开盘啦早盘竞价（实时标准字段）',
  'category': '开盘啦',
  'category_description': '开盘啦早盘竞价数据接口，属于特殊权限套餐。',
  'category_sort_order': 10,
  'sort_order': 10,
  'method': 'GET',
  'path': '/api/v1/market/kaipanla/morning_bidding?order=1&st=20&index=0&pid_type=0&b_type=4',
  'base_path': '/api/v1/market/kaipanla/morning_bidding',
  'scope': 'market:kaipanla:read',
  'permission_label': '特殊权限（开盘啦）',
  'description': '接口英文名：morning_bidding\n'
                 '套餐权限：特殊权限（开盘啦）\n'
                 '用途：直接请求开盘啦最新早盘集合竞价，不读取历史快照。\n'
                 'Schema版本：kaipanla_bidding.v2。公开结果不再包含原始数字下标、签名卖出额、技术校验字段或limit_step/kpl_list字段。',
  'params': [{'name': 'order', 'type': 'integer', 'required': '参考官网', 'example': '1', 'description': '排序方式'},
             {'name': 'st', 'type': 'integer', 'required': '参考官网', 'example': '20', 'description': '返回记录数量'},
             {'name': 'index', 'type': 'integer', 'required': '参考官网', 'example': '0', 'description': '分页起始位置'},
             {'name': 'pid_type', 'type': 'integer', 'required': '参考官网', 'example': '0', 'description': '竞价数据类型参数'},
             {'name': 'b_type', 'type': 'integer', 'required': '参考官网', 'example': '4', 'description': '竞价榜单类型参数'}],
  'request_example': 'GET /api/v1/market/kaipanla/morning_bidding?order=1&st=20&index=0&pid_type=0&b_type=4',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "kaipanla",\n'
                      '  "data_type": "morning_bidding",\n'
                      '  "source": {\n'
                      '    "provider": "kaipanla",\n'
                      '    "source_provider": "kaipanla",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260717",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "realtime",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "snapshot": {\n'
                      '    "snapshot_id": null,\n'
                      '    "snapshot_type": null,\n'
                      '    "snapshot_time": null,\n'
                      '    "payload_hash": null\n'
                      '  },\n'
                      '  "quality": {\n'
                      '    "data_quality": "complete",\n'
                      '    "schema_version": "kaipanla_bidding.v2",\n'
                      '    "warning": null\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ts_code": "000001.SZ",\n'
                      '      "name": "平安银行",\n'
                      '      "trade_date": "20260717",\n'
                      '      "snapshot_type": null,\n'
                      '      "snapshot_time": null,\n'
                      '      "snapshot_id": null,\n'
                      '      "auction_price": 12.35,\n'
                      '      "auction_pct": 3.21,\n'
                      '      "realtime_pct": 3.15,\n'
                      '      "limit_buy_amount": 86000000,\n'
                      '      "limit_buy_amount_after_0920": 72000000,\n'
                      '      "auction_net_amount": -12000000,\n'
                      '      "auction_match_amount": 36000000,\n'
                      '      "auction_amount": 40000000,\n'
                      '      "auction_turnover": 1.25,\n'
                      '      "main_net_amount": -12000000,\n'
                      '      "main_buy_amount": 24000000,\n'
                      '      "main_sell_amount": 36000000,\n'
                      '      "float_market_value": 1800000000,\n'
                      '      "sector": "银行",\n'
                      '      "limit_up_days": 2,\n'
                      '      "source_provider": "kaipanla",\n'
                      '      "source_api": "morning_bidding",\n'
                      '      "data_quality": "complete",\n'
                      '      "schema_version": "kaipanla_bidding.v2"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': '',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'kaipanla',
  'api_name': 'morning_bidding_history',
  'title': '开盘啦竞价三时点历史快照',
  'category': '开盘啦',
  'category_description': '开盘啦竞价实时数据与09:26、09:31、15:01三时点持久化快照接口，属于特殊权限套餐。',
  'category_sort_order': 10,
  'sort_order': 20,
  'method': 'GET',
  'path': '/api/v1/market/kaipanla/morning_bidding/history?trade_date=20260717&snapshot_type=auction',
  'base_path': '/api/v1/market/kaipanla/morning_bidding/history',
  'scope': 'market:kaipanla:read',
  'permission_label': '特殊权限（开盘啦）',
  'description': '接口英文名：morning_bidding_history\n'
                 '套餐权限：特殊权限（开盘啦）\n'
                 '默认查询auction快照；snapshot_type只允许auction、post_open或close。post_open或close不存在时返回404，不会以auction或Tushare冒充精确命中。\n'
                 'auction在交易日09:26:05采集，post_open在09:31:00采集，close在15:01:00采集；三类快照互不覆盖。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '否',
              'example': '20260717',
              'description': '目标日期，格式YYYYMMDD；省略时返回所选类型的最近快照'},
             {'name': 'snapshot_type',
              'type': 'string',
              'required': '否',
              'example': 'auction',
              'description': '快照类型，只允许 auction、post_open 或 close；默认auction'},
             {'name': 'snapshot_id',
              'type': 'string',
              'required': '否',
              'example': '20260717_092605_auction_abcd1234',
              'description': '精确快照ID；ID中的类型必须与snapshot_type一致'},
             {'name': 'limit',
              'type': 'integer',
              'required': '否',
              'example': '1000',
              'description': '最大返回条数，服务端限制1-10000'}],
  'request_example': 'GET /api/v1/market/kaipanla/morning_bidding/history?trade_date=20260717&snapshot_type=auction\nGET /api/v1/market/kaipanla/morning_bidding/history?trade_date=20260717&snapshot_type=close',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "kaipanla",\n'
                      '  "data_type": "morning_bidding_history",\n'
                      '  "source": {\n'
                      '    "provider": "kaipanla",\n'
                      '    "source_provider": "kaipanla_snapshot",\n'
                      '    "snapshot_type": "auction",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": "20260717",\n'
                      '    "actual_trade_date": "20260717",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_snapshot",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "snapshot": {\n'
                      '    "snapshot_id": "20260717_092605_auction_abcd1234",\n'
                      '    "snapshot_type": "auction",\n'
                      '    "snapshot_time": "2026-07-17 09:26:05",\n'
                      '    "payload_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"\n'
                      '  },\n'
                      '  "quality": {\n'
                      '    "data_quality": "complete",\n'
                      '    "schema_version": "kaipanla_bidding.v2",\n'
                      '    "warning": null\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ts_code": "000001.SZ",\n'
                      '      "name": "平安银行",\n'
                      '      "trade_date": "20260717",\n'
                      '      "snapshot_type": "auction",\n'
                      '      "snapshot_time": "2026-07-17 09:26:05",\n'
                      '      "snapshot_id": "20260717_092605_auction_abcd1234",\n'
                      '      "auction_net_amount": -12000000,\n'
                      '      "auction_match_amount": 36000000,\n'
                      '      "main_net_amount": -12000000,\n'
                      '      "main_buy_amount": 24000000,\n'
                      '      "main_sell_amount": 36000000,\n'
                      '      "limit_up_days": 2,\n'
                      '      "source_provider": "kaipanla",\n'
                      '      "source_api": "morning_bidding",\n'
                      '      "data_quality": "complete",\n'
                      '      "schema_version": "kaipanla_bidding.v2"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条；已返回开盘啦历史快照"\n'
                      '}',
  'official_url': '',
  'test_status': '新增接口（需生产环境凭据验收）',
  'test_count': 0,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'etf_basic',
  'title': 'ETF基本信息',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 20,
  'method': 'GET',
  'path': '/api/v1/market/tushare/etf_basic?list_status=L',
  'base_path': '/api/v1/market/tushare/etf_basic',
  'scope': 'tushare:points8000:read',
  'permission_label': '通用接口（8000积分权限）',
  'description': '接口英文名：etf_basic\n'
                 '套餐权限：通用接口（8000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1605\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=385\n'
                 '限量：单次请求最大返回5000条数据（当前ETF总数未超过2000）\n'
                 '参数和输出字段已按官方接口文档完整维护。',
  'params': [{'name': 'list_status',
              'type': 'string',
              'required': '参考官网',
              'example': 'L',
              'description': '上市状态，例如L为上市'}],
  'request_example': 'GET /api/v1/market/tushare/etf_basic?list_status=L',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "etf_basic",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1605,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "cname": "易方达保证金收益货币市场基金-A",\n'
                      '      "csname": "易方达保证金收益货币ETF-A",\n'
                      '      "custod_name": "交通银行股份有限公司",\n'
                      '      "etf_type": "纯境内",\n'
                      '      "exchange": "SZ",\n'
                      '      "extname": "易方达保证金收益货币ETF-A",\n'
                      '      "index_code": null,\n'
                      '      "index_name": null,\n'
                      '      "list_date": "20141020",\n'
                      '      "list_status": "L",\n'
                      '      "mgr_name": "易方达基金",\n'
                      '      "mgt_fee": 0.15\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1605条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=385',
  'test_status': '正常可用',
  'test_count': 1605,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'etf_index',
  'title': 'ETF跟踪指数',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 30,
  'method': 'GET',
  'path': '/api/v1/market/tushare/etf_index',
  'base_path': '/api/v1/market/tushare/etf_index',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：etf_index\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：560\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=386\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [],
  'request_example': 'GET /api/v1/market/tushare/etf_index',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "etf_index",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 560,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "adj_circle": "自动调整",\n'
                      '      "base_date": "19901219",\n'
                      '      "bp": 100.0,\n'
                      '      "indx_csname": "上证指数",\n'
                      '      "indx_name": "上证综合指数",\n'
                      '      "pub_date": "19910715",\n'
                      '      "pub_party_name": "中证指数有限公司、上海证券交易所",\n'
                      '      "ts_code": "000001.SH"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共560条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=386',
  'test_status': '正常可用',
  'test_count': 560,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'etf_mins',
  'title': 'ETF历史分钟',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 40,
  'method': 'GET',
  'path': '/api/v1/market/tushare/etf_mins?ts_code=510300.SH&freq=1min&start_date=2026-07-13+09%3A00%3A00&end_date=2026-07-13+15%3A30%3A00',
  'base_path': '/api/v1/market/tushare/etf_mins',
  'scope': 'tushare:independent:history:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：etf_mins\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=387\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '510300.SH',
              'description': '证券/指数/ETF代码'},
             {'name': 'freq',
              'type': 'string',
              'required': '参考官网',
              'example': '1min',
              'description': '数据频率，例如1MIN或1min'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '2026-07-13 09:00:00',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '2026-07-13 15:30:00',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET '
                     '/api/v1/market/tushare/etf_mins?ts_code=510300.SH&freq=1min&start_date=2026-07-13+09%3A00%3A00&end_date=2026-07-13+15%3A30%3A00',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "etf_mins",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=387',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'etf_sh_cons',
  'title': '每日篮子组合(沪市PCF)',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 50,
  'method': 'GET',
  'path': '/api/v1/market/tushare/etf_sh_cons?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/etf_sh_cons',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：etf_sh_cons\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：3000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=471\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/etf_sh_cons?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "etf_sh_cons",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 3000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "con_code": "600009.SH",\n'
                      '      "con_name": "上海机场",\n'
                      '      "cpr": "34",\n'
                      '      "exchange": "SH",\n'
                      '      "qty": 300,\n'
                      '      "rdr": "0",\n'
                      '      "sca": null,\n'
                      '      "sub_flag": "允许",\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "510010.SH"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共3000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=471',
  'test_status': '正常可用',
  'test_count': 3000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'etf_share_size',
  'title': 'ETF份额规模',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 60,
  'method': 'GET',
  'path': '/api/v1/market/tushare/etf_share_size?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/etf_share_size',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：etf_share_size\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1596\n'
                 '数据新鲜度：请求20260713，实际返回20260710最近可用数据。\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=408\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/etf_share_size?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "etf_share_size",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": "20260713",\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": true,\n'
                      '    "data_freshness": "latest_available",\n'
                      '    "fallback_attempt_count": 2\n'
                      '  },\n'
                      '  "count": 1596,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "etf_name": "货币ETF易方达",\n'
                      '      "exchange": "SZSE",\n'
                      '      "total_share": 2202.9288,\n'
                      '      "total_size": 2202.9288,\n'
                      '      "trade_date": "20260710",\n'
                      '      "ts_code": "159001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1596条；请求日期20260713尚未发布，已返回最近可用日期20260710的数据"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=408',
  'test_status': '正常可用',
  'test_count': 1596,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'etf_sz_cons',
  'title': '每日篮子组合(深市PCF)',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 70,
  'method': 'GET',
  'path': '/api/v1/market/tushare/etf_sz_cons?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/etf_sz_cons',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：etf_sz_cons\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：3000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=472\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/etf_sz_cons?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "etf_sz_cons",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 3000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "con_code": "159900.SZ",\n'
                      '      "con_name": "申赎现金",\n'
                      '      "cpr": null,\n'
                      '      "exchange": "SZ",\n'
                      '      "qty": 0.0,\n'
                      '      "rdr": null,\n'
                      '      "red_cc": 100.0,\n'
                      '      "sub_cc": 100.0,\n'
                      '      "sub_flag": "必须",\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "159001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共3000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=472',
  'test_status': '正常可用',
  'test_count': 3000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'fund_adj',
  'title': 'ETF复权因子',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 80,
  'method': 'GET',
  'path': '/api/v1/market/tushare/fund_adj?ts_code=510300.SH&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/fund_adj',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：fund_adj\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=199\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '510300.SH',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/fund_adj?ts_code=510300.SH&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "fund_adj",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "adj_factor": 1.2671,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "510300.SH"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=199',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'fund_daily',
  'title': 'ETF日线行情',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 90,
  'method': 'GET',
  'path': '/api/v1/market/tushare/fund_daily?ts_code=510300.SH&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/fund_daily',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：fund_daily\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=127\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '510300.SH',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/fund_daily?ts_code=510300.SH&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "fund_daily",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 7705111.563,\n'
                      '      "change": -0.085,\n'
                      '      "close": 4.744,\n'
                      '      "high": 4.821,\n'
                      '      "low": 4.719,\n'
                      '      "open": 4.802,\n'
                      '      "pct_chg": -1.76,\n'
                      '      "pre_close": 4.829,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "510300.SH",\n'
                      '      "vol": 16190529.68\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=127',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'idx_anns',
  'title': '指数公司公告',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 100,
  'method': 'GET',
  'path': '/api/v1/market/tushare/idx_anns?start_date=20250713&end_date=20260713',
  'base_path': '/api/v1/market/tushare/idx_anns',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：idx_anns\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：414\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=460\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20250713',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/idx_anns?start_date=20250713&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "idx_anns",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 414,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ann_date": "20260713",\n'
                      '      "source": "中证指数",\n'
                      '      "title": "关于终止计算、维护与发布中证海外高收益债券ETF指数的公告",\n'
                      '      "type": "指数发布",\n'
                      '      "url": "https://www.csindex.com.cn/#/about/newsDetail?id=3006163"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共414条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=460',
  'test_status': '正常可用',
  'test_count': 414,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'rt_etf_k',
  'title': 'ETF实时日线',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 110,
  'method': 'GET',
  'path': '/api/v1/market/tushare/rt_etf_k?ts_code=159919.SZ',
  'base_path': '/api/v1/market/tushare/rt_etf_k',
  'scope': 'tushare:independent:realtime:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：rt_etf_k\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=400\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '159919.SZ',
              'description': '证券/指数/ETF代码'}],
  'request_example': 'GET /api/v1/market/tushare/rt_etf_k?ts_code=159919.SZ',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "rt_etf_k",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 1727294361.769,\n'
                      '      "close": 4.949,\n'
                      '      "high": 5.029,\n'
                      '      "low": 4.924,\n'
                      '      "name": "沪深300ETF嘉实",\n'
                      '      "num": 23017,\n'
                      '      "open": 4.996,\n'
                      '      "pre_close": 5.038,\n'
                      '      "ts_code": "159919.SZ",\n'
                      '      "vol": 347824837\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=400',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'rt_etf_min',
  'title': 'ETF实时分钟',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 120,
  'method': 'GET',
  'path': '/api/v1/market/tushare/rt_etf_min?ts_code=510300.SH&freq=1MIN',
  'base_path': '/api/v1/market/tushare/rt_etf_min',
  'scope': 'tushare:independent:realtime:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：rt_etf_min\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=416\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '510300.SH',
              'description': '证券/指数/ETF代码'},
             {'name': 'freq',
              'type': 'string',
              'required': '参考官网',
              'example': '1MIN',
              'description': '数据频率，例如1MIN或1min'}],
  'request_example': 'GET /api/v1/market/tushare/rt_etf_min?ts_code=510300.SH&freq=1MIN',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "rt_etf_min",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 25630883.0,\n'
                      '      "close": 4.744,\n'
                      '      "freq": "1MIN",\n'
                      '      "high": 4.744,\n'
                      '      "low": 4.744,\n'
                      '      "open": 4.744,\n'
                      '      "time": "2026-07-13 15:00:00",\n'
                      '      "ts_code": "510300.SH",\n'
                      '      "vol": 5402800.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=416',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'rt_etf_min_daily',
  'title': 'ETF实时分钟-日累计',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 130,
  'method': 'GET',
  'path': '/api/v1/market/tushare/rt_etf_min_daily?ts_code=510300.SH&freq=1MIN',
  'base_path': '/api/v1/market/tushare/rt_etf_min_daily',
  'scope': 'tushare:independent:realtime:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：rt_etf_min_daily\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：中转路由未配置；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=470\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '510300.SH',
              'description': '证券/指数/ETF代码'},
             {'name': 'freq',
              'type': 'string',
              'required': '参考官网',
              'example': '1MIN',
              'description': '数据频率，例如1MIN或1min'}],
  'request_example': 'GET /api/v1/market/tushare/rt_etf_min_daily?ts_code=510300.SH&freq=1MIN',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "rt_etf_min_daily",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=470',
  'test_status': '中转路由未配置',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'rt_etf_sz_iopv',
  'title': 'ETF实时参考',
  'category': 'ETF专题',
  'category_description': 'ETF基础、行情、持仓组合、实时行情及历史分钟等接口。',
  'category_sort_order': 20,
  'sort_order': 140,
  'method': 'GET',
  'path': '/api/v1/market/tushare/rt_etf_sz_iopv?ts_code=159919.SZ',
  'base_path': '/api/v1/market/tushare/rt_etf_sz_iopv',
  'scope': 'tushare:independent:realtime:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：rt_etf_sz_iopv\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：中转路由未配置；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=454\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '159919.SZ',
              'description': '证券/指数/ETF代码'}],
  'request_example': 'GET /api/v1/market/tushare/rt_etf_sz_iopv?ts_code=159919.SZ',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "rt_etf_sz_iopv",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=454',
  'test_status': '中转路由未配置',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'ci_daily',
  'title': '中信行业指数日行情',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 150,
  'method': 'GET',
  'path': '/api/v1/market/tushare/ci_daily?start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/ci_daily',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：ci_daily\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：4000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=308\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/ci_daily?start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "ci_daily",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 4000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": null,\n'
                      '      "change": 0.0068,\n'
                      '      "close": 124.3407,\n'
                      '      "high": null,\n'
                      '      "low": null,\n'
                      '      "open": null,\n'
                      '      "pct_change": 0.0055,\n'
                      '      "pre_close": 124.3339,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "CI005704.CI",\n'
                      '      "vol": null\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共4000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=308',
  'test_status': '正常可用',
  'test_count': 4000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'ci_index_member',
  'title': '中信行业成分',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 160,
  'method': 'GET',
  'path': '/api/v1/market/tushare/ci_index_member',
  'base_path': '/api/v1/market/tushare/ci_index_member',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：ci_index_member\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：5000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=373\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [],
  'request_example': 'GET /api/v1/market/tushare/ci_index_member',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "ci_index_member",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 5000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "in_date": "20240102",\n'
                      '      "is_new": "Y",\n'
                      '      "l1_code": "CI005016.CI",\n'
                      '      "l1_name": "家电",\n'
                      '      "l2_code": "CI005145.CI",\n'
                      '      "l2_name": "白色家电Ⅱ",\n'
                      '      "l3_code": "CI005306.CI",\n'
                      '      "l3_name": "白色家电Ⅲ",\n'
                      '      "name": "雪祺电气",\n'
                      '      "out_date": null,\n'
                      '      "ts_code": "001387.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共5000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=373',
  'test_status': '正常可用',
  'test_count': 5000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'daily_info',
  'title': '沪深市场每日交易统计',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 170,
  'method': 'GET',
  'path': '/api/v1/market/tushare/daily_info?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/daily_info',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：daily_info\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：11\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=215\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/daily_info?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "daily_info",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 11,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 8208.23,\n'
                      '      "com_count": 1698,\n'
                      '      "exchange": "SH",\n'
                      '      "float_mv": 483725.48,\n'
                      '      "float_share": null,\n'
                      '      "pe": 13.36,\n'
                      '      "total_mv": 503397.56,\n'
                      '      "total_share": null,\n'
                      '      "tr": 1.63,\n'
                      '      "trade_date": "20260713",\n'
                      '      "trans_count": null,\n'
                      '      "ts_code": "SH_A"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共11条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=215',
  'test_status': '正常可用',
  'test_count': 11,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'idx_factor_pro',
  'title': '指数技术面因子(专业版)',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 180,
  'method': 'GET',
  'path': '/api/v1/market/tushare/idx_factor_pro?ts_code=000001.SH&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/idx_factor_pro',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：idx_factor_pro\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=358\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SH',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET '
                     '/api/v1/market/tushare/idx_factor_pro?ts_code=000001.SH&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "idx_factor_pro",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 1334871933.9,\n'
                      '      "asi_bfq": -1319.95857,\n'
                      '      "asit_bfq": 209.46581,\n'
                      '      "atr_bfq": 65.77638,\n'
                      '      "bbi_bfq": 4015.48978,\n'
                      '      "bias1_bfq": -1.946,\n'
                      '      "bias2_bfq": -2.822,\n'
                      '      "bias3_bfq": -3.401,\n'
                      '      "boll_lower_bfq": 3942.391,\n'
                      '      "boll_mid_bfq": 4060.841,\n'
                      '      "boll_upper_bfq": 4179.291,\n'
                      '      "brar_ar_bfq": 120.66878\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=358',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'idx_mins',
  'title': '指数历史分钟',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 190,
  'method': 'GET',
  'path': '/api/v1/market/tushare/idx_mins?ts_code=000001.SH&freq=1min&start_date=2026-07-13+09%3A00%3A00&end_date=2026-07-13+15%3A30%3A00',
  'base_path': '/api/v1/market/tushare/idx_mins',
  'scope': 'tushare:independent:history:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：idx_mins\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=419\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SH',
              'description': '证券/指数/ETF代码'},
             {'name': 'freq',
              'type': 'string',
              'required': '参考官网',
              'example': '1min',
              'description': '数据频率，例如1MIN或1min'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '2026-07-13 09:00:00',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '2026-07-13 15:30:00',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET '
                     '/api/v1/market/tushare/idx_mins?ts_code=000001.SH&freq=1min&start_date=2026-07-13+09%3A00%3A00&end_date=2026-07-13+15%3A30%3A00',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "idx_mins",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=419',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'index_basic',
  'title': '指数基本信息',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 200,
  'method': 'GET',
  'path': '/api/v1/market/tushare/index_basic?market=SSE',
  'base_path': '/api/v1/market/tushare/index_basic',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：index_basic\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=94\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'market', 'type': 'string', 'required': '参考官网', 'example': 'SSE', 'description': '市场代码'}],
  'request_example': 'GET /api/v1/market/tushare/index_basic?market=SSE',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "index_basic",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=94',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'index_classify',
  'title': '申万行业分类',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 210,
  'method': 'GET',
  'path': '/api/v1/market/tushare/index_classify?level=L1&src=SW2021',
  'base_path': '/api/v1/market/tushare/index_classify',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：index_classify\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：31\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=181\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'level', 'type': 'string', 'required': '参考官网', 'example': 'L1', 'description': '行业分类级别'},
             {'name': 'src', 'type': 'string', 'required': '参考官网', 'example': 'SW2021', 'description': '分类标准来源'}],
  'request_example': 'GET /api/v1/market/tushare/index_classify?level=L1&src=SW2021',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "index_classify",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 31,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "index_code": "801010.SI",\n'
                      '      "industry_code": "110000",\n'
                      '      "industry_name": "农林牧渔",\n'
                      '      "is_pub": "1",\n'
                      '      "level": "L1",\n'
                      '      "parent_code": "0",\n'
                      '      "src": "SW2021"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共31条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=181',
  'test_status': '正常可用',
  'test_count': 31,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'index_daily',
  'title': '指数日线行情',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 220,
  'method': 'GET',
  'path': '/api/v1/market/tushare/index_daily?ts_code=000001.SH&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/index_daily',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：index_daily\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=95\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SH',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/index_daily?ts_code=000001.SH&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "index_daily",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 1334871933.909,\n'
                      '      "change": -82.3676,\n'
                      '      "close": 3913.794,\n'
                      '      "high": 3983.0535,\n'
                      '      "low": 3900.6676,\n'
                      '      "open": 3966.0234,\n'
                      '      "pct_chg": -2.0612,\n'
                      '      "pre_close": 3996.1616,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "000001.SH",\n'
                      '      "vol": 590907356.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=95',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'index_dailybasic',
  'title': '大盘指数每日指标',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 230,
  'method': 'GET',
  'path': '/api/v1/market/tushare/index_dailybasic?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/index_dailybasic',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：index_dailybasic\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：12\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=128\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/index_dailybasic?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "index_dailybasic",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 12,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "float_mv": 60045389782728.0,\n'
                      '      "float_share": 4740656511156.0,\n'
                      '      "free_share": 1818505009414.0,\n'
                      '      "pb": 1.47,\n'
                      '      "pe": 16.85,\n'
                      '      "pe_ttm": 16.63,\n'
                      '      "total_mv": 75919956108212.0,\n'
                      '      "total_share": 5853400448035.0,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "000001.SH",\n'
                      '      "turnover_rate": 1.21,\n'
                      '      "turnover_rate_f": 3.16\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共12条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=128',
  'test_status': '正常可用',
  'test_count': 12,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'index_global',
  'title': '国际主要指数',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 240,
  'method': 'GET',
  'path': '/api/v1/market/tushare/index_global?ts_code=IXIC&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/index_global',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：index_global\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：18\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=211\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code', 'type': 'string', 'required': '参考官网', 'example': 'IXIC', 'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/index_global?ts_code=IXIC&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "index_global",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 18,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "change": 74.72,\n'
                      '      "close": 26281.61,\n'
                      '      "high": 26301.54,\n'
                      '      "low": 26009.49,\n'
                      '      "open": 26175.54,\n'
                      '      "pct_chg": 0.2851,\n'
                      '      "pre_close": 26206.89,\n'
                      '      "swing": 1.11,\n'
                      '      "trade_date": "20260710",\n'
                      '      "ts_code": "IXIC",\n'
                      '      "vol": 709448.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共18条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=211',
  'test_status': '正常可用',
  'test_count': 18,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'index_member_all',
  'title': '申万行业成分(分级)',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 250,
  'method': 'GET',
  'path': '/api/v1/market/tushare/index_member_all?ts_code=000001.SZ&is_new=Y',
  'base_path': '/api/v1/market/tushare/index_member_all',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：index_member_all\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=335\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'is_new', 'type': 'string', 'required': '参考官网', 'example': 'Y', 'description': '是否仅查询最新成分'}],
  'request_example': 'GET /api/v1/market/tushare/index_member_all?ts_code=000001.SZ&is_new=Y',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "index_member_all",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "in_date": "19910403",\n'
                      '      "is_new": "Y",\n'
                      '      "l1_code": "801780.SI",\n'
                      '      "l1_name": "银行",\n'
                      '      "l2_code": "801783.SI",\n'
                      '      "l2_name": "股份制银行Ⅱ",\n'
                      '      "l3_code": "857831.SI",\n'
                      '      "l3_name": "股份制银行Ⅲ",\n'
                      '      "name": "平安银行",\n'
                      '      "out_date": null,\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=335',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'index_monthly',
  'title': '指数月线行情',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 260,
  'method': 'GET',
  'path': '/api/v1/market/tushare/index_monthly?ts_code=000001.SH&start_date=20250713&end_date=20260713',
  'base_path': '/api/v1/market/tushare/index_monthly',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：index_monthly\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：12\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=172\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SH',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20250713',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/index_monthly?ts_code=000001.SH&start_date=20250713&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "index_monthly",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260630",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 12,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 30045750116420.0,\n'
                      '      "change": 25.8281,\n'
                      '      "close": 4094.3972,\n'
                      '      "high": 4175.3476,\n'
                      '      "low": 3927.8527,\n'
                      '      "open": 4067.1578,\n'
                      '      "pct_chg": 0.0063,\n'
                      '      "pre_close": 4068.5691,\n'
                      '      "trade_date": "20260630",\n'
                      '      "ts_code": "000001.SH",\n'
                      '      "vol": 1366325221200.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共12条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=172',
  'test_status': '正常可用',
  'test_count': 12,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'index_weekly',
  'title': '指数周线行情',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 270,
  'method': 'GET',
  'path': '/api/v1/market/tushare/index_weekly?ts_code=000001.SH&start_date=20260315&end_date=20260713',
  'base_path': '/api/v1/market/tushare/index_weekly',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：index_weekly\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：17\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=171\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SH',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260315',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/index_weekly?ts_code=000001.SH&start_date=20260315&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "index_weekly",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 17,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 6748124951370.0,\n'
                      '      "change": -47.4816,\n'
                      '      "close": 3996.1616,\n'
                      '      "high": 4074.828,\n'
                      '      "low": 3938.8775,\n'
                      '      "open": 4059.1941,\n'
                      '      "pct_chg": -0.0117,\n'
                      '      "pre_close": 4043.6432,\n'
                      '      "trade_date": "20260710",\n'
                      '      "ts_code": "000001.SH",\n'
                      '      "vol": 278156141300.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共17条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=171',
  'test_status': '正常可用',
  'test_count': 17,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'index_weight',
  'title': '指数成分和权重',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 280,
  'method': 'GET',
  'path': '/api/v1/market/tushare/index_weight?index_code=000300.SH&start_date=20260315&end_date=20260713',
  'base_path': '/api/v1/market/tushare/index_weight',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：index_weight\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1200\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=96\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'index_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000300.SH',
              'description': '指数代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260315',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET '
                     '/api/v1/market/tushare/index_weight?index_code=000300.SH&start_date=20260315&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "index_weight",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260630",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1200,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "con_code": "300308.SZ",\n'
                      '      "index_code": "000300.SH",\n'
                      '      "trade_date": "20260630",\n'
                      '      "weight": 5.008\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1200条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=96',
  'test_status': '正常可用',
  'test_count': 1200,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'rt_idx_k',
  'title': '指数实时日线',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 290,
  'method': 'GET',
  'path': '/api/v1/market/tushare/rt_idx_k?ts_code=000001.SH',
  'base_path': '/api/v1/market/tushare/rt_idx_k',
  'scope': 'tushare:independent:realtime:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：rt_idx_k\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=403\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SH',
              'description': '证券/指数/ETF代码'}],
  'request_example': 'GET /api/v1/market/tushare/rt_idx_k?ts_code=000001.SH',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "rt_idx_k",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 1334871933909.0,\n'
                      '      "close": 3913.794,\n'
                      '      "high": 3983.0535,\n'
                      '      "low": 3900.6676,\n'
                      '      "name": "上证指数",\n'
                      '      "open": 3966.0234,\n'
                      '      "pre_close": 3996.1616,\n'
                      '      "trade_time": "2026-07-13 15:30:36",\n'
                      '      "ts_code": "000001.SH",\n'
                      '      "vol": 590907356.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=403',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'rt_idx_min',
  'title': '指数实时分钟',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 300,
  'method': 'GET',
  'path': '/api/v1/market/tushare/rt_idx_min?ts_code=000001.SH&freq=1MIN',
  'base_path': '/api/v1/market/tushare/rt_idx_min',
  'scope': 'tushare:independent:realtime:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：rt_idx_min\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=420\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SH',
              'description': '证券/指数/ETF代码'},
             {'name': 'freq',
              'type': 'string',
              'required': '参考官网',
              'example': '1MIN',
              'description': '数据频率，例如1MIN或1min'}],
  'request_example': 'GET /api/v1/market/tushare/rt_idx_min?ts_code=000001.SH&freq=1MIN',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "rt_idx_min",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 8812652743.7,\n'
                      '      "close": 3913.794,\n'
                      '      "code": "000001.SH",\n'
                      '      "freq": "1MIN",\n'
                      '      "high": 3913.794,\n'
                      '      "low": 3912.607,\n'
                      '      "open": 3912.607,\n'
                      '      "time": "2026-07-13 15:00:00",\n'
                      '      "volume": 4990000.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=420',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'rt_sw_k',
  'title': '申万实时行情',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 310,
  'method': 'GET',
  'path': '/api/v1/market/tushare/rt_sw_k?ts_code=801010.SI',
  'base_path': '/api/v1/market/tushare/rt_sw_k',
  'scope': 'tushare:independent:realtime:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：rt_sw_k\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=417\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '801010.SI',
              'description': '证券/指数/ETF代码'}],
  'request_example': 'GET /api/v1/market/tushare/rt_sw_k?ts_code=801010.SI',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "rt_sw_k",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 17126455733,\n'
                      '      "close": 2334.641,\n'
                      '      "high": 2353.696,\n'
                      '      "low": 2321.979,\n'
                      '      "name": "农林牧渔                      ",\n'
                      '      "open": 2333.386,\n'
                      '      "pct_change": -0.58,\n'
                      '      "pre_close": 2348.25,\n'
                      '      "trade_time": "2026-07-13 15:07:00",\n'
                      '      "ts_code": "801010.SI",\n'
                      '      "vol": 1963520655\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=417',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'sw_daily',
  'title': '申万日线行情',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 320,
  'method': 'GET',
  'path': '/api/v1/market/tushare/sw_daily?ts_code=801010.SI&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/sw_daily',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：sw_daily\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=327\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '801010.SI',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/sw_daily?ts_code=801010.SI&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "sw_daily",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 1712646.0,\n'
                      '      "change": -13.61,\n'
                      '      "close": 2334.64,\n'
                      '      "float_mv": 53115013.0,\n'
                      '      "high": 2352.51,\n'
                      '      "low": 2325.4,\n'
                      '      "name": "农林牧渔",\n'
                      '      "open": 2333.39,\n'
                      '      "pb": 2.1,\n'
                      '      "pct_change": -0.58,\n'
                      '      "pe": 38.17,\n'
                      '      "total_mv": 112976805.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=327',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'sw_mins',
  'title': 'SW历史分钟',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 330,
  'method': 'GET',
  'path': '/api/v1/market/tushare/sw_mins?ts_code=801010.SI&freq=1min&start_date=2026-07-13+09%3A00%3A00&end_date=2026-07-13+15%3A30%3A00',
  'base_path': '/api/v1/market/tushare/sw_mins',
  'scope': 'tushare:independent:history:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：sw_mins\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：中转路由未配置；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=469\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '801010.SI',
              'description': '证券/指数/ETF代码'},
             {'name': 'freq',
              'type': 'string',
              'required': '参考官网',
              'example': '1min',
              'description': '数据频率，例如1MIN或1min'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '2026-07-13 09:00:00',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '2026-07-13 15:30:00',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET '
                     '/api/v1/market/tushare/sw_mins?ts_code=801010.SI&freq=1min&start_date=2026-07-13+09%3A00%3A00&end_date=2026-07-13+15%3A30%3A00',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "sw_mins",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=469',
  'test_status': '中转路由未配置',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'sz_daily_info',
  'title': '深圳市场每日交易情况',
  'category': '指数专题',
  'category_description': '交易所指数、申万/中信行业指数、全球指数及指数因子接口。',
  'category_sort_order': 30,
  'sort_order': 340,
  'method': 'GET',
  'path': '/api/v1/market/tushare/sz_daily_info?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/sz_daily_info',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：sz_daily_info\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：14\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=268\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/sz_daily_info?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "sz_daily_info",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 14,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 1099359884.86,\n'
                      '      "count": 817,\n'
                      '      "float_mv": 531745725436.21,\n'
                      '      "float_share": null,\n'
                      '      "total_mv": 531745725436.21,\n'
                      '      "total_share": null,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "ABS",\n'
                      '      "vol": null\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共14条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=268',
  'test_status': '正常可用',
  'test_count': 14,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'margin',
  'title': '融资融券交易汇总',
  'category': '两融及转融通',
  'category_description': '融资融券、转融券及做市借券数据接口。',
  'category_sort_order': 90,
  'sort_order': 350,
  'method': 'GET',
  'path': '/api/v1/market/tushare/margin?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/margin',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：margin\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：3\n'
                 '数据新鲜度：请求20260713，实际返回20260710最近可用数据。\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=58\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/margin?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "margin",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": "20260713",\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": true,\n'
                      '    "data_freshness": "latest_available",\n'
                      '    "fallback_attempt_count": 2\n'
                      '  },\n'
                      '  "count": 3,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "exchange_id": "BSE",\n'
                      '      "rqmcl": 1458.0,\n'
                      '      "rqye": 76987.0,\n'
                      '      "rqyl": 3440.0,\n'
                      '      "rzche": 893379428.0,\n'
                      '      "rzmre": 863088662.0,\n'
                      '      "rzrqye": 9035038250.0,\n'
                      '      "rzye": 9034961263.0,\n'
                      '      "trade_date": "20260710"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共3条；请求日期20260713尚未发布，已返回最近可用日期20260710的数据"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=58',
  'test_status': '正常可用',
  'test_count': 3,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'margin_detail',
  'title': '融资融券交易明细',
  'category': '两融及转融通',
  'category_description': '融资融券、转融券及做市借券数据接口。',
  'category_sort_order': 90,
  'sort_order': 360,
  'method': 'GET',
  'path': '/api/v1/market/tushare/margin_detail?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/margin_detail',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：margin_detail\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：4377\n'
                 '数据新鲜度：请求20260713，实际返回20260710最近可用数据。\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=59\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/margin_detail?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "margin_detail",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": "20260713",\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": true,\n'
                      '    "data_freshness": "latest_available",\n'
                      '    "fallback_attempt_count": 2\n'
                      '  },\n'
                      '  "count": 4377,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "rqchl": 62000.0,\n'
                      '      "rqmcl": 41800.0,\n'
                      '      "rqye": 17650050.0,\n'
                      '      "rqyl": 1689000.0,\n'
                      '      "rzche": 126796258.0,\n'
                      '      "rzmre": 139251927.0,\n'
                      '      "rzrqye": 5172680936.0,\n'
                      '      "rzye": 5155030886.0,\n'
                      '      "trade_date": "20260710",\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共4377条；请求日期20260713尚未发布，已返回最近可用日期20260710的数据"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=59',
  'test_status': '正常可用',
  'test_count': 4377,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'margin_secs',
  'title': '融资融券标的(盘前)',
  'category': '两融及转融通',
  'category_description': '融资融券、转融券及做市借券数据接口。',
  'category_sort_order': 90,
  'sort_order': 370,
  'method': 'GET',
  'path': '/api/v1/market/tushare/margin_secs?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/margin_secs',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：margin_secs\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：4089\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=326\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/margin_secs?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "margin_secs",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 4089,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "exchange": "SSE",\n'
                      '      "name": "50ETF ",\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "510050.SH"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共4089条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=326',
  'test_status': '正常可用',
  'test_count': 4089,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'slb_len',
  'title': '转融资交易汇总',
  'category': '两融及转融通',
  'category_description': '融资融券、转融券及做市借券数据接口。',
  'category_sort_order': 90,
  'sort_order': 380,
  'method': 'GET',
  'path': '/api/v1/market/tushare/slb_len?trade_date=20230901',
  'base_path': '/api/v1/market/tushare/slb_len',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：slb_len\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=331\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20230901',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/slb_len?trade_date=20230901',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "slb_len",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20230901",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "auc_amount": null,\n'
                      '      "cb": 1309.41,\n'
                      '      "ob": 1309.41,\n'
                      '      "repay_amount": null,\n'
                      '      "repo_amount": null,\n'
                      '      "trade_date": "20230901"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=331',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'slb_len_mm',
  'title': '做市借券交易汇总(停)',
  'category': '两融及转融通',
  'category_description': '融资融券、转融券及做市借券数据接口。',
  'category_sort_order': 90,
  'sort_order': 390,
  'method': 'GET',
  'path': '/api/v1/market/tushare/slb_len_mm?trade_date=20230901',
  'base_path': '/api/v1/market/tushare/slb_len_mm',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：slb_len_mm\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：123\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=334\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20230901',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/slb_len_mm?trade_date=20230901',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "slb_len_mm",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20230901",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 123,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "cls_inv": 12.57,\n'
                      '      "end_bal": 633.15,\n'
                      '      "lent_qnt": null,\n'
                      '      "name": "睿创微纳",\n'
                      '      "ope_inv": 12.57,\n'
                      '      "trade_date": "20230901",\n'
                      '      "ts_code": "688002.SH"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共123条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=334',
  'test_status': '正常可用',
  'test_count': 123,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'slb_sec',
  'title': '转融券交易汇总(停)',
  'category': '两融及转融通',
  'category_description': '融资融券、转融券及做市借券数据接口。',
  'category_sort_order': 90,
  'sort_order': 400,
  'method': 'GET',
  'path': '/api/v1/market/tushare/slb_sec?trade_date=20230901',
  'base_path': '/api/v1/market/tushare/slb_sec',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：slb_sec\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：2536\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=332\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20230901',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/slb_sec?trade_date=20230901',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "slb_sec",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20230901",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 2536,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "cls_inv": 177.32,\n'
                      '      "end_bal": 2007.26,\n'
                      '      "lent_qnt": 5.59,\n'
                      '      "name": "平安银行",\n'
                      '      "ope_inv": 171.73,\n'
                      '      "trade_date": "20230901",\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共2536条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=332',
  'test_status': '正常可用',
  'test_count': 2536,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'slb_sec_detail',
  'title': '转融券交易明细(停)',
  'category': '两融及转融通',
  'category_description': '融资融券、转融券及做市借券数据接口。',
  'category_sort_order': 90,
  'sort_order': 410,
  'method': 'GET',
  'path': '/api/v1/market/tushare/slb_sec_detail?trade_date=20230901',
  'base_path': '/api/v1/market/tushare/slb_sec_detail',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：slb_sec_detail\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1283\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=333\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20230901',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/slb_sec_detail?trade_date=20230901',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "slb_sec_detail",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20230901",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1283,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "fee_rate": 2.6,\n'
                      '      "lent_qnt": 3.19,\n'
                      '      "name": "平安银行",\n'
                      '      "tenor": "14",\n'
                      '      "trade_date": "20230901",\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1283条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=333',
  'test_status': '正常可用',
  'test_count': 1283,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'block_trade',
  'title': '大宗交易',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 420,
  'method': 'GET',
  'path': '/api/v1/market/tushare/block_trade?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/block_trade',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：block_trade\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：86\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=161\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/block_trade?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "block_trade",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 86,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 1012.69,\n'
                      '      "buyer": "机构专用",\n'
                      '      "price": 52.12,\n'
                      '      "seller": "华泰证券股份有限公司福建分公司",\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "000021.SZ",\n'
                      '      "vol": 19.43\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共86条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=161',
  'test_status': '正常可用',
  'test_count': 86,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'pledge_detail',
  'title': '股权质押明细数据',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 430,
  'method': 'GET',
  'path': '/api/v1/market/tushare/pledge_detail?ts_code=000014.SZ',
  'base_path': '/api/v1/market/tushare/pledge_detail',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：pledge_detail\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：14\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=111\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000014.SZ',
              'description': '证券/指数/ETF代码'}],
  'request_example': 'GET /api/v1/market/tushare/pledge_detail?ts_code=000014.SZ',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "pledge_detail",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 14,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ann_date": "20180106",\n'
                      '      "end_date": "20181114",\n'
                      '      "h_total_ratio": 6.51,\n'
                      '      "holder_name": "中科汇通(深圳)股权投资基金有限公司",\n'
                      '      "holding_amount": 1313.4855,\n'
                      '      "is_buyback": "0",\n'
                      '      "is_release": "1",\n'
                      '      "p_total_ratio": 2.07,\n'
                      '      "pledge_amount": 500.0,\n'
                      '      "pledged_amount": 922.0055,\n'
                      '      "pledgor": "海通证券股份有限公司",\n'
                      '      "release_date": "20180104"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共14条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=111',
  'test_status': '正常可用',
  'test_count': 14,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'pledge_stat',
  'title': '股权质押统计数据',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 440,
  'method': 'GET',
  'path': '/api/v1/market/tushare/pledge_stat?ts_code=000001.SZ',
  'base_path': '/api/v1/market/tushare/pledge_stat',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：pledge_stat\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：635\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=110\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'}],
  'request_example': 'GET /api/v1/market/tushare/pledge_stat?ts_code=000001.SZ',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "pledge_stat",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 635,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "end_date": "20260710",\n'
                      '      "pledge_count": 10,\n'
                      '      "pledge_ratio": 0.13,\n'
                      '      "rest_pledge": 0.0,\n'
                      '      "total_share": 1940591.82,\n'
                      '      "ts_code": "000001.SZ",\n'
                      '      "unrest_pledge": 2520.29\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共635条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=110',
  'test_status': '正常可用',
  'test_count': 635,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'repurchase',
  'title': '股票回购',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 450,
  'method': 'GET',
  'path': '/api/v1/market/tushare/repurchase?start_date=20250713&end_date=20260713',
  'base_path': '/api/v1/market/tushare/repurchase',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：repurchase\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：2000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=124\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20250713',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/repurchase?start_date=20250713&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "repurchase",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 2000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 4549500.0,\n'
                      '      "ann_date": "20260713",\n'
                      '      "end_date": "20260715",\n'
                      '      "exp_date": null,\n'
                      '      "high_limit": 9.0,\n'
                      '      "low_limit": 9.0,\n'
                      '      "proc": "完成",\n'
                      '      "ts_code": "688296.SH",\n'
                      '      "vol": 505500.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共2000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=124',
  'test_status': '正常可用',
  'test_count': 2000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'share_float',
  'title': '限售股解禁',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 460,
  'method': 'GET',
  'path': '/api/v1/market/tushare/share_float?start_date=20250713&end_date=20260713',
  'base_path': '/api/v1/market/tushare/share_float',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：share_float\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：6000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=160\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20250713',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/share_float?start_date=20250713&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "share_float",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 6000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ann_date": "20260709",\n'
                      '      "float_date": "20260713",\n'
                      '      "float_ratio": 2.74,\n'
                      '      "float_share": 4230552.0,\n'
                      '      "holder_name": "唐联生",\n'
                      '      "share_type": "首发原始股",\n'
                      '      "ts_code": "920781.BJ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共6000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=160',
  'test_status': '正常可用',
  'test_count': 6000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_account',
  'title': '股票开户数据(停)',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 470,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_account?start_date=20150101&end_date=20171231',
  'base_path': '/api/v1/market/tushare/stk_account',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_account\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：135\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=164\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20150101',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20171231',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/stk_account?start_date=20150101&end_date=20171231',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_account",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 135,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "date": "20171229",\n'
                      '      "total": 13398.3,\n'
                      '      "weekly_hold": null,\n'
                      '      "weekly_new": 22.42,\n'
                      '      "weekly_trade": null\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共135条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=164',
  'test_status': '正常可用',
  'test_count': 135,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_account_old',
  'title': '股票开户数据(旧)',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 480,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_account_old?start_date=20140101&end_date=20141231',
  'base_path': '/api/v1/market/tushare/stk_account_old',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_account_old\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：中转明确不支持；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=165\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20140101',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20141231',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/stk_account_old?start_date=20140101&end_date=20141231',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_account_old",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=165',
  'test_status': '中转明确不支持',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'stk_alert',
  'title': '交易所重点提示证券',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 490,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_alert?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/stk_alert',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_alert\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：2\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=453\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/stk_alert?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_alert",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 2,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "end_date": "20260724",\n'
                      '      "name": "三江转债",\n'
                      '      "start_date": "20260713",\n'
                      '      "ts_code": "123273.SZ",\n'
                      '      "type": "交易所重点提示证券"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共2条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=453',
  'test_status': '正常可用',
  'test_count': 2,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_high_shock',
  'title': '个股严重异常波动',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 500,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_high_shock?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/stk_high_shock',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_high_shock\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：2\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=452\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/stk_high_shock?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_high_shock",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 2,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "name": "万邦医药",\n'
                      '      "period": "2026071320260727",\n'
                      '      "reason": "连续10个交易日内收盘价格涨幅偏离值累计达100%",\n'
                      '      "trade_date": "20260713",\n'
                      '      "trade_market": "深交所",\n'
                      '      "ts_code": "301520.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共2条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=452',
  'test_status': '正常可用',
  'test_count': 2,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_holdernumber',
  'title': '股东人数',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 510,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_holdernumber?ts_code=000001.SZ',
  'base_path': '/api/v1/market/tushare/stk_holdernumber',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_holdernumber\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：149\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=166\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'}],
  'request_example': 'GET /api/v1/market/tushare/stk_holdernumber?ts_code=000001.SZ',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_holdernumber",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 149,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ann_date": "20260527",\n'
                      '      "end_date": "20260527",\n'
                      '      "holder_num": null,\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共149条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=166',
  'test_status': '正常可用',
  'test_count': 149,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_holdertrade',
  'title': '股东增减持',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 520,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_holdertrade?start_date=20250713&end_date=20260713',
  'base_path': '/api/v1/market/tushare/stk_holdertrade',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_holdertrade\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：3000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=175\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20250713',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/stk_holdertrade?start_date=20250713&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_holdertrade",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 3000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "after_ratio": 1.6326,\n'
                      '      "after_share": 2933300.0,\n'
                      '      "ann_date": "20260713",\n'
                      '      "avg_price": 22.71,\n'
                      '      "change_ratio": 1.0389,\n'
                      '      "change_vol": 1866700.0,\n'
                      '      "holder_name": "王绪平",\n'
                      '      "holder_type": "P",\n'
                      '      "in_de": "DE",\n'
                      '      "total_share": 2933300.0,\n'
                      '      "ts_code": "301199.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共3000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=175',
  'test_status': '正常可用',
  'test_count': 3000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_shock',
  'title': '个股异常波动',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 530,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_shock?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/stk_shock',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_shock\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：26\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=451\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/stk_shock?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_shock",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 26,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "name": "庄园牧场",\n'
                      '      "period": "2026-07-09-2026-07-13",\n'
                      '      "reason": "连续三个交易日内涨跌幅偏离值累计达20%",\n'
                      '      "trade_date": "20260713",\n'
                      '      "trade_market": "深交所",\n'
                      '      "ts_code": "002910.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共26条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=451',
  'test_status': '正常可用',
  'test_count': 26,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'top10_floatholders',
  'title': '前十大流通股东',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 540,
  'method': 'GET',
  'path': '/api/v1/market/tushare/top10_floatholders?ts_code=000001.SZ&period=20251231',
  'base_path': '/api/v1/market/tushare/top10_floatholders',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：top10_floatholders\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：10\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=62\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'period',
              'type': 'string',
              'required': '参考官网',
              'example': '20251231',
              'description': '报告期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/top10_floatholders?ts_code=000001.SZ&period=20251231',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "top10_floatholders",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 10,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ann_date": "20260321",\n'
                      '      "end_date": "20251231",\n'
                      '      "hold_amount": 9618540236.0,\n'
                      '      "hold_change": 0.0,\n'
                      '      "hold_float_ratio": 49.5658,\n'
                      '      "hold_ratio": 49.565,\n'
                      '      "holder_name": "中国平安保险(集团)股份有限公司-集团本级-自有资金",\n'
                      '      "holder_type": "一般企业",\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共10条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=62',
  'test_status': '正常可用',
  'test_count': 10,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'top10_holders',
  'title': '前十大股东',
  'category': '股票参考数据',
  'category_description': '股东、质押、回购、解禁、开户、异常波动等参考数据接口。',
  'category_sort_order': 70,
  'sort_order': 550,
  'method': 'GET',
  'path': '/api/v1/market/tushare/top10_holders?ts_code=000001.SZ&period=20251231',
  'base_path': '/api/v1/market/tushare/top10_holders',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：top10_holders\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：10\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=61\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'period',
              'type': 'string',
              'required': '参考官网',
              'example': '20251231',
              'description': '报告期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/top10_holders?ts_code=000001.SZ&period=20251231',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "top10_holders",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 10,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ann_date": "20260321",\n'
                      '      "end_date": "20251231",\n'
                      '      "hold_amount": 9618540236.0,\n'
                      '      "hold_change": 0.0,\n'
                      '      "hold_float_ratio": 49.5658,\n'
                      '      "hold_ratio": 49.565,\n'
                      '      "holder_name": "中国平安保险(集团)股份有限公司-集团本级-自有资金",\n'
                      '      "holder_type": "一般企业",\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共10条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=61',
  'test_status': '正常可用',
  'test_count': 10,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'bak_basic',
  'title': '股票历史列表',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 560,
  'method': 'GET',
  'path': '/api/v1/market/tushare/bak_basic?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/bak_basic',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：bak_basic\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：5532\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=262\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/bak_basic?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "bak_basic",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 5532,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "area": "深圳",\n'
                      '      "bvps": 23.91,\n'
                      '      "eps": 0.67,\n'
                      '      "fixed_assets": 108.79,\n'
                      '      "float_share": 194.06,\n'
                      '      "gpr": 49.29,\n'
                      '      "holder_num": 457610,\n'
                      '      "industry": "银行",\n'
                      '      "liquid_assets": 0.0,\n'
                      '      "list_date": "19910403",\n'
                      '      "name": "平安银行",\n'
                      '      "npr": 41.17\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共5532条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=262',
  'test_status': '正常可用',
  'test_count': 5532,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'bse_mapping',
  'title': '北交所新旧代码对照',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 570,
  'method': 'GET',
  'path': '/api/v1/market/tushare/bse_mapping',
  'base_path': '/api/v1/market/tushare/bse_mapping',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：bse_mapping\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：248\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=375\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [],
  'request_example': 'GET /api/v1/market/tushare/bse_mapping',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "bse_mapping",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 248,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "list_date": "20200727",\n'
                      '      "n_code": "920729.BJ",\n'
                      '      "name": "永顺生物",\n'
                      '      "o_code": "839729.BJ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共248条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=375',
  'test_status': '正常可用',
  'test_count': 248,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'namechange',
  'title': '股票曾用名',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 580,
  'method': 'GET',
  'path': '/api/v1/market/tushare/namechange?ts_code=000001.SZ&start_date=20250713&end_date=20260713',
  'base_path': '/api/v1/market/tushare/namechange',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：namechange\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=100\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20250713',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/namechange?ts_code=000001.SZ&start_date=20250713&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "namechange",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=100',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'new_share',
  'title': 'IPO新股上市',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 590,
  'method': 'GET',
  'path': '/api/v1/market/tushare/new_share?start_date=20260315&end_date=20260713',
  'base_path': '/api/v1/market/tushare/new_share',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：new_share\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：58\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=123\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260315',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/new_share?start_date=20260315&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "new_share",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 58,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 883.0,\n'
                      '      "ballot": 0.0,\n'
                      '      "funds": 1.957,\n'
                      '      "ipo_date": "20260713",\n'
                      '      "issue_date": null,\n'
                      '      "limit_amount": 39.73,\n'
                      '      "market_amount": 795.0,\n'
                      '      "name": "维琪科技",\n'
                      '      "pe": 14.99,\n'
                      '      "price": 22.16,\n'
                      '      "sub_code": "920176",\n'
                      '      "ts_code": "920176.BJ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共58条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=123',
  'test_status': '正常可用',
  'test_count': 58,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'st',
  'title': 'ST风险警示板股票',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 600,
  'method': 'GET',
  'path': '/api/v1/market/tushare/st',
  'base_path': '/api/v1/market/tushare/st',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：st\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=423\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [],
  'request_example': 'GET /api/v1/market/tushare/st',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "st",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "imp_date": "20260714",\n'
                      '      "name": "德豪润达",\n'
                      '      "pub_date": "20260711",\n'
                      '      "st_explain": '
                      '"2025年度,公司实现营业收入663,452,972.75元、归属于上市公司股东的净利润34,096,711.99元、归属于上市公司股东的扣除非经常性损益的净利润-117,793,101.82元。同时,华兴会计师事务所(特殊普通合伙)为公司出具了《关于安徽德豪润达电气股份有限公司2024年度财务报表审计报告非标准...",\n'
                      '      "st_reason": "中国证监会或交易所认定的其他应进行特别处理的情形已消除",\n'
                      '      "st_type": "撤销ST",\n'
                      '      "ts_code": "002005.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=423',
  'test_status': '正常可用',
  'test_count': 1000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_managers',
  'title': '上市公司管理层',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 610,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_managers?ts_code=000001.SZ',
  'base_path': '/api/v1/market/tushare/stk_managers',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_managers\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：193\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=193\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'}],
  'request_example': 'GET /api/v1/market/tushare/stk_managers?ts_code=000001.SZ',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_managers",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 193,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ann_date": "20251217",\n'
                      '      "begin_date": "20231226",\n'
                      '      "birthday": "1964",\n'
                      '      "edu": "博士",\n'
                      '      "end_date": null,\n'
                      '      "gender": "M",\n'
                      '      "lev": "委员会成员",\n'
                      '      "name": "项有志",\n'
                      '      "national": "中国",\n'
                      '      "title": "风险管理委员会委员",\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共193条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=193',
  'test_status': '正常可用',
  'test_count': 193,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_premarket',
  'title': '每日股本(盘前)',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 620,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_premarket?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/stk_premarket',
  'scope': 'tushare:independent:special:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：stk_premarket\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=329\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/stk_premarket?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_premarket",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=329',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'stk_rewards',
  'title': '管理层薪酬和持股',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 630,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_rewards?ts_code=000001.SZ',
  'base_path': '/api/v1/market/tushare/stk_rewards',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_rewards\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：2736\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=194\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'}],
  'request_example': 'GET /api/v1/market/tushare/stk_rewards?ts_code=000001.SZ',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_rewards",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 2736,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ann_date": "20260321",\n'
                      '      "end_date": "20251231",\n'
                      '      "hold_vol": 50000.0,\n'
                      '      "name": "杨志群",\n'
                      '      "reward": 2766300.0,\n'
                      '      "title": "董事,副行长",\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共2736条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=194',
  'test_status': '正常可用',
  'test_count': 2736,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stock_basic',
  'title': '股票列表',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 640,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stock_basic?list_status=L&fields=ts_code%2Csymbol%2Cname%2Cmarket%2Clist_status%2Clist_date',
  'base_path': '/api/v1/market/tushare/stock_basic',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stock_basic\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：5530\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=25\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'list_status',
              'type': 'string',
              'required': '参考官网',
              'example': 'L',
              'description': '上市状态，例如L为上市'},
             {'name': 'fields',
              'type': 'string',
              'required': '参考官网',
              'example': 'ts_code,symbol,name,market,list_status,list_date',
              'description': '返回字段列表，多个字段使用英文逗号分隔'}],
  'request_example': 'GET '
                     '/api/v1/market/tushare/stock_basic?list_status=L&fields=ts_code%2Csymbol%2Cname%2Cmarket%2Clist_status%2Clist_date',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stock_basic",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 5530,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "list_date": "19910403",\n'
                      '      "list_status": "L",\n'
                      '      "market": "主板",\n'
                      '      "name": "平安银行",\n'
                      '      "symbol": "000001",\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共5530条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=25',
  'test_status': '正常可用',
  'test_count': 5530,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stock_company',
  'title': '上市公司基本信息',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 650,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stock_company?exchange=SZSE&fields=ts_code%2Cchairman%2Cmanager%2Cprovince%2Ccity%2Cemployees%2Cmain_business',
  'base_path': '/api/v1/market/tushare/stock_company',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stock_company\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：3083\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=112\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'exchange', 'type': 'string', 'required': '参考官网', 'example': 'SZSE', 'description': '交易所或市场代码'},
             {'name': 'fields',
              'type': 'string',
              'required': '参考官网',
              'example': 'ts_code,chairman,manager,province,city,employees,main_business',
              'description': '返回字段列表，多个字段使用英文逗号分隔'}],
  'request_example': 'GET '
                     '/api/v1/market/tushare/stock_company?exchange=SZSE&fields=ts_code%2Cchairman%2Cmanager%2Cprovince%2Ccity%2Cemployees%2Cmain_business',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stock_company",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 3083,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "chairman": "路金波",\n'
                      '      "city": "杭州市",\n'
                      '      "employees": 311.0,\n'
                      '      "main_business": "图书策划与发行、数字内容业务、IP 衍生与运营。",\n'
                      '      "manager": "瞿洪斌",\n'
                      '      "province": "浙江",\n'
                      '      "ts_code": "301052.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共3083条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=112',
  'test_status': '正常可用',
  'test_count': 3083,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stock_hsgt',
  'title': '沪深港通股票列表',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 660,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stock_hsgt',
  'base_path': '/api/v1/market/tushare/stock_hsgt',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stock_hsgt\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：2000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=398\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [],
  'request_example': 'GET /api/v1/market/tushare/stock_hsgt',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stock_hsgt",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 2000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "name": "电讯盈科",\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "00008.HK",\n'
                      '      "type": "SH_HK",\n'
                      '      "type_name": "港股通(沪>港)"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共2000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=398',
  'test_status': '正常可用',
  'test_count': 2000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stock_st',
  'title': 'ST股票列表',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 670,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stock_st?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/stock_st',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stock_st\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：211\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=397\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/stock_st?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stock_st",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 211,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "name": "*ST威领",\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "002667.SZ",\n'
                      '      "type": "ST",\n'
                      '      "type_name": "风险警示板"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共211条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=397',
  'test_status': '正常可用',
  'test_count': 211,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'trade_cal',
  'title': '交易日历',
  'category': '股票基础数据',
  'category_description': '股票列表、交易日历、公司信息、管理层及基础资料接口。',
  'category_sort_order': 40,
  'sort_order': 680,
  'method': 'GET',
  'path': '/api/v1/market/tushare/trade_cal?exchange=SSE&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/trade_cal',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：trade_cal\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：31\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=26\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'exchange', 'type': 'string', 'required': '参考官网', 'example': 'SSE', 'description': '交易所或市场代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/trade_cal?exchange=SSE&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "trade_cal",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 31,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "cal_date": "20260713",\n'
                      '      "exchange": "SSE",\n'
                      '      "is_open": 1,\n'
                      '      "pretrade_date": "20260710"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共31条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=26',
  'test_status': '正常可用',
  'test_count': 31,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'dc_concept',
  'title': '题材数据(DC)',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 690,
  'method': 'GET',
  'path': '/api/v1/market/tushare/dc_concept?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/dc_concept',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：dc_concept\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：621\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=421\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/dc_concept?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "dc_concept",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 621,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "hot": "662",\n'
                      '      "lead_stock": "华建集团",\n'
                      '      "lead_stock_code": "600629.SH",\n'
                      '      "lead_stock_pct_change": "10.04",\n'
                      '      "main_change": "-3768133809.05",\n'
                      '      "name": "雄安新区",\n'
                      '      "pct_change": "-3.63",\n'
                      '      "sort": "296",\n'
                      '      "strength": "1563",\n'
                      '      "theme_code": "000008.DC",\n'
                      '      "trade_date": "20260713",\n'
                      '      "z_t_num": "1"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共621条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=421',
  'test_status': '正常可用',
  'test_count': 621,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'dc_concept_cons',
  'title': '题材成分(DC)',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 700,
  'method': 'GET',
  'path': '/api/v1/market/tushare/dc_concept_cons?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/dc_concept_cons',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：dc_concept_cons\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：3000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=422\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/dc_concept_cons?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "dc_concept_cons",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 3000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "hot_num": "4191",\n'
                      '      "industry": "水泥",\n'
                      '      "industry_code": "BK0424",\n'
                      '      "name": "金隅冀东",\n'
                      '      "reason": '
                      '"公司是国家重点支持水泥结构调整的12家大型水泥企业集团之一、中国北方最大的水泥生产厂商,通过实施“巩固华北、挺进东北、开拓西北”的“三北”发展战略,年设计熟料产能达到7483万吨,设计水泥产能达到1.30亿吨,余热发电总装机容量达357兆瓦,市场覆盖河北、北京、天津、陕西、山西、内蒙古、吉林、重庆等12个省(直辖...",\n'
                      '      "theme_code": "000008.DC",\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "000401.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共3000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=422',
  'test_status': '正常可用',
  'test_count': 3000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'dc_daily',
  'title': 'DC概念板块行情',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 710,
  'method': 'GET',
  'path': '/api/v1/market/tushare/dc_daily?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/dc_daily',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：dc_daily\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1022\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=382\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/dc_daily?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "dc_daily",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1022,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 246776759116.0,\n'
                      '      "category": "地域板块",\n'
                      '      "change": -817.03,\n'
                      '      "close": 21276.94,\n'
                      '      "high": 22032.96,\n'
                      '      "low": 21208.45,\n'
                      '      "open": 21953.62,\n'
                      '      "pct_change": -3.7,\n'
                      '      "swing": 3.73,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "BK0145.DC",\n'
                      '      "turnover_rate": 1.65\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1022条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=382',
  'test_status': '正常可用',
  'test_count': 1022,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'dc_hot',
  'title': 'DC热榜',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 720,
  'method': 'GET',
  'path': '/api/v1/market/tushare/dc_hot?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/dc_hot',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：dc_hot\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：788\n'
                 '数据新鲜度：请求20260713，实际返回20260710最近可用数据。\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=321\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/dc_hot?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "dc_hot",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": "20260713",\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": true,\n'
                      '    "data_freshness": "latest_available",\n'
                      '    "fallback_attempt_count": 2\n'
                      '  },\n'
                      '  "count": 788,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "concept": null,\n'
                      '      "current_price": 0.148,\n'
                      '      "data_type": "港股市场",\n'
                      '      "hot": null,\n'
                      '      "pct_change": 28.7,\n'
                      '      "rank": 1,\n'
                      '      "rank_time": "2026-07-10 22:30:00",\n'
                      '      "trade_date": "20260710",\n'
                      '      "ts_code": "08201.HK",\n'
                      '      "ts_name": "宝联控股"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共788条；请求日期20260713尚未发布，已返回最近可用日期20260710的数据"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=321',
  'test_status': '正常可用',
  'test_count': 788,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'dc_index',
  'title': 'DC概念板块分类',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 730,
  'method': 'GET',
  'path': '/api/v1/market/tushare/dc_index',
  'base_path': '/api/v1/market/tushare/dc_index',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：dc_index\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：5000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=362\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [],
  'request_example': 'GET /api/v1/market/tushare/dc_index',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "dc_index",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 5000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "down_num": 19,\n'
                      '      "idx_type": "概念板块",\n'
                      '      "leading": "梅花生物",\n'
                      '      "leading_code": "600873.SH",\n'
                      '      "leading_pct": 2.98,\n'
                      '      "level": null,\n'
                      '      "name": "2026中报预减",\n'
                      '      "pct_change": -2.8,\n'
                      '      "total_mv": 28267622.4,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "BK1752.DC",\n'
                      '      "turnover_rate": 1.87\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共5000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=362',
  'test_status': '正常可用',
  'test_count': 5000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'dc_member',
  'title': 'DC概念板块成分',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 740,
  'method': 'GET',
  'path': '/api/v1/market/tushare/dc_member',
  'base_path': '/api/v1/market/tushare/dc_member',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：dc_member\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：8000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=363\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [],
  'request_example': 'GET /api/v1/market/tushare/dc_member',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "dc_member",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 8000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "con_code": "601021.SH",\n'
                      '      "name": "春秋航空",\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "BK0145.DC"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共8000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=363',
  'test_status': '正常可用',
  'test_count': 8000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'hm_detail',
  'title': '游资交易每日明细',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 750,
  'method': 'GET',
  'path': '/api/v1/market/tushare/hm_detail?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/hm_detail',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：hm_detail\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：267\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=312\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/hm_detail?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "hm_detail",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 267,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "buy_amount": 15871528.0,\n'
                      '      "hm_name": "鑫多多",\n'
                      '      "hm_orgs": "广发证券股份有限公司南京汉中路证券营业部",\n'
                      '      "net_amount": 15866718.0,\n'
                      '      "sell_amount": 4810.0,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "301588.SZ",\n'
                      '      "ts_name": "美新科技"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共267条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=312',
  'test_status': '正常可用',
  'test_count': 267,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'hm_list',
  'title': '市场游资最全名录',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 760,
  'method': 'GET',
  'path': '/api/v1/market/tushare/hm_list',
  'base_path': '/api/v1/market/tushare/hm_list',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：hm_list\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：110\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=311\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [],
  'request_example': 'GET /api/v1/market/tushare/hm_list',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "hm_list",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 110,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "desc": "龙飞虎(克拉美书)股灾期间曾为桃县精神领袖，留有颇多名言，可见人品股品。",\n'
                      '      "name": "龙飞虎",\n'
                      '      "orgs": "[\\"华泰证券股份有限公司南京六合雄州西路证券营业部\\"]"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共110条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=311',
  'test_status': '正常可用',
  'test_count': 110,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'kpl_concept_cons',
  'title': '题材成分(KP)',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 770,
  'method': 'GET',
  'path': '/api/v1/market/tushare/kpl_concept_cons?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/kpl_concept_cons',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：kpl_concept_cons\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：470\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=351\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/kpl_concept_cons?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "kpl_concept_cons",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 470,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "con_code": "600246.SH",\n'
                      '      "con_name": "万通发展",\n'
                      '      "desc": '
                      '"参股公司数渡科技现有产品具备专属片间组网功能，可直接实现GPU与GPU之间高效直连通信、并行协同工作，能够支撑大规模算力资源池化搭建与高可用集群部署，是国内构建自主可控超节点架构的稀缺核心芯片方案",\n'
                      '      "hot_num": 5915,\n'
                      '      "name": "超节点概念",\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "000396.KP"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共470条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=351',
  'test_status': '正常可用',
  'test_count': 470,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'kpl_list',
  'title': '榜单数据(KP)',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 780,
  'method': 'GET',
  'path': '/api/v1/market/tushare/kpl_list?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/kpl_list',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：kpl_list\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：90\n'
                 '数据新鲜度：请求20260713，实际返回20260710最近可用数据。\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=347\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/kpl_list?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "kpl_list",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": "20260713",\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": true,\n'
                      '    "data_freshness": "latest_available",\n'
                      '    "fallback_attempt_count": 2\n'
                      '  },\n'
                      '  "count": 90,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 376969926.0,\n'
                      '      "bid_amount": null,\n'
                      '      "bid_change": null,\n'
                      '      "bid_pct_chg": null,\n'
                      '      "bid_turnover": null,\n'
                      '      "free_float": 8221434148.0,\n'
                      '      "last_time": "14:56:40",\n'
                      '      "ld_time": null,\n'
                      '      "limit_order": 37812584.0,\n'
                      '      "lu_bid_vol": null,\n'
                      '      "lu_desc": "商业航天",\n'
                      '      "lu_limit_order": 37812584.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共90条；请求日期20260713尚未发布，已返回最近可用日期20260710的数据"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=347',
  'test_status': '正常可用',
  'test_count': 90,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'limit_cpt_list',
  'title': '涨停最强板块统计',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 790,
  'method': 'GET',
  'path': '/api/v1/market/tushare/limit_cpt_list?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/limit_cpt_list',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：limit_cpt_list\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=357\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/limit_cpt_list?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "limit_cpt_list",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "cons_nums": "4",\n'
                      '      "days": 1,\n'
                      '      "name": "创新药",\n'
                      '      "pct_chg": -0.1024,\n'
                      '      "rank": 1,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "886015.TI",\n'
                      '      "up_nums": 9,\n'
                      '      "up_stat": "9天7板"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=357',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'limit_list_d',
  'title': '涨跌停和炸板数据',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 800,
  'method': 'GET',
  'path': '/api/v1/market/tushare/limit_list_d?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/limit_list_d',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：limit_list_d\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：215\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=298\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/limit_list_d?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "limit_list_d",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 215,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 1779195.0,\n'
                      '      "close": 0.51,\n'
                      '      "fd_amount": 2281221.0,\n'
                      '      "first_time": "92500",\n'
                      '      "float_mv": 64407424.68,\n'
                      '      "industry": "软件开发",\n'
                      '      "last_time": "92500",\n'
                      '      "limit": "U",\n'
                      '      "limit_amount": null,\n'
                      '      "limit_times": 3.0,\n'
                      '      "name": "国华退",\n'
                      '      "open_times": 0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共215条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=298',
  'test_status': '正常可用',
  'test_count': 215,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'limit_list_ths',
  'title': 'THS涨跌停榜单',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 810,
  'method': 'GET',
  'path': '/api/v1/market/tushare/limit_list_ths?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/limit_list_ths',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：limit_list_ths\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：31\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=355\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/limit_list_ths?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "limit_list_ths",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 31,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "free_float": 4558989200.0,\n'
                      '      "limit_amount": 47435384.0,\n'
                      '      "limit_order": 5936844.0,\n'
                      '      "limit_type": "涨停池",\n'
                      '      "limit_up_suc_rate": 0.8333,\n'
                      '      "lu_desc": "智能家居+跨境电商+美国产能",\n'
                      '      "lu_limit_order": null,\n'
                      '      "market_type": "HS",\n'
                      '      "name": "梦百合",\n'
                      '      "open_num": null,\n'
                      '      "pct_chg": 10.06,\n'
                      '      "price": 7.99\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共31条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=355',
  'test_status': '正常可用',
  'test_count': 31,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'limit_step',
  'title': '涨停股票连板天梯',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 820,
  'method': 'GET',
  'path': '/api/v1/market/tushare/limit_step?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/limit_step',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：limit_step\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：11\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=356\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/limit_step?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "limit_step",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 11,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "name": "ST龙元",\n'
                      '      "nums": "4",\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "600491.SH"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共11条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=356',
  'test_status': '正常可用',
  'test_count': 11,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'tdx_daily',
  'title': 'TDX概念板块行情',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 830,
  'method': 'GET',
  'path': '/api/v1/market/tushare/tdx_daily?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/tdx_daily',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：tdx_daily\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：617\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=378\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/tdx_daily?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "tdx_daily",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 617,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "10day": 10.16,\n'
                      '      "1year": 12.86,\n'
                      '      "20day": 3.1,\n'
                      '      "3day": 13.55,\n'
                      '      "5day": 7.1,\n'
                      '      "60day": 8.8,\n'
                      '      "ab_total_mv": 42.35,\n'
                      '      "amount": 12277.41,\n'
                      '      "bm_buy_net": 662.0,\n'
                      '      "bm_buy_ratio": 5.39,\n'
                      '      "bm_net": 2756.03,\n'
                      '      "bm_ratio": 22.45\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共617条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=378',
  'test_status': '正常可用',
  'test_count': 617,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'tdx_index',
  'title': 'TDX概念板块分类',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 840,
  'method': 'GET',
  'path': '/api/v1/market/tushare/tdx_index',
  'base_path': '/api/v1/market/tushare/tdx_index',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：tdx_index\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=376\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [],
  'request_example': 'GET /api/v1/market/tushare/tdx_index',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "tdx_index",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20250417",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "float_mv": 666.27,\n'
                      '      "float_share": 54.12,\n'
                      '      "idx_count": 9,\n'
                      '      "idx_type": "行业板块",\n'
                      '      "name": "酒店餐饮",\n'
                      '      "total_mv": 703.41,\n'
                      '      "total_share": 56.45,\n'
                      '      "trade_date": "20250417",\n'
                      '      "ts_code": "880423.TDX"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=376',
  'test_status': '正常可用',
  'test_count': 1000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'tdx_member',
  'title': 'TDX概念板块成分',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 850,
  'method': 'GET',
  'path': '/api/v1/market/tushare/tdx_member',
  'base_path': '/api/v1/market/tushare/tdx_member',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：tdx_member\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：3000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=377\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [],
  'request_example': 'GET /api/v1/market/tushare/tdx_member',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "tdx_member",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20250328",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 3000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "con_code": "000711.SZ",\n'
                      '      "con_name": "*ST京蓝",\n'
                      '      "trade_date": "20250328",\n'
                      '      "ts_code": "880201.TDX"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共3000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=377',
  'test_status': '正常可用',
  'test_count': 3000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'ths_daily',
  'title': 'THS概念板块行情',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 860,
  'method': 'GET',
  'path': '/api/v1/market/tushare/ths_daily?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/ths_daily',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：ths_daily\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1229\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=260\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/ths_daily?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "ths_daily",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1229,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "avg_price": 2.597,\n'
                      '      "change": -13.628,\n'
                      '      "close": 1001.123,\n'
                      '      "high": 1017.596,\n'
                      '      "low": 997.403,\n'
                      '      "open": 1013.047,\n'
                      '      "pct_change": -1.343,\n'
                      '      "pre_close": 1014.751,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "884052.TI",\n'
                      '      "turnover_rate": 0.930297,\n'
                      '      "vol": 14285689.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1229条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=260',
  'test_status': '正常可用',
  'test_count': 1229,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'ths_hot',
  'title': 'THS热榜',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 870,
  'method': 'GET',
  'path': '/api/v1/market/tushare/ths_hot?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/ths_hot',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：ths_hot\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：443\n'
                 '数据新鲜度：请求20260713，实际返回20260710最近可用数据。\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=320\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/ths_hot?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "ths_hot",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": "20260713",\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": true,\n'
                      '    "data_freshness": "latest_available",\n'
                      '    "fallback_attempt_count": 2\n'
                      '  },\n'
                      '  "count": 443,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "concept": null,\n'
                      '      "current_price": 0.0,\n'
                      '      "data_type": "期货",\n'
                      '      "hot": null,\n'
                      '      "pct_change": 2.71,\n'
                      '      "rank": 1,\n'
                      '      "rank_reason": null,\n'
                      '      "rank_time": "2026-07-10 22:30:00",\n'
                      '      "trade_date": "20260710",\n'
                      '      "ts_code": "002608.SZ",\n'
                      '      "ts_name": "鸡蛋2608"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共443条；请求日期20260713尚未发布，已返回最近可用日期20260710的数据"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=320',
  'test_status': '正常可用',
  'test_count': 443,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'ths_index',
  'title': 'THS概念板块分类',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 880,
  'method': 'GET',
  'path': '/api/v1/market/tushare/ths_index?exchange=A&type=N',
  'base_path': '/api/v1/market/tushare/ths_index',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：ths_index\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：409\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=259\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'exchange', 'type': 'string', 'required': '参考官网', 'example': 'A', 'description': '交易所或市场代码'},
             {'name': 'type', 'type': 'string', 'required': '参考官网', 'example': 'N', 'description': '接口类型参数'}],
  'request_example': 'GET /api/v1/market/tushare/ths_index?exchange=A&type=N',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "ths_index",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 409,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "count": 300.0,\n'
                      '      "exchange": "A",\n'
                      '      "list_date": "20100413",\n'
                      '      "name": "沪深300样本股",\n'
                      '      "ts_code": "883300.TI",\n'
                      '      "type": "N"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共409条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=259',
  'test_status': '正常可用',
  'test_count': 409,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'ths_member',
  'title': 'THS概念板块成分',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 890,
  'method': 'GET',
  'path': '/api/v1/market/tushare/ths_member',
  'base_path': '/api/v1/market/tushare/ths_member',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：ths_member\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：6000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=261\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [],
  'request_example': 'GET /api/v1/market/tushare/ths_member',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "ths_member",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 6000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "con_code": "000001.SZ",\n'
                      '      "con_name": "平安银行",\n'
                      '      "ts_code": "700001.TI"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共6000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=261',
  'test_status': '正常可用',
  'test_count': 6000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'top_inst',
  'title': '龙虎榜机构交易单',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 900,
  'method': 'GET',
  'path': '/api/v1/market/tushare/top_inst?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/top_inst',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：top_inst\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：935\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=107\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/top_inst?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "top_inst",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 935,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "buy": 1018827.0,\n'
                      '      "buy_rate": 57.26,\n'
                      '      "exalter": "光大证券股份有限公司重庆财富大道证券营业部",\n'
                      '      "net_buy": 1018827.0,\n'
                      '      "reason": "退市整理期",\n'
                      '      "sell": 0.0,\n'
                      '      "sell_rate": 0.0,\n'
                      '      "side": "0",\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "000004.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共935条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=107',
  'test_status': '正常可用',
  'test_count': 935,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'top_list',
  'title': '龙虎榜每日统计单',
  'category': '打板专题数据',
  'category_description': '龙虎榜、涨跌停、概念板块、热榜、游资及题材库接口。',
  'category_sort_order': 110,
  'sort_order': 910,
  'method': 'GET',
  'path': '/api/v1/market/tushare/top_list?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/top_list',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：top_list\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：91\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=106\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/top_list?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "top_list",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 91,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 1779195.0,\n'
                      '      "amount_rate": 135.05,\n'
                      '      "close": 0.51,\n'
                      '      "float_values": 64407424.68,\n'
                      '      "l_amount": 2402763.0,\n'
                      '      "l_buy": 1717578.0,\n'
                      '      "l_sell": 685185.0,\n'
                      '      "name": "国华退",\n'
                      '      "net_amount": 1032393.0,\n'
                      '      "net_rate": 58.03,\n'
                      '      "pct_change": 10.8696,\n'
                      '      "reason": "退市整理期"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共91条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=106',
  'test_status': '正常可用',
  'test_count': 91,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'broker_recommend',
  'title': '券商月度金股',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 920,
  'method': 'GET',
  'path': '/api/v1/market/tushare/broker_recommend?month=202607',
  'base_path': '/api/v1/market/tushare/broker_recommend',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：broker_recommend\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：308\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=267\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'month',
              'type': 'string',
              'required': '参考官网',
              'example': '202607',
              'description': '月份，格式YYYYMM'}],
  'request_example': 'GET /api/v1/market/tushare/broker_recommend?month=202607',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "broker_recommend",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 308,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "broker": "东兴证券",\n'
                      '      "month": "202607",\n'
                      '      "name": "宝武镁业",\n'
                      '      "ts_code": "002182.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共308条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=267',
  'test_status': '正常可用',
  'test_count': 308,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'ccass_hold',
  'title': '中央结算系统持股统计',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 930,
  'method': 'GET',
  'path': '/api/v1/market/tushare/ccass_hold?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/ccass_hold',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：ccass_hold\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：5000\n'
                 '数据新鲜度：请求20260713，实际返回20260710最近可用数据。\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=295\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/ccass_hold?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "ccass_hold",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": "20260713",\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": true,\n'
                      '    "data_freshness": "latest_available",\n'
                      '    "fallback_attempt_count": 2\n'
                      '  },\n'
                      '  "count": 5000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "hold_nums": "11",\n'
                      '      "hold_ratio": "0.48",\n'
                      '      "name": "品茗科技",\n'
                      '      "shareholding": "383392",\n'
                      '      "trade_date": "20260710",\n'
                      '      "ts_code": "30109.HK"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共5000条；请求日期20260713尚未发布，已返回最近可用日期20260710的数据"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=295',
  'test_status': '正常可用',
  'test_count': 5000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'ccass_hold_detail',
  'title': '中央结算系统持股明细',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 940,
  'method': 'GET',
  'path': '/api/v1/market/tushare/ccass_hold_detail?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/ccass_hold_detail',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：ccass_hold_detail\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：15\n'
                 '数据新鲜度：请求20260713，实际返回20260710最近可用数据。\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=274\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/ccass_hold_detail?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "ccass_hold_detail",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": "20260713",\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": true,\n'
                      '    "data_freshness": "latest_available",\n'
                      '    "fallback_attempt_count": 2\n'
                      '  },\n'
                      '  "count": 15,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "col_participant_id": "C00039",\n'
                      '      "col_participant_name": "渣打銀行(香港)有限公司",\n'
                      '      "col_shareholding": "80835",\n'
                      '      "col_shareholding_percent": "0.02",\n'
                      '      "name": "財富趨勢",\n'
                      '      "trade_date": "20260710",\n'
                      '      "ts_code": "30318.HK"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共15条；请求日期20260713尚未发布，已返回最近可用日期20260710的数据"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=274',
  'test_status': '正常可用',
  'test_count': 15,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'cyq_chips',
  'title': '每日筹码分布',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 950,
  'method': 'GET',
  'path': '/api/v1/market/tushare/cyq_chips?ts_code=000001.SZ&trade_date=20260713',
  'base_path': '/api/v1/market/tushare/cyq_chips',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：cyq_chips\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：104\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=294\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/cyq_chips?ts_code=000001.SZ&trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "cyq_chips",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 104,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "percent": 0.01,\n'
                      '      "price": 0.2,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共104条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=294',
  'test_status': '正常可用',
  'test_count': 104,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'cyq_perf',
  'title': '每日筹码及胜率',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 960,
  'method': 'GET',
  'path': '/api/v1/market/tushare/cyq_perf?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/cyq_perf',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：cyq_perf\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=293\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/cyq_perf?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "cyq_perf",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "cost_15pct": 10.4,\n'
                      '      "cost_50pct": 10.6,\n'
                      '      "cost_5pct": 10.0,\n'
                      '      "cost_85pct": 11.2,\n'
                      '      "cost_95pct": 12.2,\n'
                      '      "his_high": 20.8,\n'
                      '      "his_low": 0.2,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "000001.SZ",\n'
                      '      "weight_avg": 10.9,\n'
                      '      "winner_rate": 30.58\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=293',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'hk_hold',
  'title': '沪深股通持股明细',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 970,
  'method': 'GET',
  'path': '/api/v1/market/tushare/hk_hold?trade_date=20260713&exchange=HK',
  'base_path': '/api/v1/market/tushare/hk_hold',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：hk_hold\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：948\n'
                 '数据新鲜度：请求20260713，实际返回20260710最近可用数据。\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=188\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'},
             {'name': 'exchange', 'type': 'string', 'required': '参考官网', 'example': 'HK', 'description': '交易所或市场代码'}],
  'request_example': 'GET /api/v1/market/tushare/hk_hold?trade_date=20260713&exchange=HK',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "hk_hold",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": "20260713",\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": true,\n'
                      '    "data_freshness": "latest_available",\n'
                      '    "fallback_attempt_count": 2\n'
                      '  },\n'
                      '  "count": 948,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "code": "1",\n'
                      '      "exchange": "HK",\n'
                      '      "name": "長和",\n'
                      '      "ratio": 2.01,\n'
                      '      "trade_date": "20260710",\n'
                      '      "ts_code": "00001.HK",\n'
                      '      "vol": 77390590\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共948条；请求日期20260713尚未发布，已返回最近可用日期20260710的数据"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=188',
  'test_status': '正常可用',
  'test_count': 948,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'irm_qa_sh',
  'title': '上证e互动问答',
  'category': '大模型语料',
  'category_description': '交易所投资者互动问答语料接口，属于Tushare单独权限。',
  'category_sort_order': 120,
  'sort_order': 980,
  'method': 'GET',
  'path': '/api/v1/market/tushare/irm_qa_sh?ts_code=600000.SH&start_date=20260315&end_date=20260713',
  'base_path': '/api/v1/market/tushare/irm_qa_sh',
  'scope': 'tushare:independent:special:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：irm_qa_sh\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=366\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '600000.SH',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260315',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/irm_qa_sh?ts_code=600000.SH&start_date=20260315&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "irm_qa_sh",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=366',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'irm_qa_sz',
  'title': '深证易互动问答',
  'category': '大模型语料',
  'category_description': '交易所投资者互动问答语料接口，属于Tushare单独权限。',
  'category_sort_order': 120,
  'sort_order': 990,
  'method': 'GET',
  'path': '/api/v1/market/tushare/irm_qa_sz?ts_code=000001.SZ&start_date=20260315&end_date=20260713',
  'base_path': '/api/v1/market/tushare/irm_qa_sz',
  'scope': 'tushare:independent:special:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：irm_qa_sz\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=367\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260315',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/irm_qa_sz?ts_code=000001.SZ&start_date=20260315&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "irm_qa_sz",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=367',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'report_rc',
  'title': '券商盈利预测数据',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 1000,
  'method': 'GET',
  'path': '/api/v1/market/tushare/report_rc?ts_code=000001.SZ&start_date=20250713&end_date=20260713',
  'base_path': '/api/v1/market/tushare/report_rc',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：report_rc\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：258\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=292\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20250713',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/report_rc?ts_code=000001.SZ&start_date=20250713&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "report_rc",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 258,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "author_name": "徐凝碧,林加力",\n'
                      '      "classify": "一般报告",\n'
                      '      "eps": 2.1,\n'
                      '      "ev_ebitda": null,\n'
                      '      "max_price": null,\n'
                      '      "min_price": null,\n'
                      '      "name": "平安银行",\n'
                      '      "np": 4075242.822,\n'
                      '      "op_pr": null,\n'
                      '      "op_rt": null,\n'
                      '      "org_name": "国海证券",\n'
                      '      "pe": null\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共258条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=292',
  'test_status': '正常可用',
  'test_count': 258,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_ah_comparison',
  'title': 'AH股比价',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 1010,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_ah_comparison',
  'base_path': '/api/v1/market/tushare/stk_ah_comparison',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_ah_comparison\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1000\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=399\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [],
  'request_example': 'GET /api/v1/market/tushare/stk_ah_comparison',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_ah_comparison",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1000,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ah_comparison": 1.21,\n'
                      '      "ah_premium": 20.96,\n'
                      '      "close": 6.59,\n'
                      '      "hk_close": 6.3,\n'
                      '      "hk_code": "03618.HK",\n'
                      '      "hk_name": "重庆农村商业银行",\n'
                      '      "hk_pct_chg": 3.96,\n'
                      '      "name": "渝农商行",\n'
                      '      "pct_chg": 4.6,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "601077.SH"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1000条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=399',
  'test_status': '正常可用',
  'test_count': 1000,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_auction_c',
  'title': '股票收盘集合竞价数据',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 1020,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_auction_c?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/stk_auction_c',
  'scope': 'tushare:independent:special:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：stk_auction_c\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=354\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/stk_auction_c?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_auction_c",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=354',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'stk_auction_o',
  'title': '股票开盘集合竞价数据',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 1030,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_auction_o?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/stk_auction_o',
  'scope': 'tushare:independent:special:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：stk_auction_o\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=353\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/stk_auction_o?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_auction_o",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=353',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'stk_factor',
  'title': '股票技术面因子',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 1040,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_factor?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/stk_factor',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_factor\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=296\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/stk_factor?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_factor",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "adj_factor": 139.008,\n'
                      '      "amount": 971033.14,\n'
                      '      "boll_lower": 10.0,\n'
                      '      "boll_mid": 10.494,\n'
                      '      "boll_upper": 10.989,\n'
                      '      "cci": 59.562,\n'
                      '      "change": 0.09,\n'
                      '      "close": 10.54,\n'
                      '      "close_hfq": 1465.14432,\n'
                      '      "close_qfq": 10.54,\n'
                      '      "high": 10.55,\n'
                      '      "high_hfq": 1466.5344\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=296',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_factor_pro',
  'title': '股票技术面因子(专业版)',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 1050,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_factor_pro?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/stk_factor_pro',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_factor_pro\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=328\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET '
                     '/api/v1/market/tushare/stk_factor_pro?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_factor_pro",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "adj_factor": 139.008,\n'
                      '      "amount": 971033.14,\n'
                      '      "asi_bfq": -10.26077,\n'
                      '      "asi_hfq": -792.08571,\n'
                      '      "asi_qfq": -5.69813,\n'
                      '      "asit_bfq": -13.99489,\n'
                      '      "asit_hfq": -1311.5134,\n'
                      '      "asit_qfq": -9.43481,\n'
                      '      "atr_bfq": 0.227,\n'
                      '      "atr_hfq": 31.55482,\n'
                      '      "atr_qfq": 0.227,\n'
                      '      "bbi_bfq": 10.46363\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=328',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_nineturn',
  'title': '神奇九转指标',
  'category': '股票特色数据',
  'category_description': '筹码、技术因子、中央结算持股、集合竞价及AH股比价等接口。',
  'category_sort_order': 80,
  'sort_order': 1060,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_nineturn?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/stk_nineturn',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_nineturn\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=364\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/stk_nineturn?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_nineturn",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 971033.14,\n'
                      '      "close": 10.54,\n'
                      '      "down_count": 0.0,\n'
                      '      "freq": "daily",\n'
                      '      "high": 10.55,\n'
                      '      "low": 10.38,\n'
                      '      "nine_down_turn": null,\n'
                      '      "nine_up_turn": null,\n'
                      '      "open": 10.42,\n'
                      '      "trade_date": "2026-07-13 00:00:00",\n'
                      '      "ts_code": "000001.SZ",\n'
                      '      "up_count": 1.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=364',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'adj_factor',
  'title': '复权因子',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1070,
  'method': 'GET',
  'path': '/api/v1/market/tushare/adj_factor?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/adj_factor',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：adj_factor\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=28\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/adj_factor?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "adj_factor",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "adj_factor": 139.008,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=28',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'bak_daily',
  'title': '备用行情',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1080,
  'method': 'GET',
  'path': '/api/v1/market/tushare/bak_daily?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/bak_daily',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：bak_daily\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：5532\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=255\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/bak_daily?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "bak_daily",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 5532,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "activity": 4749.0,\n'
                      '      "amount": 97103.32,\n'
                      '      "area": "深圳",\n'
                      '      "attack": 1.54,\n'
                      '      "avg_price": 10.5,\n'
                      '      "avg_turnover": 0.0,\n'
                      '      "buying": 511968.0,\n'
                      '      "change": 0.09,\n'
                      '      "close": 10.54,\n'
                      '      "float_mv": 2045.35,\n'
                      '      "float_share": 194.06,\n'
                      '      "high": 10.55\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共5532条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=255',
  'test_status': '正常可用',
  'test_count': 5532,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'daily',
  'title': '历史日线',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1090,
  'method': 'GET',
  'path': '/api/v1/market/tushare/daily?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/daily',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：daily\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=27\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/daily?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "daily",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 971033.14443,\n'
                      '      "change": 0.09,\n'
                      '      "close": 10.54,\n'
                      '      "high": 10.55,\n'
                      '      "low": 10.38,\n'
                      '      "open": 10.42,\n'
                      '      "pct_chg": 0.8612,\n'
                      '      "pre_close": 10.45,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "000001.SZ",\n'
                      '      "vol": 924746.24\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=27',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'daily_basic',
  'title': '每日指标',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1100,
  'method': 'GET',
  'path': '/api/v1/market/tushare/daily_basic?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/daily_basic',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：daily_basic\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=32\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/daily_basic?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "daily_basic",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "circ_mv": 20453503.1378,\n'
                      '      "close": 10.54,\n'
                      '      "dv_ratio": 5.6738,\n'
                      '      "dv_ttm": 5.6547,\n'
                      '      "float_share": 1940560.0653,\n'
                      '      "free_share": 816048.1215,\n'
                      '      "pb": 0.4407,\n'
                      '      "pe": 4.7977,\n'
                      '      "pe_ttm": 4.7501,\n'
                      '      "ps": 1.5561,\n'
                      '      "ps_ttm": 1.5378,\n'
                      '      "total_mv": 20453837.7828\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=32',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'ggt_daily',
  'title': '港股通每日成交统计',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1110,
  'method': 'GET',
  'path': '/api/v1/market/tushare/ggt_daily?start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/ggt_daily',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：ggt_daily\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：18\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=196\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/ggt_daily?start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "ggt_daily",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 18,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "buy_amount": 467.5,\n'
                      '      "buy_volume": 78.21,\n'
                      '      "sell_amount": 500.94,\n'
                      '      "sell_volume": 75.94,\n'
                      '      "trade_date": "20260710"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共18条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=196',
  'test_status': '正常可用',
  'test_count': 18,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'ggt_top10',
  'title': '港股通十大成交股',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1120,
  'method': 'GET',
  'path': '/api/v1/market/tushare/ggt_top10?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/ggt_top10',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：ggt_top10\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=49\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/ggt_top10?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "ggt_top10",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=49',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'hsgt_top10',
  'title': '沪深股通十大成交股',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1130,
  'method': 'GET',
  'path': '/api/v1/market/tushare/hsgt_top10?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/hsgt_top10',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：hsgt_top10\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=48\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/hsgt_top10?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "hsgt_top10",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=48',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'monthly',
  'title': '月线行情',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1140,
  'method': 'GET',
  'path': '/api/v1/market/tushare/monthly?ts_code=000001.SZ&start_date=20250713&end_date=20260713',
  'base_path': '/api/v1/market/tushare/monthly',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：monthly\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：12\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=145\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20250713',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/monthly?ts_code=000001.SZ&start_date=20250713&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "monthly",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260630",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 12,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 26553616134.33,\n'
                      '      "change": -0.88,\n'
                      '      "close": 10.05,\n'
                      '      "high": 11.39,\n'
                      '      "low": 10.02,\n'
                      '      "open": 10.9,\n'
                      '      "pct_chg": -0.0805,\n'
                      '      "pre_close": 10.93,\n'
                      '      "trade_date": "20260630",\n'
                      '      "ts_code": "000001.SZ",\n'
                      '      "vol": 2452489226.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共12条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=145',
  'test_status': '正常可用',
  'test_count': 12,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'pro_bar',
  'title': '复权行情',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1150,
  'method': 'GET',
  'path': '/api/v1/market/tushare/pro_bar?ts_code=000001.SZ&asset=E&freq=D&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/pro_bar',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：pro_bar\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=146\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'asset', 'type': 'string', 'required': '参考官网', 'example': 'E', 'description': '资产类别'},
             {'name': 'freq', 'type': 'string', 'required': '参考官网', 'example': 'D', 'description': '数据频率，例如1MIN或1min'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET '
                     '/api/v1/market/tushare/pro_bar?ts_code=000001.SZ&asset=E&freq=D&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "pro_bar",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 971033.14443,\n'
                      '      "change": 0.09,\n'
                      '      "close": 10.54,\n'
                      '      "high": 10.55,\n'
                      '      "low": 10.38,\n'
                      '      "open": 10.42,\n'
                      '      "pct_chg": 0.86,\n'
                      '      "pre_close": 10.45,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "000001.SZ",\n'
                      '      "vol": 924746.24\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=146',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'rt_k',
  'title': '实时日线',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1160,
  'method': 'GET',
  'path': '/api/v1/market/tushare/rt_k?ts_code=000001.SZ',
  'base_path': '/api/v1/market/tushare/rt_k',
  'scope': 'tushare:independent:realtime:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：rt_k\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=372\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'}],
  'request_example': 'GET /api/v1/market/tushare/rt_k?ts_code=000001.SZ',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "rt_k",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 971033144.43,\n'
                      '      "close": 10.54,\n'
                      '      "high": 10.55,\n'
                      '      "low": 10.38,\n'
                      '      "name": "平安银行",\n'
                      '      "num": 76166,\n'
                      '      "open": 10.42,\n'
                      '      "pre_close": 10.45,\n'
                      '      "ts_code": "000001.SZ",\n'
                      '      "vol": 92474624\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=372',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'rt_min',
  'title': '实时分钟',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1170,
  'method': 'GET',
  'path': '/api/v1/market/tushare/rt_min?ts_code=000001.SZ&freq=1MIN',
  'base_path': '/api/v1/market/tushare/rt_min',
  'scope': 'tushare:independent:realtime:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：rt_min\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=374\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'freq',
              'type': 'string',
              'required': '参考官网',
              'example': '1MIN',
              'description': '数据频率，例如1MIN或1min'}],
  'request_example': 'GET /api/v1/market/tushare/rt_min?ts_code=000001.SZ&freq=1MIN',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "rt_min",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 5327232.2,\n'
                      '      "close": 10.54,\n'
                      '      "freq": "1MIN",\n'
                      '      "high": 10.54,\n'
                      '      "low": 10.54,\n'
                      '      "open": 10.54,\n'
                      '      "time": "2026-07-13 15:00:00",\n'
                      '      "ts_code": "000001.SZ",\n'
                      '      "vol": 505430.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=374',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'rt_min_daily',
  'title': 'A股实时分钟-日累计',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1180,
  'method': 'GET',
  'path': '/api/v1/market/tushare/rt_min_daily?ts_code=000001.SZ&freq=1MIN',
  'base_path': '/api/v1/market/tushare/rt_min_daily',
  'scope': 'tushare:independent:realtime:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：rt_min_daily\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：中转路由未配置；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=457\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'freq',
              'type': 'string',
              'required': '参考官网',
              'example': '1MIN',
              'description': '数据频率，例如1MIN或1min'}],
  'request_example': 'GET /api/v1/market/tushare/rt_min_daily?ts_code=000001.SZ&freq=1MIN',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "rt_min_daily",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=457',
  'test_status': '中转路由未配置',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'stk_limit',
  'title': '每日涨跌停价格',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1190,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_limit?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/stk_limit',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：stk_limit\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：7695\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=183\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/stk_limit?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_limit",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 7695,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "down_limit": 9.41,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "000001.SZ",\n'
                      '      "up_limit": 11.5\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共7695条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=183',
  'test_status': '正常可用',
  'test_count': 7695,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'stk_mins',
  'title': '历史分钟',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1200,
  'method': 'GET',
  'path': '/api/v1/market/tushare/stk_mins?ts_code=000001.SZ&freq=1min&start_date=2026-07-13+09%3A00%3A00&end_date=2026-07-13+15%3A30%3A00',
  'base_path': '/api/v1/market/tushare/stk_mins',
  'scope': 'tushare:independent:history:read',
  'permission_label': '特殊权限（Tushare单独权限）',
  'description': '接口英文名：stk_mins\n'
                 '套餐权限：特殊权限（Tushare单独权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=370\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'freq',
              'type': 'string',
              'required': '参考官网',
              'example': '1min',
              'description': '数据频率，例如1MIN或1min'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '2026-07-13 09:00:00',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '2026-07-13 15:30:00',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET '
                     '/api/v1/market/tushare/stk_mins?ts_code=000001.SZ&freq=1min&start_date=2026-07-13+09%3A00%3A00&end_date=2026-07-13+15%3A30%3A00',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "stk_mins",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=370',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'suspend_d',
  'title': '每日停复牌信息',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1210,
  'method': 'GET',
  'path': '/api/v1/market/tushare/suspend_d?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/suspend_d',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：suspend_d\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：中转Token未开通；数据条数：0\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=214\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/suspend_d?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "suspend_d",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 0,\n'
                      '  "data": [],\n'
                      '  "msg": "获取成功，共0条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=214',
  'test_status': '中转Token未开通',
  'test_count': 0,
  'is_callable': False,
  'has_data': False},
 {'provider': 'tushare',
  'api_name': 'weekly',
  'title': '周线行情',
  'category': '股票行情数据',
  'category_description': 'A股日线、周线、月线、实时行情、分钟行情和交易统计接口。',
  'category_sort_order': 50,
  'sort_order': 1220,
  'method': 'GET',
  'path': '/api/v1/market/tushare/weekly?ts_code=000001.SZ&start_date=20260315&end_date=20260713',
  'base_path': '/api/v1/market/tushare/weekly',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：weekly\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：17\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=144\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260315',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/weekly?ts_code=000001.SZ&start_date=20260315&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "weekly",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260710",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 17,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amount": 4732098271.12,\n'
                      '      "change": 0.16,\n'
                      '      "close": 10.45,\n'
                      '      "high": 10.63,\n'
                      '      "low": 10.22,\n'
                      '      "open": 10.25,\n'
                      '      "pct_chg": 0.0155,\n'
                      '      "pre_close": 10.29,\n'
                      '      "trade_date": "20260710",\n'
                      '      "ts_code": "000001.SZ",\n'
                      '      "vol": 452154136.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共17条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=144',
  'test_status': '正常可用',
  'test_count': 17,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'balancesheet',
  'title': '资产负债表',
  'category': '股票财务数据',
  'category_description': '利润表、资产负债表、现金流量表、财务指标及披露日期接口。',
  'category_sort_order': 60,
  'sort_order': 1230,
  'method': 'GET',
  'path': '/api/v1/market/tushare/balancesheet?ts_code=000001.SZ&period=20251231',
  'base_path': '/api/v1/market/tushare/balancesheet',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：balancesheet\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：2\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=36\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'period',
              'type': 'string',
              'required': '参考官网',
              'example': '20251231',
              'description': '报告期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/balancesheet?ts_code=000001.SZ&period=20251231',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "balancesheet",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 2,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "acc_exp": null,\n'
                      '      "acc_receivable": null,\n'
                      '      "accounts_pay": null,\n'
                      '      "accounts_receiv": null,\n'
                      '      "accounts_receiv_bill": null,\n'
                      '      "acct_payable": null,\n'
                      '      "acting_trading_sec": null,\n'
                      '      "acting_uw_sec": null,\n'
                      '      "adv_receipts": null,\n'
                      '      "agency_bus_liab": null,\n'
                      '      "amor_exp": null,\n'
                      '      "ann_date": "20260321"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共2条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=36',
  'test_status': '正常可用',
  'test_count': 2,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'cashflow',
  'title': '现金流量表',
  'category': '股票财务数据',
  'category_description': '利润表、资产负债表、现金流量表、财务指标及披露日期接口。',
  'category_sort_order': 60,
  'sort_order': 1240,
  'method': 'GET',
  'path': '/api/v1/market/tushare/cashflow?ts_code=000001.SZ&period=20251231',
  'base_path': '/api/v1/market/tushare/cashflow',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：cashflow\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=44\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'period',
              'type': 'string',
              'required': '参考官网',
              'example': '20251231',
              'description': '报告期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/cashflow?ts_code=000001.SZ&period=20251231',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "cashflow",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "amort_intang_assets": 849000000.0,\n'
                      '      "ann_date": "20260321",\n'
                      '      "beg_bal_cash": 3421000000.0,\n'
                      '      "beg_bal_cash_equ": 253525000000.0,\n'
                      '      "c_cash_equ_beg_period": 256946000000.0,\n'
                      '      "c_cash_equ_end_period": 342635000000.0,\n'
                      '      "c_disp_withdrwl_invest": 864286000000.0,\n'
                      '      "c_fr_oth_operate_a": 79462000000.0,\n'
                      '      "c_fr_sale_sg": null,\n'
                      '      "c_inf_fr_operate_a": 625358000000.0,\n'
                      '      "c_paid_for_taxes": 25048000000.0,\n'
                      '      "c_paid_goods_s": null\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=44',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'disclosure_date',
  'title': '财报披露日期表',
  'category': '股票财务数据',
  'category_description': '利润表、资产负债表、现金流量表、财务指标及披露日期接口。',
  'category_sort_order': 60,
  'sort_order': 1250,
  'method': 'GET',
  'path': '/api/v1/market/tushare/disclosure_date?end_date=20251231',
  'base_path': '/api/v1/market/tushare/disclosure_date',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：disclosure_date\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：5531\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=162\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20251231',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/disclosure_date?end_date=20251231',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "disclosure_date",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 5531,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "actual_date": "20260430",\n'
                      '      "ann_date": null,\n'
                      '      "end_date": "20251231",\n'
                      '      "pre_date": null,\n'
                      '      "ts_code": "600200.SH"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共5531条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=162',
  'test_status': '正常可用',
  'test_count': 5531,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'dividend',
  'title': '分红送股数据',
  'category': '股票财务数据',
  'category_description': '利润表、资产负债表、现金流量表、财务指标及披露日期接口。',
  'category_sort_order': 60,
  'sort_order': 1260,
  'method': 'GET',
  'path': '/api/v1/market/tushare/dividend?ts_code=000001.SZ',
  'base_path': '/api/v1/market/tushare/dividend',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：dividend\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：53\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=103\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'}],
  'request_example': 'GET /api/v1/market/tushare/dividend?ts_code=000001.SZ',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "dividend",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 53,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ann_date": "20260321",\n'
                      '      "cash_div": 0.0,\n'
                      '      "cash_div_tax": 0.36,\n'
                      '      "div_listdate": null,\n'
                      '      "div_proc": "预案",\n'
                      '      "end_date": "20251231",\n'
                      '      "ex_date": null,\n'
                      '      "imp_ann_date": null,\n'
                      '      "pay_date": null,\n'
                      '      "record_date": null,\n'
                      '      "stk_bo_rate": null,\n'
                      '      "stk_co_rate": null\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共53条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=103',
  'test_status': '正常可用',
  'test_count': 53,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'express',
  'title': '业绩快报',
  'category': '股票财务数据',
  'category_description': '利润表、资产负债表、现金流量表、财务指标及披露日期接口。',
  'category_sort_order': 60,
  'sort_order': 1270,
  'method': 'GET',
  'path': '/api/v1/market/tushare/express?period=20251231',
  'base_path': '/api/v1/market/tushare/express',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：express\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1149\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=46\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'period',
              'type': 'string',
              'required': '参考官网',
              'example': '20251231',
              'description': '报告期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/express?period=20251231',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "express",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1149,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ann_date": "20260105",\n'
                      '      "bps": null,\n'
                      '      "diluted_eps": 0.4,\n'
                      '      "diluted_roe": 10.34,\n'
                      '      "end_date": "20251231",\n'
                      '      "n_income": 404513100.0,\n'
                      '      "operate_profit": 503805300.0,\n'
                      '      "perf_summary": null,\n'
                      '      "revenue": 17684876700.0,\n'
                      '      "total_assets": 38803155400.0,\n'
                      '      "total_hldr_eqy_exc_min_int": 4055785000.0,\n'
                      '      "total_profit": 492415300.0\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1149条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=46',
  'test_status': '正常可用',
  'test_count': 1149,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'fina_audit',
  'title': '财务审计意见',
  'category': '股票财务数据',
  'category_description': '利润表、资产负债表、现金流量表、财务指标及披露日期接口。',
  'category_sort_order': 60,
  'sort_order': 1280,
  'method': 'GET',
  'path': '/api/v1/market/tushare/fina_audit?ts_code=000001.SZ&period=20251231',
  'base_path': '/api/v1/market/tushare/fina_audit',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：fina_audit\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=80\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'period',
              'type': 'string',
              'required': '参考官网',
              'example': '20251231',
              'description': '报告期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/fina_audit?ts_code=000001.SZ&period=20251231',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "fina_audit",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ann_date": "20260321",\n'
                      '      "audit_agency": "安永华明会计师事务所",\n'
                      '      "audit_fees": 9140000.0,\n'
                      '      "audit_result": "标准无保留意见",\n'
                      '      "audit_sign": "陈胜,罗杨",\n'
                      '      "end_date": "20251231",\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=80',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'fina_indicator',
  'title': '财务指标数据',
  'category': '股票财务数据',
  'category_description': '利润表、资产负债表、现金流量表、财务指标及披露日期接口。',
  'category_sort_order': 60,
  'sort_order': 1290,
  'method': 'GET',
  'path': '/api/v1/market/tushare/fina_indicator?ts_code=000001.SZ&period=20251231',
  'base_path': '/api/v1/market/tushare/fina_indicator',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：fina_indicator\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=79\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'period',
              'type': 'string',
              'required': '参考官网',
              'example': '20251231',
              'description': '报告期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/fina_indicator?ts_code=000001.SZ&period=20251231',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "fina_indicator",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "adminexp_of_gr": 29.0592,\n'
                      '      "ann_date": "20260321",\n'
                      '      "ar_turn": null,\n'
                      '      "assets_to_eqt": 10.751,\n'
                      '      "assets_turn": 0.0225,\n'
                      '      "assets_yoy": 2.7128,\n'
                      '      "basic_eps_yoy": -3.7209,\n'
                      '      "bps": 23.2522,\n'
                      '      "bps_yoy": 6.2,\n'
                      '      "ca_to_assets": null,\n'
                      '      "ca_turn": null,\n'
                      '      "capital_rese_ps": 4.1555\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=79',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'fina_mainbz',
  'title': '主营业务构成',
  'category': '股票财务数据',
  'category_description': '利润表、资产负债表、现金流量表、财务指标及披露日期接口。',
  'category_sort_order': 60,
  'sort_order': 1300,
  'method': 'GET',
  'path': '/api/v1/market/tushare/fina_mainbz?ts_code=000001.SZ&period=20251231',
  'base_path': '/api/v1/market/tushare/fina_mainbz',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：fina_mainbz\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：28\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=81\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'period',
              'type': 'string',
              'required': '参考官网',
              'example': '20251231',
              'description': '报告期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/fina_mainbz?ts_code=000001.SZ&period=20251231',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "fina_mainbz",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 28,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "bz_code": "D",\n'
                      '      "bz_cost": 6903000000.0,\n'
                      '      "bz_item": "东区",\n'
                      '      "bz_profit": 13115000000.0,\n'
                      '      "bz_sales": 20018000000.0,\n'
                      '      "curr_type": "CNY",\n'
                      '      "end_date": "20251231",\n'
                      '      "ts_code": "000001.SZ"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共28条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=81',
  'test_status': '正常可用',
  'test_count': 28,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'forecast',
  'title': '业绩预告',
  'category': '股票财务数据',
  'category_description': '利润表、资产负债表、现金流量表、财务指标及披露日期接口。',
  'category_sort_order': 60,
  'sort_order': 1310,
  'method': 'GET',
  'path': '/api/v1/market/tushare/forecast?ann_date=20260713',
  'base_path': '/api/v1/market/tushare/forecast',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：forecast\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：10\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=45\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ann_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '公告日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/forecast?ann_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "forecast",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 10,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ann_date": "20260713",\n'
                      '      "change_reason": '
                      '"经公司财务部门初步测算，公司预计实现归属于上市公司股东的净利润为3,800万元–5,000万元，较上年同期增长965.92%–1,302.52%；实现饲料销量45万吨，同比增长33%。报告期内公司业绩同比实现较大增长的主要驱动因素如下：1、公司产品质量持续稳定提升，客户认可度与忠诚度进一步增加，“粤海阳光行”主题...",\n'
                      '      "end_date": "20260630",\n'
                      '      "first_ann_date": "20260713",\n'
                      '      "last_parent_net": 356.5,\n'
                      '      "net_profit_max": 5000.0,\n'
                      '      "net_profit_min": 3800.0,\n'
                      '      "p_change_max": 1302.52,\n'
                      '      "p_change_min": 965.92,\n'
                      '      "summary": "预计:净利润3800-5000",\n'
                      '      "ts_code": "001313.SZ",\n'
                      '      "type": "预增"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共10条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=45',
  'test_status': '正常可用',
  'test_count': 10,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'income',
  'title': '利润表',
  'category': '股票财务数据',
  'category_description': '利润表、资产负债表、现金流量表、财务指标及披露日期接口。',
  'category_sort_order': 60,
  'sort_order': 1320,
  'method': 'GET',
  'path': '/api/v1/market/tushare/income?ts_code=000001.SZ&period=20251231',
  'base_path': '/api/v1/market/tushare/income',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：income\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=33\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'period',
              'type': 'string',
              'required': '参考官网',
              'example': '20251231',
              'description': '报告期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/income?ts_code=000001.SZ&period=20251231',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "income",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": null,\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "adj_lossgain": null,\n'
                      '      "admin_exp": 38196000000.0,\n'
                      '      "ann_date": "20260321",\n'
                      '      "ass_invest_income": null,\n'
                      '      "assets_impair_loss": null,\n'
                      '      "basic_eps": 2.07,\n'
                      '      "biz_tax_surchg": 1271000000.0,\n'
                      '      "capit_comstock_div": null,\n'
                      '      "comm_exp": 3346000000.0,\n'
                      '      "comm_income": 27240000000.0,\n'
                      '      "comp_type": "2",\n'
                      '      "compens_payout": null\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=33',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'moneyflow',
  'title': '个股资金流向',
  'category': '资金流向数据',
  'category_description': '个股、行业、市场及沪深港通资金流向接口。',
  'category_sort_order': 100,
  'sort_order': 1330,
  'method': 'GET',
  'path': '/api/v1/market/tushare/moneyflow?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/moneyflow',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：moneyflow\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=170\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/moneyflow?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "moneyflow",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "buy_elg_amount": 19479.95,\n'
                      '      "buy_elg_vol": 185672,\n'
                      '      "buy_lg_amount": 24335.44,\n'
                      '      "buy_lg_vol": 231948,\n'
                      '      "buy_md_amount": 26975.09,\n'
                      '      "buy_md_vol": 256778,\n'
                      '      "buy_sm_amount": 26312.83,\n'
                      '      "buy_sm_vol": 250348,\n'
                      '      "net_mf_amount": 11148.04,\n'
                      '      "net_mf_vol": 105602,\n'
                      '      "sell_elg_amount": 22474.53,\n'
                      '      "sell_elg_vol": 214127\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=170',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'moneyflow_dc',
  'title': '个股资金流向(DC)',
  'category': '资金流向数据',
  'category_description': '个股、行业、市场及沪深港通资金流向接口。',
  'category_sort_order': 100,
  'sort_order': 1340,
  'method': 'GET',
  'path': '/api/v1/market/tushare/moneyflow_dc?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/moneyflow_dc',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：moneyflow_dc\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=349\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/moneyflow_dc?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "moneyflow_dc",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "buy_elg_amount": -2835.12,\n'
                      '      "buy_elg_amount_rate": -2.92,\n'
                      '      "buy_lg_amount": 931.03,\n'
                      '      "buy_lg_amount_rate": 0.96,\n'
                      '      "buy_md_amount": -821.76,\n'
                      '      "buy_md_amount_rate": -0.85,\n'
                      '      "buy_sm_amount": 2725.86,\n'
                      '      "buy_sm_amount_rate": 2.81,\n'
                      '      "close": 10.54,\n'
                      '      "name": "平安银行",\n'
                      '      "net_amount": -1904.1,\n'
                      '      "net_amount_rate": -1.96\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=349',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'moneyflow_hsgt',
  'title': '沪深港通资金流向',
  'category': '资金流向数据',
  'category_description': '个股、行业、市场及沪深港通资金流向接口。',
  'category_sort_order': 100,
  'sort_order': 1350,
  'method': 'GET',
  'path': '/api/v1/market/tushare/moneyflow_hsgt?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/moneyflow_hsgt',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：moneyflow_hsgt\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=47\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/moneyflow_hsgt?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "moneyflow_hsgt",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "ggt_ss": "31585.48",\n'
                      '      "ggt_sz": "22957.86",\n'
                      '      "hgt": "184689.74",\n'
                      '      "north_money": "417810.63",\n'
                      '      "sgt": "233120.89",\n'
                      '      "south_money": "54543.34",\n'
                      '      "trade_date": "20260713"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=47',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'moneyflow_ind_dc',
  'title': '板块资金流向(DC)',
  'category': '资金流向数据',
  'category_description': '个股、行业、市场及沪深港通资金流向接口。',
  'category_sort_order': 100,
  'sort_order': 1360,
  'method': 'GET',
  'path': '/api/v1/market/tushare/moneyflow_ind_dc?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/moneyflow_ind_dc',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：moneyflow_ind_dc\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1022\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=344\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/moneyflow_ind_dc?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "moneyflow_ind_dc",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1022,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "buy_elg_amount": 93340720.0,\n'
                      '      "buy_elg_amount_rate": 0.44,\n'
                      '      "buy_lg_amount": 498662656.0,\n'
                      '      "buy_lg_amount_rate": 2.34,\n'
                      '      "buy_md_amount": 164706816.0,\n'
                      '      "buy_md_amount_rate": 0.77,\n'
                      '      "buy_sm_amount": -753361408.0,\n'
                      '      "buy_sm_amount_rate": -3.54,\n'
                      '      "buy_sm_amount_stock": "中国石油",\n'
                      '      "close": 5917.85,\n'
                      '      "content_type": "行业",\n'
                      '      "name": "石油石化"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1022条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=344',
  'test_status': '正常可用',
  'test_count': 1022,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'moneyflow_ind_ths',
  'title': '行业资金流向(THS)',
  'category': '资金流向数据',
  'category_description': '个股、行业、市场及沪深港通资金流向接口。',
  'category_sort_order': 100,
  'sort_order': 1370,
  'method': 'GET',
  'path': '/api/v1/market/tushare/moneyflow_ind_ths?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/moneyflow_ind_ths',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：moneyflow_ind_ths\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：90\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=343\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/moneyflow_ind_ths?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "moneyflow_ind_ths",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 90,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "close": 3046.86,\n'
                      '      "close_price": 9.0,\n'
                      '      "company_num": 68,\n'
                      '      "industry": "中药",\n'
                      '      "lead_stock": "陇神戎发",\n'
                      '      "net_amount": 6.0,\n'
                      '      "net_buy_amount": 63.0,\n'
                      '      "net_sell_amount": 56.0,\n'
                      '      "pct_change": 2.88,\n'
                      '      "pct_change_stock": 20.0,\n'
                      '      "trade_date": "20260713",\n'
                      '      "ts_code": "881141.TI"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共90条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=343',
  'test_status': '正常可用',
  'test_count': 90,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'moneyflow_mkt_dc',
  'title': '大盘资金流向(DC)',
  'category': '资金流向数据',
  'category_description': '个股、行业、市场及沪深港通资金流向接口。',
  'category_sort_order': 100,
  'sort_order': 1380,
  'method': 'GET',
  'path': '/api/v1/market/tushare/moneyflow_mkt_dc?trade_date=20260713',
  'base_path': '/api/v1/market/tushare/moneyflow_mkt_dc',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：moneyflow_mkt_dc\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：1\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=345\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'trade_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '交易日期，格式YYYYMMDD'}],
  'request_example': 'GET /api/v1/market/tushare/moneyflow_mkt_dc?trade_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "moneyflow_mkt_dc",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 1,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "buy_elg_amount": -106502647808.0,\n'
                      '      "buy_elg_amount_rate": -3.78,\n'
                      '      "buy_lg_amount": -63390658560.0,\n'
                      '      "buy_lg_amount_rate": -2.25,\n'
                      '      "buy_md_amount": 52130734080.0,\n'
                      '      "buy_md_amount_rate": 1.85,\n'
                      '      "buy_sm_amount": 117762572288.0,\n'
                      '      "buy_sm_amount_rate": 4.18,\n'
                      '      "close_sh": 3913.79,\n'
                      '      "close_sz": 14522.85,\n'
                      '      "net_amount": -169893306368.0,\n'
                      '      "net_amount_rate": -6.03\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共1条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=345',
  'test_status': '正常可用',
  'test_count': 1,
  'is_callable': True,
  'has_data': True},
 {'provider': 'tushare',
  'api_name': 'moneyflow_ths',
  'title': '个股资金流向(THS)',
  'category': '资金流向数据',
  'category_description': '个股、行业、市场及沪深港通资金流向接口。',
  'category_sort_order': 100,
  'sort_order': 1390,
  'method': 'GET',
  'path': '/api/v1/market/tushare/moneyflow_ths?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'base_path': '/api/v1/market/tushare/moneyflow_ths',
  'scope': 'tushare:points15000:read',
  'permission_label': '通用接口（15000积分权限）',
  'description': '接口英文名：moneyflow_ths\n'
                 '套餐权限：通用接口（15000积分权限）\n'
                 '最新实测状态：正常可用；数据条数：20\n'
                 '官方文档：https://tushare.pro/document/2?doc_id=348\n'
                 '参数表展示本平台最新验收使用的可运行示例；完整可选参数、字段和业务口径以官方接口文档为准。',
  'params': [{'name': 'ts_code',
              'type': 'string',
              'required': '参考官网',
              'example': '000001.SZ',
              'description': '证券/指数/ETF代码'},
             {'name': 'start_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260613',
              'description': '开始日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'},
             {'name': 'end_date',
              'type': 'string',
              'required': '参考官网',
              'example': '20260713',
              'description': '结束日期；分钟接口可使用YYYY-MM-DD HH:MM:SS'}],
  'request_example': 'GET /api/v1/market/tushare/moneyflow_ths?ts_code=000001.SZ&start_date=20260613&end_date=20260713',
  'response_example': '{\n'
                      '  "success": true,\n'
                      '  "code": 200,\n'
                      '  "provider": "tushare",\n'
                      '  "data_type": "moneyflow_ths",\n'
                      '  "source": {\n'
                      '    "provider": "tushare",\n'
                      '    "cache_hit": false\n'
                      '  },\n'
                      '  "freshness": {\n'
                      '    "requested_trade_date": null,\n'
                      '    "actual_trade_date": "20260713",\n'
                      '    "fallback_used": false,\n'
                      '    "data_freshness": "exact_request",\n'
                      '    "fallback_attempt_count": 0\n'
                      '  },\n'
                      '  "count": 20,\n'
                      '  "data": [\n'
                      '    {\n'
                      '      "buy_lg_amount": 5038.48,\n'
                      '      "buy_lg_amount_rate": 5.19,\n'
                      '      "buy_md_amount": 1682.27,\n'
                      '      "buy_md_amount_rate": 1.73,\n'
                      '      "buy_sm_amount": 4427.28,\n'
                      '      "buy_sm_amount_rate": 4.56,\n'
                      '      "latest": 10.54,\n'
                      '      "name": "平安银行",\n'
                      '      "net_amount": 11148.03,\n'
                      '      "net_d5_amount": -5699.86,\n'
                      '      "pct_change": 0.86,\n'
                      '      "trade_date": "20260713"\n'
                      '    }\n'
                      '  ],\n'
                      '  "msg": "获取成功，共20条"\n'
                      '}',
  'official_url': 'https://tushare.pro/document/2?doc_id=348',
  'test_status': '正常可用',
  'test_count': 20,
  'is_callable': True,
  'has_data': True}]
# Derived automatically so interface-count changes never require a second edit.
FULL_API_DOCS_TOTAL = len(FULL_API_DOCS)
