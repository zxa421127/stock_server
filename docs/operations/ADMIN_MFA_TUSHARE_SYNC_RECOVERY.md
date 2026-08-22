# 已废弃：管理员TOTP恢复说明

本文件记录的是旧版TOTP方案。当前生产后台改用：管理员密码 + 图形验证码 + 项目自签发mTLS客户端证书。

请阅读：

- `docs/security/admin-client-certificate.md`
- `docs/operations/zero-to-one-production-installation.md`

旧的 `tools/security/generate_admin_totp.py` 仅保留回滚兼容，不应作为新部署步骤。
