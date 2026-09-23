"""Настройки приложения.

Читаются из переменных окружения (файл .env в корне проекта).
Поддерживаются два режима БД:
  - PostgreSQL (продакшен / Docker): DATABASE_URL=postgresql://...
  - SQLite (локальная разработка без Docker): DATABASE_URL=sqlite:///crm.db
"""
import os

from dotenv import load_dotenv

# Подгружаем .env из корня проекта (на уровень выше папки app/)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///crm.db")
    # Heroku-style postgres:// -> postgresql:// (SQLAlchemy 2.x требует второе)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Название компании в шапке
    APP_NAME = "Детроид"

    # Пагинация списков
    LEADS_PER_PAGE = 50
    CONTACTS_PER_PAGE = 50
    COMPANIES_PER_PAGE = 50

    # Cookies: без доступа из JS, только свой домен,
    # с учётом заголовков от прокси (nginx шлёт X-Forwarded-Proto)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Secure включается, когда сайт работает по HTTPS (см. ProxyFix в __init__.py)
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "") == "1"

    # Анти-брутфорс входа: не более MAX неудач за окно, дальше пауза
    LOGIN_MAX_FAILURES = 5
    LOGIN_LOCK_SECONDS = 900
