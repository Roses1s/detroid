"""Компании (контакты полностью убраны из логики CRM).

Контакты — отдельный справочник, который больше не используется.
Клиентская информация теперь хранится прямо в лиде (компании):
- contact_name, phone, email внутри Lead.

Этот blueprint теперь отвечает только за компании.
Старые /contacts/... маршруты возвращают 410 Gone с пояснением.
"""

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..extensions import db
from ..models import Company, Lead

contacts_bp = Blueprint("contacts", __name__)


def _page_param() -> int:
    page = request.args.get("page", "1")
    return int(page) if page.isdigit() and int(page) > 0 else 1


def _fill_company(company: Company, form) -> None:
    company.name = (form.get("name") or "").strip()
    company.inn = (form.get("inn") or "").strip()
    company.phone = (form.get("phone") or "").strip()
    company.email = (form.get("email") or "").strip()
    company.address = (form.get("address") or "").strip()
    company.website = (form.get("website") or "").strip()
    company.notes = (form.get("notes") or "").strip()


# ─── Контакты убраны — старые URL возвращают пояснение ─────
@contacts_bp.route("/contacts")
@contacts_bp.route("/contacts/<path:_>")
@login_required
def contacts_removed(_=None):
    flash("Справочник контактов полностью убран из CRM. Клиент теперь — это лид (компания) с полями контактного лица.", "info")
    return redirect(url_for("leads.kanban"))


# ─── Компании ────────────────────────────────────────────
@contacts_bp.route("/companies")
@login_required
def companies_list():
    q = (request.args.get("q") or "").strip()
    query = Company.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Company.name.ilike(like)) | (Company.phone.ilike(like)) | (Company.email.ilike(like))
        )
    per_page = current_app.config["COMPANIES_PER_PAGE"]
    total = query.count()
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(_page_param(), pages)
    companies = (
        query.order_by(Company.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "companies/list.html", companies=companies, search_q=q,
        page=page, pages=pages, per_page=per_page, total=total,
    )


@contacts_bp.route("/companies/new", methods=["GET", "POST"])
@login_required
def company_create():
    if request.method == "POST":
        company = Company()
        _fill_company(company, request.form)
        if not company.name:
            flash("Укажите название компании.", "danger")
            return render_template("companies/form.html", company=company, is_new=True)
        db.session.add(company)
        db.session.commit()
        flash(f"Компания «{company.name}» создана.", "success")
        return redirect(url_for("contacts.company_detail", company_id=company.id))
    return render_template("companies/form.html", company=Company(), is_new=True)


@contacts_bp.route("/companies/<int:company_id>")
@login_required
def company_detail(company_id: int):
    company = Company.query.get_or_404(company_id)
    leads = company.leads.order_by(Lead.updated_at.desc()).all()
    # Контакты убраны — не показываем
    return render_template(
        "companies/detail.html", company=company, leads=leads
    )


@contacts_bp.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
@login_required
def company_edit(company_id: int):
    company = Company.query.get_or_404(company_id)
    if request.method == "POST":
        _fill_company(company, request.form)
        if not company.name:
            flash("Укажите название компании.", "danger")
        else:
            db.session.commit()
            flash(f"Компания «{company.name}» сохранена.", "success")
            return redirect(url_for("contacts.company_detail", company_id=company.id))
    return render_template("companies/form.html", company=company, is_new=False)


@contacts_bp.route("/companies/<int:company_id>/delete", methods=["POST"])
@login_required
def company_delete(company_id: int):
    """Удалить компанию — доступно всем пользователям."""
    company = Company.query.get_or_404(company_id)
    # Отвязываем лиды и заявки (сами записи не удаляем, только отвязываем)
    for lead in company.leads.all():
        lead.company_id = None
    for req in company.requests.all():
        req.company_id = None
    db.session.delete(company)
    db.session.commit()
    flash(f"Компания «{company.name}» удалена. Удалять могут все пользователи.", "info")
    return redirect(url_for("contacts.companies_list"))


@contacts_bp.route("/companies/clear-all", methods=["POST"])
@login_required
def companies_clear_all():
    """Удалить ВСЕ компании — доступно всем пользователям (первый шаг глобального обновления)."""
    count = Company.query.count()
    # Отвязываем лиды и заявки
    for lead in Lead.query.all():
        lead.company_id = None
    from ..models.request import Request as ReqModel
    db.session.query(ReqModel).update({ReqModel.company_id: None})
    db.session.query(Company).delete()
    db.session.commit()
    flash(f"Удалены ВСЕ компании: {count} шт.", "info")
    return redirect(request.form.get("next") or url_for("contacts.companies_list"))
