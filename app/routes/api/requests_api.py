"""JSON API заявок: список, создание, смена статуса, удаление, лента."""
from datetime import date

from flask import jsonify, request
from flask_login import current_user, login_required

from ...extensions import db
from ...models.lead import MessageKind
from ...models.request import RequestMessage, RequestStatus
from ...models.request import Request as RequestModel
from . import api_bp


@api_bp.route("/requests", methods=["GET"])
@login_required
def api_requests_list():
    status = (request.args.get("status") or "").strip()
    query = RequestModel.query
    if status:
        try:
            query = query.filter(RequestModel.status == RequestStatus(status))
        except ValueError:
            return jsonify({"error": f"unknown status: {status}"}), 400
    reqs = query.order_by(RequestModel.updated_at.desc()).all()
    return jsonify([r.to_dict() for r in reqs])


@api_bp.route("/requests", methods=["POST"])
@login_required
def api_request_create():
    data = request.get_json(force=True, silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    req = RequestModel(title=title, manager_id=current_user.id)
    status_value = (data.get("status") or RequestStatus.DRAFT.value).strip()
    try:
        req.status = RequestStatus(status_value)
    except ValueError:
        req.status = RequestStatus.DRAFT
    req.origin = (data.get("origin") or "").strip()
    req.destination = (data.get("destination") or "").strip()
    db.session.add(req)
    db.session.flush()
    req.assign_number()
    db.session.commit()
    return jsonify(req.to_dict()), 201


@api_bp.route("/requests/<int:request_id>/status", methods=["PATCH"])
@login_required
def api_request_move(request_id: int):
    """Смена статуса — вызывается при drag&drop карточки."""
    req = RequestModel.query.get_or_404(request_id)
    data = request.get_json(force=True, silent=True) or {}
    status_value = (data.get("status") or "").strip()
    try:
        new_status = RequestStatus(status_value)
    except ValueError:
        return jsonify({"error": f"unknown status: {status_value}"}), 400
    old_status = req.status
    req.status = new_status
    req.log_status_change(old_status)
    db.session.commit()
    return jsonify(req.to_dict())


@api_bp.route("/requests/<int:request_id>", methods=["PUT", "PATCH"])
@login_required
def api_request_update(request_id: int):
    req = RequestModel.query.get_or_404(request_id)
    data = request.get_json(force=True, silent=True) or {}
    for field in ("title", "origin", "destination", "cargo_type", "transport_type",
                  "carrier", "driver_name", "driver_phone", "vehicle_number", "notes"):
        if field in data and isinstance(data[field], str):
            setattr(req, field, data[field].strip())
    for field in ("client_price", "cost", "weight", "volume"):
        if field in data:
            try:
                setattr(req, field, float(data[field] or 0))
            except (TypeError, ValueError):
                pass
    for field in ("load_date", "unload_date"):
        if field in data:
            try:
                setattr(req, field, date.fromisoformat(data[field]) if data[field] else None)
            except (TypeError, ValueError):
                pass
    db.session.commit()
    return jsonify(req.to_dict())


@api_bp.route("/requests/<int:request_id>", methods=["DELETE"])
@login_required
def api_request_delete(request_id: int):
    req = RequestModel.query.get_or_404(request_id)
    db.session.delete(req)
    db.session.commit()
    return jsonify({"ok": True})


# ── Лента общения ─────────────────────────────────────────
@api_bp.route("/requests/<int:request_id>/messages", methods=["GET"])
@login_required
def api_request_messages_list(request_id: int):
    req = RequestModel.query.get_or_404(request_id)
    messages = req.messages.order_by(RequestMessage.created_at.desc()).all()
    return jsonify([m.to_dict() for m in messages])


@api_bp.route("/requests/<int:request_id>/messages", methods=["POST"])
@login_required
def api_request_message_create(request_id: int):
    req = RequestModel.query.get_or_404(request_id)
    data = request.get_json(force=True, silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "body is required"}), 400
    try:
        kind = MessageKind((data.get("kind") or MessageKind.NOTE.value).strip())
    except ValueError:
        kind = MessageKind.NOTE
    msg = RequestMessage(request=req, author=current_user, kind=kind, body=body)
    db.session.add(msg)
    db.session.commit()
    return jsonify(msg.to_dict()), 201


@api_bp.route("/request-messages/<int:message_id>", methods=["DELETE"])
@login_required
def api_request_message_delete(message_id: int):
    msg = RequestMessage.query.get_or_404(message_id)
    if msg.author_id != current_user.id and current_user.role != "admin":
        return jsonify({"error": "you can delete only your own messages"}), 403
    db.session.delete(msg)
    db.session.commit()
    return jsonify({"ok": True})
