"""Контакты и компании (ЭТАП 3): списки, карточки, создание, редактирование."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Company, Contact, Lead

contacts_bp = Blueprint("contacts", __name__)


# ─── Контакты ────────────────────────────────────────────
def _fill_contact(contact: Contact, form) -> list[str]:
    warnings = []
    contact.first_name = (form.get("first_name") or "").strip()
    contact.last_name = (form.get("last_name") or "").strip()
    contact.phone = (form.get("phone") or "").strip()
    contact.email = (form.get("email") or "").strip()
    contact.position = (form.get("position") or "").strip()
    contact.notes = (form.get("notes") or "").strip()
    # Компания — только существующая (поддельный id не сохраняем)
    company_id = (form.get("company_id") or "").strip()
    if company_id.isdigit() and db.session.get(Company, int(company_id)):
        contact.company_id = int(company_id)
    else:
        if company_id:
            warnings.append("указанная компания не найдена — поле очищено")
        contact.company_id = None
    return warnings


def _page_param() -> int:
    page = request.args.get("page", "1")
    return int(page) if page.isdigit() and int(page) > 0 else 1


@contacts_bp.route("/contacts")
@login_required
def contacts_list():
    q = (request.args.get("q") or "").strip()
    query = Contact.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Contact.first_name.ilike(like))
            | (Contact.last_name.ilike(like))
            | (Contact.phone.ilike(like))
            | (Contact.email.ilike(like))
        )
    # Пагинация на уровне БД + жадная загрузка компании
    per_page = current_app.config["CONTACTS_PER_PAGE"]
    total = query.count()
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(_page_param(), pages)
    contacts = (
        query.options(selectinload(Contact.company))
        .order_by(Contact.last_name, Contact.first_name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "contacts/list.html", contacts=contacts, search_q=q,
        page=page, pages=pages, per_page=per_page, total=total,
    )


@contacts_bp.route("/contacts/new", methods=["GET", "POST"])
@login_required
def contact_create():
    companies = Company.query.order_by(Company.name).all()
    if request.method == "POST":
        contact = Contact()
        warnings = _fill_contact(contact, request.form)
        if not contact.first_name and not contact.last_name:
            flash("Укажите имя или фамилию контакта.", "danger")
            return render_template(
                "contacts/form.html", contact=contact, companies=companies, is_new=True
            )
        db.session.add(contact)
        db.session.commit()
        for w in warnings:
            flash(w.capitalize() + ".", "warning")
        flash(f"Контакт «{contact.full_name}» создан.", "success")
        return redirect(url_for("contacts.contact_detail", contact_id=contact.id))
    preset_company = (request.args.get("company_id") or "").strip()
    contact = Contact()
    if preset_company.isdigit():
        contact.company_id = int(preset_company)
    return render_template(
        "contacts/form.html", contact=contact, companies=companies, is_new=True
    )


@contacts_bp.route("/contacts/<int:contact_id>")
@login_required
def contact_detail(contact_id: int):
    contact = Contact.query.get_or_404(contact_id)
    leads = contact.leads.order_by(Lead.updated_at.desc()).all()
    return render_template("contacts/detail.html", contact=contact, leads=leads)


@contacts_bp.route("/contacts/<int:contact_id>/edit", methods=["GET", "POST"])
@login_required
def contact_edit(contact_id: int):
    contact = Contact.query.get_or_404(contact_id)
    companies = Company.query.order_by(Company.name).all()
    if request.method == "POST":
        warnings = _fill_contact(contact, request.form)
        if not contact.first_name and not contact.last_name:
            flash("Укажите имя или фамилию контакта.", "danger")
        else:
            db.session.commit()
            for w in warnings:
                flash(w.capitalize() + ".", "warning")
            flash(f"Контакт «{contact.full_name}» сохранён.", "success")
            return redirect(url_for("contacts.contact_detail", contact_id=contact.id))
    return render_template(
        "contacts/form.html", contact=contact, companies=companies, is_new=False
    )


@contacts_bp.route("/contacts/<int:contact_id>/delete", methods=["POST"])
@login_required
def contact_delete(contact_id: int):
    contact = Contact.query.get_or_404(contact_id)
    # Отвязываем лиды и заявки (сами записи не удаляем!)
    for lead in contact.leads.all():
        lead.contact_id = None
    for req in contact.requests.all():
        req.contact_id = None
    db.session.delete(contact)
    db.session.commit()
    flash(f"Контакт «{contact.full_name}» удалён.", "info")
    return redirect(url_for("contacts.contacts_list"))


# ─── Компании ────────────────────────────────────────────
def _fill_company(company: Company, form) -> None:
    company.name = (form.get("name") or "").strip()
    company.inn = (form.get("inn") or "").strip()
    company.phone = (form.get("phone") or "").strip()
    company.email = (form.get("email") or "").strip()
    company.address = (form.get("address") or "").strip()
    company.website = (form.get("website") or "").strip()
    company.notes = (form.get("notes") or "").strip()


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
    contacts = company.contacts.order_by(Contact.last_name, Contact.first_name).all()
    leads = company.leads.order_by(Lead.updated_at.desc()).all()
    return render_template(
        "companies/detail.html", company=company, contacts=contacts, leads=leads
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
    company = Company.query.get_or_404(company_id)
    # Отвязываем контакты, лиды и заявки (сами записи не удаляем!)
    for contact in company.contacts.all():
        contact.company_id = None
    for lead in company.leads.all():
        lead.company_id = None
    for req in company.requests.all():
        req.company_id = None
    db.session.delete(company)
    db.session.commit()
    flash(f"Компания «{company.name}» удалена.", "info")
    return redirect(url_for("contacts.companies_list"))
