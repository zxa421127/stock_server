from __future__ import annotations

import sqlite3

import config
import db_utils
from services import member_service


def _use_database(monkeypatch, path):
    db_utils.close_thread_connection()
    monkeypatch.setattr(db_utils, "DB_FILE", str(path))
    monkeypatch.setattr(db_utils, "API_TOKEN_HASH_SECRET", "T" * 48)
    monkeypatch.setattr(config, "API_TOKEN_HASH_SECRET", "T" * 48)
    monkeypatch.setattr(config, "APP_ENV", "test")
    db_utils._db_pragmas_initialized = False


def test_legacy_plaintext_api_token_is_hashed_and_still_authenticates(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            phone TEXT UNIQUE,
            email TEXT UNIQUE,
            taobao_nick TEXT UNIQUE,
            password_hash TEXT,
            register_source TEXT DEFAULT 'admin',
            status TEXT DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT,
            last_login_at TEXT
        );
        CREATE TABLE api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            last_used_at TEXT
        );
        """
    )
    token = "SK_STOCK_API_20260725000000_LEGACYTOKEN1234567890"
    conn.execute("INSERT INTO users(id,username,status) VALUES (1,'alice','active')")
    conn.execute("INSERT INTO api_keys(user_id,token,status) VALUES (1,?,'active')", (token,))
    conn.commit()
    conn.close()

    _use_database(monkeypatch, db_path)
    db_utils.init_db()

    row = db_utils.get_conn().execute(
        "SELECT token,token_hash,token_prefix,token_last4 FROM api_keys WHERE user_id=1"
    ).fetchone()
    assert row["token"].startswith("hashed:")
    assert token not in row["token"]
    assert len(row["token_hash"]) == 64
    assert row["token_prefix"] == token[:20]
    assert row["token_last4"] == token[-4:]
    auth = db_utils.get_api_key_auth_record(token)
    assert auth and auth["username"] == "alice"


def test_rotated_api_token_invalidates_old_token_and_stores_no_plaintext(tmp_path, monkeypatch):
    db_path = tmp_path / "new.db"
    _use_database(monkeypatch, db_path)
    db_utils.init_db()
    conn = db_utils.get_conn()
    conn.execute(
        "INSERT INTO users(id,username,status,created_at,updated_at) VALUES (1,'bob','active','','')"
    )
    conn.commit()

    first = member_service.get_or_create_api_key(1)
    assert first.startswith("SK_STOCK_API_")
    assert db_utils.get_api_key_auth_record(first)

    second = member_service.rotate_api_key(1)
    assert second.startswith("SK_STOCK_API_") and second != first
    assert db_utils.get_api_key_auth_record(first) is None
    assert db_utils.get_api_key_auth_record(second)
    stored = conn.execute("SELECT token,token_hash FROM api_keys WHERE user_id=1").fetchone()
    assert stored["token"].startswith("hashed:")
    assert first not in stored["token"] and second not in stored["token"]
    assert len(stored["token_hash"]) == 64
