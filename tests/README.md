# tests 定位

`tests/` 只存放可重复自动运行的单元测试、内部集成测试、安全回归和测试夹具。默认不得访问真实TuShare、飞书、开盘啦、生产Redis或生产数据库。

- `fixtures/` 是输入样例，例如TuShare官方Markdown；这些 `.md` 是测试数据，不是普通项目文档。
- 真实部署验收放在 `e2e_tests/`。
- 必须人工确认或可能改变第三方数据的脚本放在 `scripts/manual_tests/`。

推荐标记：`unit`、`integration`、`security`、`network`、`slow`。CI默认执行不含 `network` 的测试。
