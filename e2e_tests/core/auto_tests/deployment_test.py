from auto_tests.common import Result, BASE_URL, request, save_report, message


def main() -> int:
    results = []
    try:
        status, payload, ms = request("/ping")
        raw = payload.get("raw", "") if isinstance(payload, dict) else ""
        results.append(Result("deployment", "服务存活", status == 200 and raw == "pong",
                              "HTTP 200且响应体严格等于pong", f"HTTP {status} body={raw!r}", f"{ms}ms"))
        status, payload, ms = request("/")
        ok = status == 200 and isinstance(payload, dict) and payload.get("success") is True
        results.append(Result("deployment", "服务首页", ok, "HTTP 200且success=true",
                              f"HTTP {status}", f"{message(payload)} {ms}ms"))
        status, payload, _ = request("/api/v1/market/tushare/catalog")
        results.append(Result("deployment", "无Token保护", status == 401, "HTTP 401", f"HTTP {status}", message(payload)))
        status, payload, _ = request("/api/v1/market/tushare/catalog", "invalid-token-for-test")
        results.append(Result("deployment", "错误Token保护", status == 401, "HTTP 401", f"HTTP {status}", message(payload)))
    except Exception as exc:
        results.append(Result("deployment", "连接服务", False, f"能连接{BASE_URL}", "连接失败", str(exc)))
    save_report("01_部署基础测试", results)
    return 0 if all(x.passed for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
