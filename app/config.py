"""Настройки приложения.

Читаются из переменных окружения (.env в корне).
Поддерживаются:
  - PostgreSQL (прод): DATABASE_URL=postgresql://...
  - SQLite (локально): DATABASE_URL=sqlite:///crm.db
"""

import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///crm.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    APP_NAME = os.environ.get("APP_NAME", "Детроид")

    # Пагинация — только лиды (единственный модуль)
    LEADS_PER_PAGE = int(os.environ.get("LEADS_PER_PAGE", "50"))

    # Cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "") == "1"

    # Анти-брутфорс
    LOGIN_MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", "5"))
    LOGIN_LOCK_SECONDS = int(os.environ.get("LOGIN_LOCK_SECONDS", "900"))
