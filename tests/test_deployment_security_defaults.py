from __future__ import annotations

from pathlib import Path


def test_gunicorn_and_raw_debug_bind_loopback_by_default():
    gunicorn = Path("gunicorn.conf.py").read_text(encoding="utf-8")
    raw_debug = Path("tools/debug/raw_http_debug.py").read_text(encoding="utf-8")
    assert "os.getenv('SERVER_HOST', '127.0.0.1')" in gunicorn
    assert 'parser.add_argument("--host", default="127.0.0.1")' in raw_debug


def test_production_env_template_uses_secure_session_cookie():
    template = Path(".env.example").read_text(encoding="utf-8")
    assert "APP_ENV=production" in template
    assert "SESSION_COOKIE_SECURE=True" in template


def _numeric_version(value: str) -> tuple[int, ...]:
    return tuple(
        int(part)
        for part in value.split(".")
    )


def test_requirements_exclude_known_vulnerable_web_stack_versions():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    active = [
        line.strip()
        for line in requirements.splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
    ]

    assert active
    assert all("==" in line for line in active)

    pins = {}

    for line in active:
        requirement = (
            line.split(";", 1)[0].strip()
        )

        name, version = requirement.split(
            "==",
            1,
        )

        pins[name.lower()] = version.strip()

    minimums = {
        "flask": (3, 1, 3),
        "werkzeug": (3, 1, 8),
        "flask-cors": (6, 0, 5),
        "python-dotenv": (1, 2, 2),
        "requests": (2, 34, 2),
        "waitress": (3, 0, 2),
    }

    assert set(minimums).issubset(pins)

    for name, minimum in minimums.items():
        assert (
            _numeric_version(pins[name])
            >= minimum
        )

    for vulnerable_pin in (
        "Flask==2.3.3",
        "Flask-Cors==4.0.0",
        "python-dotenv==1.0.0",
    ):
        assert vulnerable_pin not in requirements
