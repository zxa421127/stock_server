from auto_tests.common import Result, compact_json, data_evidence, load_tokens, message, request, save_report

CASES = [
    ("未带Token", None, "/api/v1/market/tushare/catalog", 401),
    ("无效Token", "__invalid__", "/api/v1/market/tushare/catalog", 401),
    ("无套餐账户", "unsubscribed", "/api/v1/market/tushare/catalog", 402),
    ("过期套餐", "expired", "/api/v1/market/tushare/catalog", 402),
    ("禁用Token", "disabled", "/api/v1/market/tushare/catalog", 401),
    ("通用套餐-Tushare目录", "general", "/api/v1/market/tushare/catalog", 200),
    ("通用套餐-开盘啦目录", "general", "/api/v1/market/kaipanla/catalog", 403),
    ("通用套餐-MiniQMT目录", "general", "/api/v1/market/miniqmt/catalog", 403),
    ("通用套餐-Tushare单独权限", "general", "/api/v1/market/tushare/rt_k", 403),
    ("通用套餐-缓存管理", "general", "/api/v1/market/cache/stats", 403),
    ("特殊套餐-Tushare目录", "special", "/api/v1/market/tushare/catalog", 200),
    ("特殊套餐-开盘啦目录", "special", "/api/v1/market/kaipanla/catalog", 200),
    ("特殊套餐-缓存管理", "special", "/api/v1/market/cache/stats", 403),
    ("管理员-Tushare目录", "admin", "/api/v1/market/tushare/catalog", 200),
    ("管理员-开盘啦目录", "admin", "/api/v1/market/kaipanla/catalog", 200),
    ("管理员-缓存管理", "admin", "/api/v1/market/cache/stats", 200),
]


def main() -> int:
    results = []
    try:
        tokens = load_tokens()
        for name, role, path, expected in CASES:
            token = "" if role is None else ("invalid-token-for-test" if role == "__invalid__" else tokens[role])
            status, payload, ms = request(path, token)
            count, sample = data_evidence(payload)
            results.append(Result(
                "permission",
                name,
                status == expected,
                f"HTTP {expected}",
                f"HTTP {status}",
                f"消息={message(payload)}；数据条数={count}；返回证据={compact_json(sample)}；{ms}ms",
            ))

        # 正向数据测试：权限放行还不够，必须真正取得非空数据并保存前3条。
        samples = [
            ("通用套餐-股票积分接口", "general", "/api/v1/market/tushare/daily", {"ts_code":"000001.SZ","start_date":"20260101","end_date":"20260201"}),
            ("通用套餐-ETF积分接口", "general", "/api/v1/market/tushare/fund_daily", {"ts_code":"510300.SH","start_date":"20260101","end_date":"20260201"}),
            ("通用套餐-指数积分接口", "general", "/api/v1/market/tushare/index_daily", {"ts_code":"000001.SH","start_date":"20260101","end_date":"20260201"}),
            ("特殊套餐-Tushare单独权限", "special", "/api/v1/market/tushare/rt_k", {"ts_code":"000001.SZ"}),
            ("特殊套餐-开盘啦权限", "special", "/api/v1/market/kaipanla/morning_bidding", {"st":1}),
        ]
        for name, role, path, body in samples:
            status, payload, ms = request(path, tokens[role], "POST", body)
            count, sample = data_evidence(payload)
            base_ok = status == 200 and isinstance(payload, dict) and payload.get("success") is True

            # rt_k 是交易时段实时接口。周末、节假日和非交易时段可能正常返回空数据。
            # 权限矩阵只验证特殊套餐是否有权调用；实时数据非空由全接口测试验证。
            is_realtime_quote = path.endswith("/rt_k")
            ok = base_ok if is_realtime_quote else (base_ok and count > 0)
            expected = (
                "HTTP 200、success=true（非交易时段允许data为空）"
                if is_realtime_quote
                else "HTTP 200、success=true、data非空"
            )

            results.append(Result(
                "permission-data",
                name,
                ok,
                expected,
                f"HTTP {status}，数据条数={count}",
                f"请求参数={compact_json(body)}；前3条具体数据={compact_json(sample)}；消息={message(payload)}；{ms}ms",
            ))
    except Exception as exc:
        results.append(Result("permission", "权限矩阵执行", False, "脚本正常完成", "异常", str(exc)))
    save_report("03_权限矩阵测试", results)
    return 0 if all(x.passed for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
