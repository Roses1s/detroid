"""JSON API контактов и компаний (ЭТАП 3)."""
from flask import jsonify, request
from flask_login import login_required

from ...extensions import db
from ...models import Company, Contact
from . import api_bp


# ── Контакты ──────────────────────────────────────────────
@api_bp.route("/contacts", methods=["GET"])
@login_required
def api_contacts_list():
    contacts = Contact.query.order_by(Contact.last_name, Contact.first_name).all()
    return jsonify([c.to_dict() for c in contacts])


@api_bp.route("/contacts", methods=["POST"])
@login_required
def api_contact_create():
    data = request.get_json(force=True, silent=True) or {}
    contact = Contact()
    _apply_contact_data(contact, data)
    if not contact.first_name and not contact.last_name:
        return jsonify({"error": "first_name or last_name is required"}), 400
    db.session.add(contact)
    db.session.commit()
    return jsonify(contact.to_dict()), 201


@api_bp.route("/contacts/<int:contact_id>", methods=["GET"])
@login_required
def api_contact_get(contact_id: int):
    return jsonify(Contact.query.get_or_404(contact_id).to_dict())


@api_bp.route("/contacts/<int:contact_id>", methods=["PUT", "PATCH"])
@login_required
def api_contact_update(contact_id: int):
    contact = Contact.query.get_or_404(contact_id)
    data = request.get_json(force=True, silent=True) or {}
    _apply_contact_data(contact, data)
    db.session.commit()
    return jsonify(contact.to_dict())


@api_bp.route("/contacts/<int:contact_id>", methods=["DELETE"])
@login_required
def api_contact_delete(contact_id: int):
    contact = Contact.query.get_or_404(contact_id)
    for lead in contact.leads.all():
        lead.contact_id = None
    for req in contact.requests.all():
        req.contact_id = None
    db.session.delete(contact)
    db.session.commit()
    return jsonify({"ok": True})


def _apply_contact_data(contact: Contact, data: dict) -> None:
    for field in ("first_name", "last_name", "phone", "email", "position", "notes"):
        if field in data and isinstance(data[field], str):
            setattr(contact, field, data[field].strip())
    if "company_id" in data:
        value = data["company_id"]
        # Только существующая компания: поддельный/чужой id не сохраняем
        if isinstance(value, int) and db.session.get(Company, value):
            contact.company_id = value
        else:
            contact.company_id = None


# ── Компании ──────────────────────────────────────────────
@api_bp.route("/companies", methods=["GET"])
@login_required
def api_companies_list():
    companies = Company.query.order_by(Company.name).all()
    return jsonify([c.to_dict() for c in companies])


@api_bp.route("/companies", methods=["POST"])
@login_required
def api_company_create():
    data = request.get_json(force=True, silent=True) or {}
    company = Company()
    _apply_company_data(company, data)
    if not company.name:
        return jsonify({"error": "name is required"}), 400
    db.session.add(company)
    db.session.commit()
    return jsonify(company.to_dict()), 201


@api_bp.route("/companies/<int:company_id>", methods=["GET"])
@login_required
def api_company_get(company_id: int):
    return jsonify(Company.query.get_or_404(company_id).to_dict())


@api_bp.route("/companies/<int:company_id>", methods=["PUT", "PATCH"])
@login_required
def api_company_update(company_id: int):
    company = Company.query.get_or_404(company_id)
    data = request.get_json(force=True, silent=True) or {}
    _apply_company_data(company, data)
    db.session.commit()
    return jsonify(company.to_dict())


@api_bp.route("/companies/<int:company_id>", methods=["DELETE"])
@login_required
def api_company_delete(company_id: int):
    company = Company.query.get_or_404(company_id)
    for contact in company.contacts.all():
        contact.company_id = None
    for lead in company.leads.all():
        lead.company_id = None
    for req in company.requests.all():
        req.company_id = None
    db.session.delete(company)
    db.session.commit()
    return jsonify({"ok": True})


def _apply_company_data(company: Company, data: dict) -> None:
    for field in ("name", "inn", "phone", "email", "address", "website", "notes"):
        if field in data and isinstance(data[field], str):
            setattr(company, field, data[field].strip())
