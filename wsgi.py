"""WSGI entry point for Gunicorn/Waitress."""
from app import app

__all__ = ["app"]
