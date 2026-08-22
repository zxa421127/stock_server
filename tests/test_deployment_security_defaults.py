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


def test_requirements_exclude_known_vulnerable_web_stack_versions():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    assert "Flask>=3.1.3,<4" in requirements
    assert "Werkzeug>=3.1.8,<4" in requirements
    assert "Flask-Cors>=6.0.5,<7" in requirements
    assert "python-dotenv>=1.2.2,<2" in requirements
    assert "requests>=2.34.2,<3" in requirements
    assert "waitress>=3.0.2,<4" in requirements
    for vulnerable_pin in ("Flask==2.3.3", "Flask-Cors==4.0.0", "python-dotenv==1.0.0"):
        assert vulnerable_pin not in requirements
