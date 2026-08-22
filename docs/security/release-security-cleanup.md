# 发布包安全清理说明

本补丁 ZIP 只包含需要替换的源码、测试和文档，不包含真实凭据或运行数据。

制作完整源码发布包时必须排除：

- `.env`、`.env_before_https` 和任何真实 Token/密码文件；
- `data/*.db`、SQLite WAL/SHM 文件；
- `logs/` 下的运行日志；
- `.venv/`、`venv/`、`.idea/`；
- `__pycache__/`、`.pytest_cache/`、`*.pyc`；
- 临时导出 CSV、真实上游 payload 和调试抓包。

注意：生产服务器运行所需的 `.env` 和数据库不能被清理脚本自动删除。应只从“对外分发的 ZIP/源码副本”中排除，并在服务器上通过安全方式保留。此前已经进入共享 ZIP 的 Token 应进行轮换。

以下文件没有当前运行引用，可从源码发布副本中人工移除，但不要由补丁自动删除：

- `app_before_https.py`；
- `.env_before_https`；
- `integrations/market_data/miniqmt/subscription_manager.py`（仅在确认近期不启用 MiniQMT 实时订阅时）；
- 历史补丁说明、重复文件树和旧测试报告。
