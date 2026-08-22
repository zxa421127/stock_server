# -*- coding: utf-8 -*-
"""Delivery adapters for registration verification codes."""
from __future__ import annotations

from email.message import EmailMessage
import hashlib
import hmac
import json
import smtplib
import time
from urllib.parse import urlparse

import requests

import config


def send_email_code(address: str, code: str) -> None:
    host = str(getattr(config, "SMTP_HOST", "") or "").strip()
    sender = str(getattr(config, "SMTP_FROM_ADDRESS", "") or "").strip()
    if not host or not sender:
        raise RuntimeError("邮箱验证码服务未配置")
    port = int(getattr(config, "SMTP_PORT", 587))
    timeout = int(getattr(config, "SMTP_TIMEOUT_SECONDS", 10))
    username = str(getattr(config, "SMTP_USERNAME", "") or "")
    password = str(getattr(config, "SMTP_PASSWORD", "") or "")
    use_ssl = bool(getattr(config, "SMTP_USE_SSL", False))
    use_tls = bool(getattr(config, "SMTP_USE_TLS", True)) and not use_ssl

    message = EmailMessage()
    message["Subject"] = "股票数据平台注册验证码"
    message["From"] = sender
    message["To"] = address
    ttl_minutes = max(1, int(getattr(config, "CONTACT_CODE_TTL_SECONDS", 300)) // 60)
    message.set_content(
        f"你的注册验证码是：{code}\n\n验证码在 {ttl_minutes} 分钟内有效，请勿转发给他人。"
    )

    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_cls(host, port, timeout=timeout) as client:
        if use_tls:
            client.ehlo()
            client.starttls()
            client.ehlo()
        if username:
            client.login(username, password)
        client.send_message(message)


def send_sms_code(phone: str, code: str) -> None:
    url = str(getattr(config, "SMS_VERIFY_WEBHOOK_URL", "") or "").strip()
    secret = str(getattr(config, "SMS_VERIFY_WEBHOOK_SECRET", "") or "")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("短信验证码Webhook必须配置为HTTPS地址")
    if len(secret) < 16:
        raise RuntimeError("短信验证码Webhook密钥未配置或过短")
    payload = {"phone": phone, "code": code, "purpose": "registration"}
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    response = requests.post(
        url,
        json=payload,
        headers={
            "X-Stock-Timestamp": timestamp,
            "X-Stock-Signature": signature,
            "Content-Type": "application/json",
        },
        timeout=int(getattr(config, "SMS_VERIFY_TIMEOUT_SECONDS", 10)),
        allow_redirects=False,
    )
    response.raise_for_status()
