"""Главная: health, очистка CRM, редиректы на канбан лидов."""

from flask import Blueprint, flash, redirect, request, url_for
from flask_login import login_required

from ..extensions import db

main_bp = Blueprint("main", __name__)


@main_bp.route("/health")
def health():
    return {"status": "ok"}


@main_bp.route("/clear-all-crm", methods=["POST"])
@login_required
def clear_all_crm():
    """Глобальная очистка — остаётся в бэкенде, без кнопки в UI.

    Чистит все таблицы, включая legacy (companies, contacts, shipments) для полной очистки.
    """
    from ..models import SavedFilter
    from ..models.lead import Lead, LeadMessage

    # Считаем только лиды для сообщения
    leads_count = Lead.query.count()

    # Сообщения
    db.session.query(LeadMessage).delete()

    # Legacy — чистим если таблицы существуют
    for legacy_model_name in ("RequestMessage", "Request", "Company", "Contact"):
        try:
            if legacy_model_name == "RequestMessage":
                from ..models.request import RequestMessage as RM
                db.session.query(RM).delete()
            elif legacy_model_name == "Request":
                from ..models.request import Request as R
                db.session.query(R).delete()
            elif legacy_model_name == "Company":
                from ..models.company import Company
                db.session.query(Company).delete()
            elif legacy_model_name == "Contact":
                from ..models.contact import Contact
                db.session.query(Contact).delete()
        except Exception:
            pass

    db.session.query(Lead).delete()
    db.session.query(SavedFilter).delete()
    db.session.commit()
    flash(f"CRM очищена: лидов {leads_count} удалено.", "info")
    return redirect(request.form.get("next") or url_for("leads.kanban"))


@main_bp.route("/")
@login_required
def dashboard():
    return redirect(url_for("leads.kanban"))


@main_bp.route("/reports")
@login_required
def reports():
    return redirect(url_for("leads.kanban"), code=301)
