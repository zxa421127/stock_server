# -*- coding: utf-8 -*-
"""Issue, inspect, list, and revoke project-managed administrator mTLS certificates."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import getpass
import json
import os
from pathlib import Path
import re
import stat

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from services.admin_client_certificate import (
    list_certificates,
    register_certificate,
    revoke_certificate,
)

CA_KEY_NAME = "admin-client-ca.key.pem"
CA_CERT_NAME = "admin-client-ca.crt.pem"


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _secure_file(path: Path) -> None:
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _safe_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip("-.")
    return text or "device"


def initialize_ca(
    output_dir: Path,
    *,
    password: str,
    common_name: str = "StockData Administrator Client CA",
    valid_days: int = 3650,
) -> dict:
    if len(password) < 16:
        raise ValueError("CA私钥密码至少16位")
    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    key_path = directory / CA_KEY_NAME
    cert_path = directory / CA_CERT_NAME
    if key_path.exists() or cert_path.exists():
        raise FileExistsError("CA文件已存在；拒绝覆盖，请先安全备份或使用新目录")

    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "StockData"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=max(365, int(valid_days))))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(password.encode("utf-8")),
        )
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    _secure_file(key_path)
    return {
        "private_key_path": str(key_path),
        "certificate_path": str(cert_path),
        "serial_number": format(certificate.serial_number, "X"),
        "fingerprint_sha256": certificate.fingerprint(hashes.SHA256()).hex().upper(),
        "not_after": _utc_text(certificate.not_valid_after_utc),
    }


def _load_ca(ca_dir: Path, password: str):
    directory = Path(ca_dir).resolve()
    key_path = directory / CA_KEY_NAME
    cert_path = directory / CA_CERT_NAME
    if not key_path.is_file() or not cert_path.is_file():
        raise FileNotFoundError(f"CA文件不存在：{directory}")
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=password.encode("utf-8"))
    certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
    return key, certificate


def issue_certificate(
    *,
    ca_dir: Path,
    ca_password: str,
    output_dir: Path,
    pfx_password: str,
    admin_username: str,
    device_name: str,
    valid_days: int = 825,
    conn=None,
) -> dict:
    if len(pfx_password) < 12:
        raise ValueError("PFX安装密码至少12位")
    ca_key, ca_certificate = _load_ca(Path(ca_dir), ca_password)
    now = datetime.now(timezone.utc)
    not_after = min(
        now + timedelta(days=max(30, int(valid_days))),
        ca_certificate.not_valid_after_utc - timedelta(days=1),
    )
    if not_after <= now + timedelta(days=1):
        raise ValueError("CA证书即将过期，不能继续签发客户端证书")

    client_key = ec.generate_private_key(ec.SECP256R1())
    common_name = f"{admin_username}@{device_name}"
    subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "StockData"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Administrator Client"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_certificate.subject)
        .public_key(client_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(client_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    basename = f"{_safe_name(admin_username)}-{_safe_name(device_name)}"
    pfx_path = directory / f"{basename}.p12"
    cert_path = directory / f"{basename}.crt.pem"
    if pfx_path.exists() or cert_path.exists():
        raise FileExistsError("目标证书文件已存在；请更换设备名称或输出目录")

    pfx_path.write_bytes(
        pkcs12.serialize_key_and_certificates(
            basename.encode("utf-8"),
            client_key,
            certificate,
            [ca_certificate],
            serialization.BestAvailableEncryption(pfx_password.encode("utf-8")),
        )
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    _secure_file(pfx_path)

    fingerprint = certificate.fingerprint(hashes.SHA256()).hex().upper()
    serial = format(certificate.serial_number, "X")
    registered = register_certificate(
        admin_username=admin_username,
        device_name=device_name,
        serial_number=serial,
        fingerprint_sha256=fingerprint,
        subject_dn=certificate.subject.rfc4514_string(),
        not_before=_utc_text(certificate.not_valid_before_utc),
        not_after=_utc_text(certificate.not_valid_after_utc),
        metadata={"issuer": certificate.issuer.rfc4514_string(), "algorithm": "ECDSA-P256-SHA256"},
        conn=conn,
    )
    return {
        "pfx_path": str(pfx_path),
        "certificate_path": str(cert_path),
        "ca_certificate_path": str(Path(ca_dir).resolve() / CA_CERT_NAME),
        "serial_number": serial,
        "fingerprint_sha256": fingerprint,
        "not_before": registered.get("not_before"),
        "not_after": registered.get("not_after"),
        "database_id": registered.get("id"),
    }


def inspect_pfx(path: Path, *, password: str) -> dict:
    key, certificate, chain = pkcs12.load_key_and_certificates(
        Path(path).read_bytes(), password.encode("utf-8")
    )
    if key is None or certificate is None:
        raise ValueError("PFX中没有完整客户端私钥和证书")
    return {
        "subject": certificate.subject.rfc4514_string(),
        "issuer": certificate.issuer.rfc4514_string(),
        "serial_number": format(certificate.serial_number, "X"),
        "fingerprint_sha256": certificate.fingerprint(hashes.SHA256()).hex().upper(),
        "not_before": _utc_text(certificate.not_valid_before_utc),
        "not_after": _utc_text(certificate.not_valid_after_utc),
        "chain_length": len(chain or []),
    }


def _read_password(env_name: str, prompt: str) -> str:
    value = str(os.getenv(env_name, "") or "")
    return value if value else getpass.getpass(prompt)


def _read_new_password(
    env_name: str,
    prompt: str,
    confirm_prompt: str,
) -> str:
    """Read a newly created password twice and require an exact match.

    Environment-variable passwords keep the existing non-interactive behavior
    so automated deployment/test flows are not broken.
    """
    value = str(os.getenv(env_name, "") or "")
    if value:
        return value

    password = getpass.getpass(prompt)
    confirm_password = getpass.getpass(confirm_prompt)

    if password != confirm_password:
        raise SystemExit("两次输入的密码不一致，已取消操作。")

    return password


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage StockData administrator client certificates")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-ca", help="Create the private administrator client CA")
    init.add_argument("--output-dir", default="security/admin-client-ca")
    init.add_argument("--common-name", default="StockData Administrator Client CA")
    init.add_argument("--valid-days", type=int, default=3650)
    init.add_argument("--password-env", default="ADMIN_CA_PASSWORD")

    issue = sub.add_parser("issue", help="Issue and register one administrator device certificate")
    issue.add_argument("--ca-dir", default="security/admin-client-ca")
    issue.add_argument("--output-dir", default="security/admin-client-certificates")
    issue.add_argument("--admin", default="admin")
    issue.add_argument("--device", required=True)
    issue.add_argument("--valid-days", type=int, default=825)
    issue.add_argument("--ca-password-env", default="ADMIN_CA_PASSWORD")
    issue.add_argument("--pfx-password-env", default="ADMIN_PFX_PASSWORD")

    sub.add_parser("list", help="List registered administrator certificates")

    revoke = sub.add_parser("revoke", help="Revoke a registered certificate")
    group = revoke.add_mutually_exclusive_group(required=True)
    group.add_argument("--fingerprint")
    group.add_argument("--serial")
    revoke.add_argument("--reason", default="manual revoke")

    inspect = sub.add_parser("inspect-pfx", help="Inspect an exported PKCS#12/PFX file")
    inspect.add_argument("path")
    inspect.add_argument("--password-env", default="ADMIN_PFX_PASSWORD")

    args = parser.parse_args()
    if args.command == "init-ca":
        password = _read_new_password(
            args.password_env,
            "请输入CA私钥密码：",
            "请再次输入CA私钥密码：",
        )
        result = initialize_ca(Path(args.output_dir), password=password, common_name=args.common_name, valid_days=args.valid_days)
    elif args.command == "issue":
        ca_password = _read_password(args.ca_password_env, "请输入CA私钥密码：")
        pfx_password = _read_new_password(
            args.pfx_password_env,
            "请输入新PFX安装密码：",
            "请再次输入新PFX安装密码：",
        )
        result = issue_certificate(
            ca_dir=Path(args.ca_dir), ca_password=ca_password,
            output_dir=Path(args.output_dir), pfx_password=pfx_password,
            admin_username=args.admin, device_name=args.device, valid_days=args.valid_days,
        )
    elif args.command == "list":
        result = {"items": list_certificates()}
    elif args.command == "revoke":
        result = {
            "revoked": revoke_certificate(
                fingerprint=args.fingerprint, serial_number=args.serial, reason=args.reason
            )
        }
    else:
        password = _read_password(args.password_env, "请输入PFX密码：")
        result = inspect_pfx(Path(args.path), password=password)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("revoked", True) is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
