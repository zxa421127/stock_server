# 文档目录

项目文档按用途分层，避免正式运维说明、开发设计和历史补丁混放。

- `architecture/`：当前有效的架构、目录和组件边界。
- `operations/`：生产部署、迁移、备份、监控、压测和故障处理。
- `security/`：生产安全基线、密钥轮换和事件响应。
- `features/`：仍在使用的业务功能说明。
- `archive/`：历史设计、旧补丁、旧测试报告，只用于追溯，不作为生产操作依据。
- `CHANGELOG.md`：版本变化摘要。

根目录 `README.md` 是项目入口；`interface_specs/README.md` 是接口规格子系统的就地说明；`tests/fixtures/**/*.md` 是自动化测试夹具，不属于普通文档，不能移动到本目录。

生产安装与管理员证书：

- `operations/zero-to-one-production-installation.md`
- `security/admin-client-certificate.md`

- `operations/windows-production-installation.md`：Windows轻量服务器生产部署。
