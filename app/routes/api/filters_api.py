"""JSON API избранных фильтров — только для лидов."""

from flask import jsonify, request
from flask_login import current_user, login_required

from ...extensions import db
from ...models.saved_filter import SavedFilter
from . import api_bp

TARGETS = ("leads",)


@api_bp.route("/favorites", methods=["GET"])
@login_required
def api_favorites_list():
    target = (request.args.get("target") or "leads").strip()
    if target not in TARGETS:
        target = "leads"
    favs = (
        SavedFilter.query.filter_by(user_id=current_user.id, target=target)
        .order_by(SavedFilter.name)
        .all()
    )
    return jsonify([f.to_dict() for f in favs])


@api_bp.route("/favorites", methods=["POST"])
@login_required
def api_favorite_create():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    target = (data.get("target") or "leads").strip()
    params = (data.get("params") or "").strip().lstrip("?")
    if not name:
        return jsonify({"error": "name is required"}), 400
    if len(name) > 80:
        return jsonify({"error": "name too long (max 80)"}), 400
    if target not in TARGETS:
        return jsonify({"error": f"unknown target: {target}"}), 400
    if len(params) > 2000:
        return jsonify({"error": "params too long"}), 400
    fav = SavedFilter(user_id=current_user.id, name=name, target=target, params=params)
    db.session.add(fav)
    db.session.commit()
    return jsonify(fav.to_dict()), 201


@api_bp.route("/favorites/<int:fav_id>", methods=["DELETE"])
@login_required
def api_favorite_delete(fav_id: int):
    fav = SavedFilter.query.get_or_404(fav_id)
    if fav.user_id != current_user.id:
        return jsonify({"error": "not your favorite"}), 403
    db.session.delete(fav)
    db.session.commit()
    return jsonify({"ok": True})
