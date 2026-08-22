# -*- coding: utf-8 -*-
"""Generate production-safe values without writing plaintext secrets to disk."""
from __future__ import annotations

import argparse
import getpass
import os
import secrets

from services.security_credentials import hash_secret


def _read_admin_password(env_name: str) -> str:
    value = str(os.getenv(env_name, "") or "")
    if value:
        return value
    first = getpass.getpass("请输入管理员高强度密码（不会显示）：")
    second = getpass.getpass("请再次输入管理员密码：")
    if first != second:
        raise ValueError("两次输入的管理员密码不一致")
    return first


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate stock-server production secrets")
    parser.add_argument(
        "--admin-password-env",
        default="ADMIN_BOOTSTRAP_PASSWORD",
        help="可选：从指定环境变量读取管理员密码；默认交互式安全输入",
    )
    args = parser.parse_args()
    try:
        admin_password = _read_admin_password(args.admin_password_env)
    except ValueError as exc:
        parser.error(str(exc))
    if len(admin_password) < 16:
        parser.error("管理员密码至少16位")
    print(f"SECRET_KEY={secrets.token_urlsafe(48)}")
    print(f"ADMIN_PASSWORD_HASH={hash_secret(admin_password)}")
    print(f"ADMIN_CLIENT_CERT_PROXY_SECRET={secrets.token_urlsafe(48)}")
    print(f"API_TOKEN_HASH_SECRET={secrets.token_urlsafe(48)}")
    print(f"AUDIT_TOKEN_HMAC_SECRET={secrets.token_urlsafe(48)}")
    print(f"CONTACT_VERIFICATION_HMAC_SECRET={secrets.token_urlsafe(48)}")
    print(f"SMS_VERIFY_WEBHOOK_SECRET={secrets.token_urlsafe(48)}")
    print("\n请将代理共享密钥同时配置到.env和管理员反向代理站点；不要提交到Git或聊天记录。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
