# -*- coding: utf-8 -*-
"""Generate or verify a standalone administrator TOTP setup key."""
from __future__ import annotations

import argparse
import base64
import secrets
from urllib.parse import quote

from services.security_credentials import verify_totp


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an administrator authenticator setup key")
    parser.add_argument("--account", default="admin", help="Authenticator account label")
    parser.add_argument("--issuer", default="StockData", help="Authenticator issuer label")
    parser.add_argument("--secret", default="", help="Reuse an existing Base32 secret")
    parser.add_argument("--verify-code", default="", help="Verify a current six-digit code")
    args = parser.parse_args()

    secret = str(args.secret or "").strip().replace(" ", "").upper()
    if not secret:
        secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    if args.verify_code:
        ok = verify_totp(secret, args.verify_code)
        print("PASS: 动态验证码正确" if ok else "FAIL: 动态验证码错误或服务器时间不同步")
        return 0 if ok else 1

    issuer = str(args.issuer or "StockData").strip()
    account = str(args.account or "admin").strip()
    uri = (
        f"otpauth://totp/{quote(issuer)}:{quote(account)}"
        f"?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    )
    print(f"ADMIN_TOTP_SECRET={secret}")
    print(f"OTPAUTH_URI={uri}")
    print("\n操作：在Google/Microsoft Authenticator中选择“输入设置密钥”，录入上面的Secret；")
    print("然后将ADMIN_TOTP_SECRET写入服务器.env，并设置ADMIN_REQUIRE_MFA=True，重启服务。")
    print("页面不会生成或显示动态验证码，验证码每30秒由验证器应用生成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
