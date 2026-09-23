"""REST API — только лиды и фильтры (компании и заявки отключены)."""
from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

from . import filters_api, leads_api  # noqa: E402,F401 — регистрирует маршруты на api_bp
# contacts_api и requests_api отключены — модули удалены
