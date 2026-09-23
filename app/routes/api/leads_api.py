"""JSON API лидов — единственный активный модуль."""

from flask import jsonify, request
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from ...extensions import db
from ...models.lead import Lead, LeadMessage, LeadStage, MessageKind
from ...models.user import User
from . import api_bp


@api_bp.route("/leads", methods=["GET"])
@login_required
def api_leads_list():
    stage = (request.args.get("stage") or "").strip()
    query = Lead.query.options(selectinload(Lead.manager))
    if stage:
        try:
            query = query.filter(Lead.stage == LeadStage(stage))
        except ValueError:
            return jsonify({"error": f"unknown stage: {stage}"}), 400
    leads = query.order_by(Lead.updated_at.desc()).all()
    return jsonify([l.to_dict() for l in leads])


@api_bp.route("/leads", methods=["POST"])
@login_required
def api_lead_create():
    data = request.get_json(force=True, silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    if len(title) > 200:
        return jsonify({"error": "title too long (max 200)"}), 400

    lead = Lead(title=title, manager_id=current_user.id)
    stage_value = (data.get("stage") or LeadStage.LEAD.value).strip()
    try:
        lead.stage = LeadStage(stage_value)
    except ValueError:
        lead.stage = LeadStage.LEAD

    if "manager" in data:
        mgr = (str(data.get("manager")) or "").strip()
        if mgr == "none":
            lead.manager_id = None
        elif mgr == "me":
            lead.manager_id = current_user.id
        elif mgr.isdigit() and db.session.get(User, int(mgr)):
            lead.manager_id = int(mgr)

    if "priority" in data:
        try:
            lead.priority = max(0, min(3, int(data["priority"])))
        except (TypeError, ValueError):
            pass

    lead.contact_name = (data.get("contact_name") or "").strip()[:120]
    lead.phone = (data.get("phone") or "").strip()[:40]
    try:
        lead.expected_revenue = float(data.get("expected_revenue") or 0)
        if lead.expected_revenue < 0:
            lead.expected_revenue = 0
    except (TypeError, ValueError):
        lead.expected_revenue = 0

    db.session.add(lead)
    db.session.commit()
    return jsonify(lead.to_dict()), 201


@api_bp.route("/leads/<int:lead_id>/stage", methods=["PATCH"])
@login_required
def api_lead_move(lead_id: int):
    lead = Lead.query.get_or_404(lead_id)
    data = request.get_json(force=True, silent=True) or {}
    stage_value = (data.get("stage") or "").strip()
    try:
        new_stage = LeadStage(stage_value)
    except ValueError:
        return jsonify({"error": f"unknown stage: {stage_value}"}), 400
    old_stage = lead.stage
    lead.stage = new_stage
    lead.log_stage_change(old_stage)
    db.session.commit()
    return jsonify(lead.to_dict())


@api_bp.route("/leads/<int:lead_id>/manager", methods=["PATCH"])
@login_required
def api_lead_assign(lead_id: int):
    lead = Lead.query.options(selectinload(Lead.manager)).get_or_404(lead_id)
    data = request.get_json(force=True, silent=True) or {}
    mgr = (str(data.get("manager")) or "").strip()
    if mgr == "none":
        new_id, new_name = None, "Без менеджера"
    elif mgr == "me":
        new_id, new_name = current_user.id, current_user.display_name
    elif mgr.isdigit() and db.session.get(User, int(mgr)):
        new_id = int(mgr)
        new_name = db.session.get(User, new_id).display_name
    else:
        return jsonify({"error": f"unknown manager: {mgr}"}), 400
    old_name = lead.manager.display_name if lead.manager else "Без менеджера"
    lead.manager_id = new_id
    if old_name != new_name:
        db.session.add(LeadMessage(
            lead=lead, author=None, kind=MessageKind.NOTE,
            body=f"👤 Менеджер изменён: {old_name} → {new_name}",
        ))
    db.session.commit()
    return jsonify(lead.to_dict())


@api_bp.route("/leads/<int:lead_id>/priority", methods=["PATCH"])
@login_required
def api_lead_priority(lead_id: int):
    lead = Lead.query.get_or_404(lead_id)
    data = request.get_json(force=True, silent=True) or {}
    try:
        num = int(data.get("priority"))
    except (TypeError, ValueError):
        return jsonify({"error": "priority must be 0..3"}), 400
    if num not in (0, 1, 2, 3):
        return jsonify({"error": "priority must be 0..3"}), 400
    lead.priority = num
    db.session.commit()
    return jsonify(lead.to_dict())


@api_bp.route("/leads/<int:lead_id>", methods=["PUT", "PATCH"])
@login_required
def api_lead_update(lead_id: int):
    lead = Lead.query.get_or_404(lead_id)
    data = request.get_json(force=True, silent=True) or {}
    for field in ("title", "contact_name", "phone", "email", "source", "notes"):
        if field in data and isinstance(data[field], str):
            setattr(lead, field, data[field].strip())
    if "expected_revenue" in data:
        try:
            val = float(data["expected_revenue"] or 0)
            lead.expected_revenue = max(0, val)
        except (TypeError, ValueError):
            pass
    if "priority" in data:
        try:
            lead.priority = max(0, min(3, int(data["priority"])))
        except (TypeError, ValueError):
            pass
    if "tags" in data and isinstance(data["tags"], list):
        lead.tag_list = [str(t) for t in data["tags"]]
    db.session.commit()
    return jsonify(lead.to_dict())


@api_bp.route("/leads/<int:lead_id>", methods=["DELETE"])
@login_required
def api_lead_delete(lead_id: int):
    lead = Lead.query.get_or_404(lead_id)
    db.session.delete(lead)
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/leads/<int:lead_id>/messages", methods=["GET"])
@login_required
def api_messages_list(lead_id: int):
    lead = Lead.query.get_or_404(lead_id)
    messages = lead.messages.order_by(LeadMessage.created_at.desc()).all()
    return jsonify([m.to_dict() for m in messages])


@api_bp.route("/leads/<int:lead_id>/messages", methods=["POST"])
@login_required
def api_message_create(lead_id: int):
    lead = Lead.query.get_or_404(lead_id)
    data = request.get_json(force=True, silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "body is required"}), 400
    if len(body) > 5000:
        return jsonify({"error": "body too long (max 5000)"}), 400
    try:
        kind = MessageKind((data.get("kind") or MessageKind.NOTE.value).strip())
    except ValueError:
        kind = MessageKind.NOTE
    msg = LeadMessage(lead=lead, author=current_user, kind=kind, body=body)
    db.session.add(msg)
    db.session.commit()
    return jsonify(msg.to_dict()), 201


@api_bp.route("/messages/<int:message_id>", methods=["DELETE"])
@login_required
def api_message_delete(message_id: int):
    msg = LeadMessage.query.get_or_404(message_id)
    if msg.author_id != current_user.id and current_user.role != "admin":
        return jsonify({"error": "you can delete only your own messages"}), 403
    db.session.delete(msg)
    db.session.commit()
    return jsonify({"ok": True})
