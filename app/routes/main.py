"""Главная страница — теперь редирект на канбан лидов (главный экран)."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..extensions import db

main_bp = Blueprint("main", __name__)


@main_bp.route("/health")
def health():
    return {"status": "ok"}


@main_bp.route("/clear-all-crm", methods=["POST"])
@login_required
def clear_all_crm():
    """Глобальная очистка — остаётся в бэкенде, кнопки в UI нет."""
    from ..models import Company, SavedFilter
    from ..models.lead import Lead, LeadMessage
    from ..models.request import Request as ReqModel, RequestMessage

    leads_count = Lead.query.count()
    req_count = ReqModel.query.count()
    comp_count = Company.query.count()

    db.session.query(RequestMessage).delete()
    db.session.query(LeadMessage).delete()
    db.session.query(ReqModel).delete()
    db.session.query(Lead).delete()
    try:
        from ..models import Contact
        db.session.query(Contact).delete()
    except Exception:
        pass
    db.session.query(Company).delete()
    db.session.query(SavedFilter).delete()
    db.session.commit()
    flash(f"CRM очищена: лидов {leads_count}, заявок {req_count}, компаний {comp_count}.", "info")
    return redirect(request.form.get("next") or url_for("leads.kanban"))


@main_bp.route("/")
@login_required
def dashboard():
    """Главный экран — канбан лидов (единственный модуль)."""
    return redirect(url_for("leads.kanban"))


@main_bp.route("/reports")
@login_required
def reports():
    """Отчёты отключены — оставляем 301 редирект на канбан чтобы старые ссылки не ломались."""
    return redirect(url_for("leads.kanban"), code=301)
