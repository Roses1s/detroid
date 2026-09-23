"""JSON API компаний (контакты полностью убраны из CRM)."""

from flask import jsonify, request
from flask_login import login_required

from ...extensions import db
from ...models import Company
from . import api_bp


# ── Контакты убраны — API возвращает 410 Gone ───────────
@api_bp.route("/contacts", methods=["GET", "POST"])
@api_bp.route("/contacts/<path:_>", methods=["GET", "PUT", "PATCH", "DELETE"])
@login_required
def api_contacts_removed(_=None):
    return jsonify({"error": "contacts removed", "message": "Справочник контактов полностью убран из CRM. Клиент теперь — это лид (компания)."}), 410


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
    """Удалить компанию — доступно всем пользователям."""
    company = Company.query.get_or_404(company_id)
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
