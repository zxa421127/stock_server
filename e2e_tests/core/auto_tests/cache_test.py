from auto_tests.common import Result, load_tokens, message, request, save_report


def main() -> int:
    results = []
    try:
        tokens = load_tokens()
        status, payload, _ = request("/api/v1/market/cache/clear", tokens["admin"], "POST")
        results.append(Result("cache", "管理员清空缓存", status == 200, "HTTP 200", f"HTTP {status}", message(payload)))
        body = {"ts_code":"000001.SZ", "start_date":"20260101", "end_date":"20260201"}
        s1, p1, _ = request("/api/v1/market/tushare/daily", tokens["general"], "POST", body)
        if s1 != 200:
            results.append(Result("cache", "缓存前置数据请求", False, "HTTP 200", f"HTTP {s1}",
                                  "上游未成功，无法判断缓存；" + message(p1)))
        else:
            hit1 = bool((p1.get("source") or {}).get("cache_hit"))
            s2, p2, _ = request("/api/v1/market/tushare/daily", tokens["general"], "POST", body)
            hit2 = bool((p2.get("source") or {}).get("cache_hit"))
            results.append(Result("cache", "第一次请求未命中", not hit1, "cache_hit=false", str(hit1)))
            results.append(Result("cache", "第二次请求命中", s2 == 200 and hit2, "HTTP 200且cache_hit=true", f"HTTP {s2}, {hit2}"))
    except Exception as exc:
        results.append(Result("cache", "缓存测试执行", False, "脚本正常完成", "异常", str(exc)))
    save_report("05_缓存测试", results)
    return 0 if all(x.passed for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
