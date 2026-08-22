# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3

import pytest

import db_utils
from integrations.feishu.bitable import FeishuBitableManager
from services.member_service import (
    apply_subscription_action,
    create_or_get_user,
    get_or_create_api_key,
)
import services.feishu_sync_service as sync_service


class FakeBitable:
    def __init__(self, records=None):
        self.records = list(records or [])
        self.updated_records: list[tuple[str, dict]] = []
        self.upsert_calls: list[tuple[tuple, dict]] = []

    def list_all_records(self):
        return list(self.records)

    def update_record(self, record_id: str, fields: dict, *args, **kwargs):
        self.updated_records.append((record_id, dict(fields)))
        return True

    def upsert_member_record(self, *args, **kwargs):
        self.upsert_calls.append((args, kwargs))
        return "updated"

    @staticmethod
    def _str_to_ms(_value):
        return 123456789


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    old_db = db_utils.DB_FILE
    old_conn = getattr(db_utils._local, "conn", None)
    if old_conn is not None:
        old_conn.close()
    db_utils._local.conn = None
    db_utils._db_pragmas_initialized = False
    monkeypatch.setattr(db_utils, "DB_FILE", str(tmp_path / "test.db"))
    db_utils.init_db()
    monkeypatch.setattr(sync_service, "_feishu_config_ready", lambda: True)
    yield
    conn = getattr(db_utils._local, "conn", None)
    if conn is not None:
        conn.close()
    db_utils._local.conn = None
    db_utils._db_pragmas_initialized = False
    db_utils.DB_FILE = old_db


def _read_one(sql: str, params=()):
    conn = db_utils.get_conn()
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _read_all(sql: str, params=()):
    conn = db_utils.get_conn()
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def test_member_publish_clears_token_and_returns_fields_only():
    row = {
        "user_id": 7,
        "username": "member",
        "phone": "13800000000",
        "email": "member@example.com",
        "taobao_nick": "shop-user",
        "token": "SK_STOCK_API_TOP_SECRET",
        "key_status": "active",
        "user_status": "active",
        "plan_code": "general_month",
        "plan_type": "general",
        "subscription_status": "active",
        "start_time": "2026-07-01 00:00:00",
        "expire_time": "2026-08-01 00:00:00",
        "token_create_time": "2026-07-01 00:00:00",
    }

    fields = sync_service._build_feishu_member_fields(row, FakeBitable())

    assert isinstance(fields, dict)
    assert fields["用户ID"] == "7"
    assert fields["授权码"] == ""
    assert "SK_STOCK_API_TOP_SECRET" not in repr(fields)


def test_member_upsert_uses_user_id_only_and_never_token_lookup(monkeypatch):
    manager = object.__new__(FeishuBitableManager)
    calls = []
    monkeypatch.setattr(manager, "find_record_by_user_id", lambda user_id: ("rec-7", {"用户ID": str(user_id)}))
    monkeypatch.setattr(
        manager,
        "find_record_by_token",
        lambda _token: pytest.fail("Token lookup must not be used for member upsert"),
    )
    monkeypatch.setattr(manager, "update_record", lambda record_id, fields: calls.append((record_id, fields)) or True)
    monkeypatch.setattr(manager, "add_record", lambda fields: pytest.fail("existing user ID should update"))

    result = manager.upsert_member_record({"用户ID": "7", "授权码": ""}, user_id=7)

    assert result == "updated"
    assert calls == [("rec-7", {"用户ID": "7", "授权码": ""})]


def test_reverse_import_does_not_modify_existing_user_token_or_subscription(isolated_db, monkeypatch):
    user = create_or_get_user(username="local-name", phone="13800000001", email="local@example.com")
    user_id = int(user["id"])
    local_token = get_or_create_api_key(user_id)
    apply_subscription_action(user_id, "general_month", "open")

    fake = FakeBitable([
        (
            "rec-existing",
            {
                "用户ID": str(user_id),
                "授权码": "SK_STOCK_API_ATTACKER_CONTROLLED",
                "用户名称": "remote-name",
                "手机号": "13999999999",
                "邮箱": "remote@example.com",
                "淘宝昵称": "remote-shop",
                "状态": "已禁用",
                "用户状态": "disabled",
                "Token状态": "disabled",
                "套餐代码": "special_year",
                "开始授权时间": "2026-01-01 00:00:00",
                "授权截止时间": "2126-01-01 00:00:00",
                "备注": "remote remark",
            },
        )
    ])
    monkeypatch.setattr(sync_service, "get_bitable_manager", lambda: fake)

    added, linked = sync_service.sync_feishu_to_local()

    assert (added, linked) == (0, 1)
    assert _read_one("SELECT username,phone,email,taobao_nick,status FROM users WHERE id=?", (user_id,)) == {
        "username": "local-name",
        "phone": "13800000001",
        "email": "local@example.com",
        "taobao_nick": None,
        "status": "active",
    }
    keys = _read_all("SELECT token,token_hash,status FROM api_keys WHERE user_id=? ORDER BY id", (user_id,))
    assert len(keys) == 1
    assert keys[0]["token"].startswith("hashed:")
    assert local_token not in keys[0]["token"]
    assert len(keys[0]["token_hash"]) == 64
    assert keys[0]["status"] == "active"
    subscriptions = _read_all(
        "SELECT plan_code,status,operation_type FROM subscriptions WHERE user_id=? ORDER BY id",
        (user_id,),
    )
    assert subscriptions == [{"plan_code": "general_month", "status": "active", "operation_type": "open"}]
    assert fake.updated_records and fake.updated_records[0][0] == "rec-existing"
    assert fake.updated_records[0][1]["用户名称"] == "local-name"
    assert fake.updated_records[0][1]["授权码"] == ""


def test_reverse_import_creates_disabled_review_user_without_token(isolated_db, monkeypatch):
    fake = FakeBitable([
        (
            "rec-new",
            {
                "用户名称": "new-from-feishu",
                "手机号": "13800000002",
                "邮箱": "new@example.com",
                "淘宝昵称": "new-shop",
                "授权码": "SK_STOCK_API_MUST_NOT_IMPORT",
                "状态": "已禁用",
                "套餐代码": "special_year",
                "开始授权时间": "2026-01-01 00:00:00",
                "授权截止时间": "2126-01-01 00:00:00",
            },
        )
    ])
    monkeypatch.setattr(sync_service, "get_bitable_manager", lambda: fake)

    added, linked = sync_service.sync_feishu_to_local()

    assert (added, linked) == (1, 0)
    user = _read_one("SELECT id,username,phone,email,taobao_nick,register_source,status FROM users WHERE phone=?", ("13800000002",))
    assert user is not None
    assert user["username"] == "new-from-feishu"
    assert user["register_source"] == "feishu_pending"
    assert user["status"] == "disabled"
    keys = _read_all("SELECT token,status FROM api_keys WHERE user_id=?", (user["id"],))
    assert keys == []
    assert _read_all("SELECT id FROM subscriptions WHERE user_id=?", (user["id"],)) == []
    assert fake.updated_records and fake.updated_records[0][0] == "rec-new"
    assert fake.updated_records[0][1]["用户ID"] == str(user["id"])
    assert fake.updated_records[0][1]["套餐代码"] == ""
    assert fake.updated_records[0][1]["授权码"] == ""


def test_reverse_import_links_unique_contact_without_overwriting(isolated_db, monkeypatch):
    user = create_or_get_user(username="canonical", phone="13800000003")
    user_id = int(user["id"])
    get_or_create_api_key(user_id)
    fake = FakeBitable([
        (
            "rec-link",
            {
                "用户名称": "wrong-remote-name",
                "手机号": "13800000003",
                "状态": "已禁用",
                "套餐代码": "special_year",
            },
        )
    ])
    monkeypatch.setattr(sync_service, "get_bitable_manager", lambda: fake)

    assert sync_service.sync_feishu_to_local() == (0, 1)
    assert _read_one("SELECT username,status FROM users WHERE id=?", (user_id,)) == {
        "username": "canonical",
        "status": "active",
    }
    assert fake.updated_records[0][1]["用户ID"] == str(user_id)
    assert fake.updated_records[0][1]["用户名称"] == "canonical"


def test_reverse_import_skips_ambiguous_contact_match(isolated_db, monkeypatch):
    conn = db_utils.get_conn()
    now = "2026-07-21 08:00:00"
    conn.execute(
        "INSERT INTO users (username,phone,register_source,status,created_at,updated_at) VALUES (?,?,?,?,?,?)",
        ("dup-a", "13800000004", "admin", "active", now, now),
    )
    conn.execute(
        "INSERT INTO users (username,phone,register_source,status,created_at,updated_at) VALUES (?,?,?,?,?,?)",
        ("dup-b", "13800000004", "admin", "active", now, now),
    )
    conn.commit()
    fake = FakeBitable([("rec-ambiguous", {"用户名称": "new", "手机号": "13800000004"})])
    monkeypatch.setattr(sync_service, "get_bitable_manager", lambda: fake)

    assert sync_service.sync_feishu_to_local() == (0, 0)
    assert len(_read_all("SELECT id FROM users WHERE phone=?", ("13800000004",))) == 2
    assert fake.updated_records == []


def test_periodic_full_sync_is_publish_only(monkeypatch):
    calls = []
    monkeypatch.setattr(sync_service, "sync_feishu_to_local", lambda: calls.append("reverse"))
    monkeypatch.setattr(sync_service, "sync_local_to_feishu", lambda: calls.append("publish"))
    monkeypatch.setattr(sync_service, "_check_and_sync_bidding", lambda: calls.append("bidding"))

    sync_service.run_full_sync()

    assert calls == ["publish", "bidding"]
