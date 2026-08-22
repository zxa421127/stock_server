# 项目目录与职责

## 运行代码

- `routes/`：HTTP入口，只负责参数接收、权限检查、调用服务和组织响应。
- `services/`：业务逻辑、缓存、限流、审计、规格同步和后台任务。
- `integrations/`：TuShare、开盘啦、飞书、MiniQMT等外部系统适配器。
- `middleware/`：请求级中间件。
- `utils/`：无业务状态的通用工具。
- `templates/`：HTML模板。
- `interface_specs/`：当前生效、候选和历史接口规格版本。
- `tools/`：迁移、诊断、发布、安全扫描和独立Worker入口。
- `deploy/`：Nginx、systemd等生产部署样例。

## 测试

- `tests/`：单元测试、内部集成测试、安全回归和测试夹具；默认不能访问真实外部服务。
- `e2e_tests/`：连接已经部署的服务器进行端到端验收，需要测试Token和网络。
- `scripts/manual_tests/`：只能人工执行、可能访问真实TuShare或飞书的诊断脚本。

## 文档

见 `docs/README.md`。根README和局部README有意放在所属目录，测试用Markdown有意放在fixtures中。

## 接口元数据边界

`interface_specs/current.json` 指向的正式规格是测试台和官方规格校核的权威来源。`services/api_doc_catalog.py` 暂时保留为旧API文档页面的兼容数据源，不允许再从响应样例写回正式规格；后续应通过生成器逐步移除该兼容层，而不是手工维护第二套字段定义。
