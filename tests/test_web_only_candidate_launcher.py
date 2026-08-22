from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]

LAUNCHER = (
    ROOT
    / "run_waitress_web_only.py"
)


def _source() -> str:
    return LAUNCHER.read_text(
        encoding="utf-8-sig"
    )


def test_web_only_launcher_exists():
    assert LAUNCHER.is_file()


def test_web_only_launcher_is_valid_python():
    ast.parse(
        _source(),
        filename=str(LAUNCHER),
    )


def test_web_only_launcher_never_starts_runtime_services():
    text = _source()

    assert "start_runtime_services" not in text
    assert "start_background=True" not in text


def test_web_only_launcher_uses_existing_app():
    text = _source()

    assert (
        "from app import app, setup_logging"
        in text
    )


def test_web_only_launcher_uses_configured_port():
    text = _source()

    assert "port=config.SERVER_PORT" in text
    assert "host=config.SERVER_HOST" in text


def test_web_only_launcher_matches_waitress_limits():
    text = _source()

    assert (
        "threads=config.SERVER_THREADS"
        in text
    )

    assert (
        "connection_limit="
        "config.WAITRESS_CONNECTION_LIMIT"
        in text
    )

    assert (
        "channel_timeout="
        "config.WAITRESS_CHANNEL_TIMEOUT"
        in text
    )


def test_app_global_instance_is_background_free():
    app_file = ROOT / "app.py"

    text = app_file.read_text(
        encoding="utf-8-sig"
    )

    normalized = "".join(
        text.split()
    )

    assert (
        "app=create_app("
        "start_background=False,"
        "configure_logging=False"
        ")"
        in normalized
    )
