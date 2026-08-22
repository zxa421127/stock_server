from tools.interface_tester import InterfaceTester, test_refs, save_results, print_summary
from auto_tests.common import BASE_URL, load_tokens


def main() -> int:
    tokens = load_tokens()
    tester = InterfaceTester(BASE_URL, tokens["special"])
    providers = tester.providers()
    refs = []
    for provider in providers:
        refs.extend((provider, str(row.get("api_name"))) for row in tester.catalog(provider) if row.get("api_name"))
    print(f"将使用特殊权限套餐测试 {len(refs)} 个真实接口，会消耗上游额度。")
    if input("确认继续请输入 YES：").strip() != "YES":
        print("已取消，不算失败。")
        return 0
    results = test_refs(tester, refs, interval=0.1)
    print_summary(results)
    # Only local/auth/server failures make the command fail; upstream permission/no-data is reported separately.
    bad = {"Token无效", "未开通套餐", "套餐无权限", "服务器异常", "网络错误"}
    return 1 if any(r.verdict in bad for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
