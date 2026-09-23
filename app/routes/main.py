"""Главная страница (dashboard) и служебные страницы."""
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from sqlalchemy import func

from ..extensions import db
from ..models.lead import Lead, LeadStage

main_bp = Blueprint("main", __name__)


@main_bp.route("/health")
def health():
    """Для мониторинга и docker-проверок: жив ли сервис."""
    return {"status": "ok"}


@main_bp.route("/clear-all-crm", methods=["POST"])
@login_required
def clear_all_crm():
    """Глобальная очистка CRM — удалить ВСЕ карточки (лиды, компании, заявки, логи).
    
    Доступно всем пользователям — требование первого шага глобального обновления.
    Контакты уже убраны из логики.
    """
    from ..models import Company, SavedFilter
    from ..models.lead import LeadMessage
    from ..models.request import Request as ReqModel, RequestMessage

    # Считаем для сообщения
    leads_count = Lead.query.count()
    req_count = ReqModel.query.count()
    comp_count = Company.query.count()

    # Чистим логи
    db.session.query(RequestMessage).delete()
    db.session.query(LeadMessage).delete()
    # Чистим заявки
    db.session.query(ReqModel).delete()
    # Отвязываем и чистим лиды
    db.session.query(Lead).delete()
    # Контакты — если таблица еще есть
    try:
        from ..models import Contact
        db.session.query(Contact).delete()
    except Exception:
        pass
    db.session.query(Company).delete()
    db.session.query(SavedFilter).delete()
    db.session.commit()
    flash(f"CRM полностью очищена: лидов {leads_count}, заявок {req_count}, компаний {comp_count} удалено. Контакты убраны.", "info")
    return redirect(request.form.get("next") or url_for("main.dashboard"))


@main_bp.route("/")
@login_required
def dashboard():
    # Нейтральная статистика: финальных стадий нет, все лиды равноправны.
    total_leads = Lead.query.count()
    pipeline_sum = (
        db.session.query(func.coalesce(func.sum(Lead.expected_revenue), 0)).scalar()
    )
    week_ago = datetime.utcnow() - timedelta(days=7)
    week_leads = Lead.query.filter(Lead.created_at >= week_ago).count()
    avg_revenue = (
        db.session.query(func.coalesce(func.avg(Lead.expected_revenue), 0)).scalar()
    )
    recent_leads = Lead.query.order_by(Lead.updated_at.desc()).limit(5).all()
    return render_template(
        "dashboard/index.html",
        total_leads=total_leads,
        pipeline_sum=float(pipeline_sum or 0),
        week_leads=week_leads,
        avg_revenue=float(avg_revenue or 0),
        recent_leads=recent_leads,
    )


@main_bp.route("/reports")
@login_required
def reports():
    """Простая воронка по стадиям: сколько лидов и на какую сумму в каждой."""
    rows = (
        db.session.query(
            Lead.stage,
            func.count(Lead.id),
            func.coalesce(func.sum(Lead.expected_revenue), 0),
        )
        .group_by(Lead.stage)
        .all()
    )
    funnel = [
        {
            "stage": stage.value if stage else "lead",
            "title": stage.title if stage else "-",
            "count": count,
            "sum": float(total or 0),
        }
        for stage, count, total in rows
    ]
    return render_template("dashboard/reports.html", funnel=funnel)
