"""REST API (JSON). Используется канбаном: drag&drop, быстрое создание, фильтры."""
from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

from . import contacts_api, filters_api, leads_api, requests_api  # noqa: E402,F401 — регистрирует маршруты на api_bp
