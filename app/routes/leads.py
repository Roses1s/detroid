"""Лиды — единственный модуль CRM: канбан, список, карточка, форма, лента."""

from itertools import groupby
from urllib.parse import urlencode

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import SavedFilter, User
from ..models.lead import STAGE_ORDER, Lead, LeadMessage, LeadStage, MessageKind

leads_bp = Blueprint("leads", __name__, url_prefix="/leads")


def _page_param() -> int:
    page = request.args.get("page", "1")
    return int(page) if page.isdigit() and int(page) > 0 else 1


_EAGER = (selectinload(Lead.manager),)


def _filtered_query():
    q = (request.args.get("q") or "").strip()
    stage = (request.args.get("stage") or "").strip()
    manager_id = (request.args.get("manager_id") or "").strip()
    priority = (request.args.get("priority") or "").strip()

    query = Lead.query
    if q:
        # Ограничиваем длину поиска чтобы не грузить БД
        q = q[:100]
        like = f"%{q}%"
        query = query.filter(
            or_(
                Lead.title.ilike(like),
                Lead.contact_name.ilike(like),
                Lead.phone.ilike(like),
                Lead.email.ilike(like),
                Lead.tags.ilike(like),
            )
        )
    if stage:
        try:
            query = query.filter(Lead.stage == LeadStage(stage))
        except ValueError:
            pass
    if manager_id:
        if manager_id == "me":
            query = query.filter(Lead.manager_id == current_user.id)
        elif manager_id == "none":
            query = query.filter(Lead.manager_id.is_(None))
        elif manager_id.isdigit():
            query = query.filter(Lead.manager_id == int(manager_id))
    if priority and priority.isdigit():
        query = query.filter(Lead.priority == int(priority))
    for f in _parse_custom_filters():
        query = _apply_custom_filter(query, f)
    return query


CUSTOM_FILTER_FIELDS = {
    "stage": {"title": "Стадия", "ops": ("=", "!=")},
    "manager": {"title": "Менеджер", "ops": ("=", "!=")},
    "priority": {"title": "Приоритет", "ops": ("=", "!=", ">=", "<=")},
    "revenue": {"title": "Сумма", "ops": ("=", ">=", "<=")},
    "tag": {"title": "Тег", "ops": ("~",)},
    "source": {"title": "Источник", "ops": ("~",)},
}
OP_TITLES = {"=": "=", "!=": "≠", ">=": "≥", "<=": "≤", "~": "содержит"}


def _money_short(value) -> str:
    try:
        return f"{float(value):,.0f}".replace(",", " ") + " ₽"
    except (TypeError, ValueError):
        return str(value)


def _custom_filter_label(field: str, op_: str, value: str):
    title = CUSTOM_FILTER_FIELDS[field]["title"]
    op_title = OP_TITLES[op_]
    if field == "stage":
        try:
            return f"{title} {op_title} {LeadStage(value).title}"
        except ValueError:
            return None
    if field == "manager":
        if value == "me":
            who = current_user.display_name
        elif value == "none":
            who = "Без менеджера"
        elif value.isdigit():
            user = db.session.get(User, int(value))
            who = user.display_name if user else f"#{value}"
        else:
            return None
        return f"{title} {op_title} {who}"
    if field == "priority":
        if not value.isdigit() or int(value) not in (0, 1, 2, 3):
            return None
        return f"{title} {op_title} {'★' * int(value) or '—'}"
    if field == "revenue":
        try:
            float(value)
        except (TypeError, ValueError):
            return None
        return f"{title} {op_title} {_money_short(value)}"
    return f"{title} {op_title} {value[:30]}"


def _parse_custom_filters():
    out = []
    for raw in request.args.getlist("flt"):
        parts = (raw or "").split("|", 2)
        if len(parts) != 3:
            continue
        field, op_, value = (p.strip() for p in parts)
        spec = CUSTOM_FILTER_FIELDS.get(field)
        if not spec or op_ not in spec["ops"] or value == "":
            continue
        # Ограничиваем длину значения
        if len(value) > 100:
            value = value[:100]
        label = _custom_filter_label(field, op_, value)
        if label is None:
            continue
        out.append({"field": field, "op": op_, "value": value, "label": label, "raw": raw})
    return out


def _manager_value(value: str):
    if value == "me":
        return current_user.id
    if value == "none":
        return None
    if value.isdigit():
        return int(value)
    return "bad"


def _apply_custom_filter(query, f):
    field, op_, value = f["field"], f["op"], f["value"]
    if field == "stage":
        stage = LeadStage(value)
        return query.filter(Lead.stage == stage if op_ == "=" else Lead.stage != stage)
    if field == "manager":
        resolved = _manager_value(value)
        if resolved == "bad":
            return query
        if op_ == "=":
            return query.filter(Lead.manager_id.is_(None) if resolved is None else Lead.manager_id == resolved)
        if resolved is None:
            return query.filter(Lead.manager_id.is_not(None))
        return query.filter(or_(Lead.manager_id != resolved, Lead.manager_id.is_(None)))
    if field == "priority":
        num = int(value)
        if op_ == "=":
            return query.filter(Lead.priority == num)
        if op_ == "!=":
            return query.filter(Lead.priority != num)
        if op_ == ">=":
            return query.filter(Lead.priority >= num)
        return query.filter(Lead.priority <= num)
    if field == "revenue":
        amount = func.coalesce(Lead.expected_revenue, 0)
        num = float(value)
        if op_ == "=":
            return query.filter(amount == num)
        if op_ == ">=":
            return query.filter(amount >= num)
        return query.filter(amount <= num)
    if field == "tag":
        return query.filter(Lead.tags.ilike(f"%{value}%"))
    return query.filter(Lead.source.ilike(f"%{value}%"))


GROUP_BY_MODES = {"stage": "Стадия", "manager": "Менеджер", "priority": "Приоритет"}


def _active_group() -> str:
    group = (request.args.get("group_by") or "stage").strip()
    return group if group in GROUP_BY_MODES else "stage"


def _group_columns(base, group: str):
    base = base.options(*_EAGER)
    if group == "manager":
        managers = User.query.filter_by(is_active=True).order_by(User.full_name).all()
        columns = []
        for m in managers + [None]:
            if m is not None:
                leads = base.filter(Lead.manager_id == m.id).order_by(Lead.priority.desc(), Lead.updated_at.desc()).all()
                title, drop = m.display_name, str(m.id)
            else:
                leads = base.filter(Lead.manager_id.is_(None)).order_by(Lead.priority.desc(), Lead.updated_at.desc()).all()
                title, drop = "Без менеджера", "none"
            total = sum(float(r.expected_revenue or 0) for r in leads)
            columns.append({"key": f"manager:{drop}", "title": title, "drop": drop, "leads": leads, "total": total})
        return columns, "manager", "manager"
    if group == "priority":
        columns = []
        for num, title in [(3, "★★★"), (2, "★★"), (1, "★"), (0, "—")]:
            leads = base.filter(Lead.priority == num).order_by(Lead.updated_at.desc()).all()
            total = sum(float(r.expected_revenue or 0) for r in leads)
            columns.append({"key": f"priority:{num}", "title": title, "drop": str(num), "leads": leads, "total": total})
        return columns, "priority", "priority"
    columns = []
    for stage in STAGE_ORDER:
        leads = base.filter(Lead.stage == stage).order_by(Lead.priority.desc(), Lead.updated_at.desc()).all()
        total = sum(float(r.expected_revenue or 0) for r in leads)
        columns.append({"key": f"stage:{stage.value}", "title": stage.title, "drop": stage.value, "leads": leads, "total": total})
    return columns, "stage", "stage"


def _qs(**overrides) -> str:
    args = request.args.to_dict(flat=False)
    for key, val in overrides.items():
        if val is None or val == "" or val == []:
            args.pop(key, None)
        elif isinstance(val, list):
            args[key] = [str(v) for v in val]
        else:
            args[key] = [str(val)]
    return urlencode(args, doseq=True)


def _qs_wo_flt(idx: int) -> str:
    args = request.args.to_dict(flat=False)
    rest = [f for i, f in enumerate(args.get("flt", [])) if i != idx]
    if rest:
        args["flt"] = rest
    else:
        args.pop("flt", None)
    return urlencode(args, doseq=True)


def _search_context():
    managers = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    rows = db.session.query(Lead.stage, func.count(Lead.id)).group_by(Lead.stage).all()
    stage_counts = {stage.value: count for stage, count in rows if stage}
    active_manager = request.args.get("manager_id", "")
    active_manager_name = ""
    if active_manager == "me":
        active_manager_name = "Мои лиды"
    elif active_manager == "none":
        active_manager_name = "Без менеджера"
    elif active_manager.isdigit():
        manager = db.session.get(User, int(active_manager))
        if manager:
            active_manager_name = manager.display_name
    return {
        "managers": managers,
        "stage_counts": stage_counts,
        "active_stage": request.args.get("stage", ""),
        "active_manager": active_manager,
        "active_manager_name": active_manager_name,
        "active_priority": request.args.get("priority", ""),
        "search_q": request.args.get("q", ""),
        "active_group": _active_group(),
        "group_modes": GROUP_BY_MODES,
        "custom_filters": _parse_custom_filters(),
        "active_flts": request.args.getlist("flt"),
        "favorites": SavedFilter.query.filter_by(user_id=current_user.id, target="leads").order_by(SavedFilter.name).all(),
        "qs": _qs,
        "qs_wo_flt": _qs_wo_flt,
        "searchview_data": {
            "stages": [{"value": s.value, "title": s.title} for s in STAGE_ORDER],
            "managers": [{"id": m.id, "name": m.display_name} for m in managers],
        },
    }


@leads_bp.route("/")
@login_required
def kanban():
    base = _filtered_query()
    group = _active_group()
    columns, status_key, move_suffix = _group_columns(base, group)
    max_total = max([c["total"] for c in columns], default=0)
    for c in columns:
        c["share"] = round(c["total"] / max_total * 100) if max_total else 0
    return render_template(
        "leads/kanban.html", columns=columns, view="kanban",
        status_key=status_key, move_suffix=move_suffix, **_search_context(),
    )


@leads_bp.route("/list")
@login_required
def list_view():
    per_page = current_app.config["LEADS_PER_PAGE"]
    base = _filtered_query()
    group = _active_group()
    if group == "stage":
        total_count = base.count()
        pages = max(1, (total_count + per_page - 1) // per_page)
        page = min(_page_param(), pages)
        query = base.options(*_EAGER).order_by(Lead.updated_at.desc())
        leads = query.offset((page - 1) * per_page).limit(per_page).all()
        page_sum = sum(float(l.expected_revenue or 0) for l in leads)
        groups = [{"title": None, "leads": leads, "total": page_sum}]
        total = float(base.with_entities(func.coalesce(func.sum(Lead.expected_revenue), 0)).scalar() or 0)
    else:
        columns, _, _ = _group_columns(base, group)
        groups = [{"title": c["title"], "leads": c["leads"], "total": c["total"]} for c in columns]
        total = sum(c["total"] for c in columns)
        total_count = sum(len(c["leads"]) for c in columns)
        page, pages = 1, 1
    return render_template(
        "leads/list.html", groups=groups, total=total, total_count=total_count,
        page=page, pages=pages, per_page=per_page, view="list", **_search_context()
    )


@leads_bp.route("/<int:lead_id>")
@login_required
def detail(lead_id: int):
    lead = Lead.query.options(*_EAGER).get_or_404(lead_id)
    messages = lead.messages.order_by(LeadMessage.created_at.desc()).all()
    days = [
        (day, list(group))
        for day, group in groupby(messages, key=lambda m: m.created_at.date() if m.created_at else None)
    ]
    return render_template("leads/detail.html", lead=lead, days=days, stages=STAGE_ORDER)


@leads_bp.route("/<int:lead_id>/stage", methods=["POST"])
@login_required
def move_stage(lead_id: int):
    lead = Lead.query.get_or_404(lead_id)
    try:
        new_stage = LeadStage((request.form.get("stage") or "").strip())
    except ValueError:
        flash("Неизвестная стадия.", "danger")
        return redirect(url_for("leads.detail", lead_id=lead.id))
    old_stage = lead.stage
    lead.stage = new_stage
    lead.log_stage_change(old_stage)
    db.session.commit()
    flash(f"Стадия: {new_stage.title}.", "success")
    return redirect(url_for("leads.detail", lead_id=lead.id))


@leads_bp.route("/<int:lead_id>/notes", methods=["POST"])
@login_required
def add_note(lead_id: int):
    lead = Lead.query.get_or_404(lead_id)
    body = (request.form.get("body") or "").strip()
    if len(body) > 5000:
        body = body[:5000]
    kind_value = (request.form.get("kind") or MessageKind.NOTE.value).strip()
    if not body:
        flash("Напишите текст записи — пустую добавлять нечего.", "warning")
    else:
        try:
            kind = MessageKind(kind_value)
        except ValueError:
            kind = MessageKind.NOTE
        db.session.add(LeadMessage(lead=lead, author=current_user, kind=kind, body=body))
        db.session.commit()
        flash("Запись добавлена в ленту.", "success")
    return redirect(url_for("leads.detail", lead_id=lead.id) + "#chatter")


@leads_bp.route("/notes/<int:message_id>/delete", methods=["POST"])
@login_required
def delete_note(message_id: int):
    msg = LeadMessage.query.get_or_404(message_id)
    lead_id = msg.lead_id
    if msg.author_id != current_user.id and current_user.role != "admin":
        flash("Удалять можно только свои записи.", "danger")
    else:
        db.session.delete(msg)
        db.session.commit()
        flash("Запись удалена.", "info")
    return redirect(url_for("leads.detail", lead_id=lead_id) + "#chatter")


def _fill_from_form(lead: Lead, form) -> list[str]:
    warnings = []
    title = (form.get("title") or "").strip()
    if len(title) > 200:
        title = title[:200]
    lead.title = title
    lead.contact_name = (form.get("contact_name") or "").strip()[:120]
    lead.phone = (form.get("phone") or "").strip()[:40]
    lead.email = (form.get("email") or "").strip()[:120]
    lead.source = (form.get("source") or "").strip()[:60]
    lead.notes = (form.get("notes") or "").strip()[:5000]
    try:
        val = float(form.get("expected_revenue") or 0)
        lead.expected_revenue = max(0, val)
    except ValueError:
        lead.expected_revenue = 0
    try:
        lead.priority = max(0, min(3, int(form.get("priority") or 0)))
    except ValueError:
        lead.priority = 0
    tags_raw = (form.get("tags") or "")[:500]
    lead.tag_list = tags_raw.split(",")
    stage_value = (form.get("stage") or "").strip()
    if stage_value:
        try:
            lead.stage = LeadStage(stage_value)
        except ValueError:
            pass
    manager_value = (form.get("manager_id") or "").strip()
    if manager_value.isdigit() and db.session.get(User, int(manager_value)):
        lead.manager_id = int(manager_value)
    else:
        if manager_value:
            warnings.append("указанный менеджер не найден — поле очищено")
        lead.manager_id = None
    return warnings


def _form_context():
    return {
        "managers": User.query.filter_by(is_active=True).order_by(User.full_name).all(),
        "stages": STAGE_ORDER,
    }


@leads_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    ctx = _form_context()
    if request.method == "POST":
        lead = Lead(manager_id=current_user.id)
        warnings = _fill_from_form(lead, request.form)
        if not lead.title:
            flash("Укажите название лида.", "danger")
            return render_template("leads/form.html", lead=lead, is_new=True, **ctx)
        db.session.add(lead)
        db.session.commit()
        for w in warnings:
            flash(w.capitalize() + ".", "warning")
        flash(f"Лид «{lead.title}» создан.", "success")
        return redirect(url_for("leads.detail", lead_id=lead.id))
    preset_stage = request.args.get("stage", LeadStage.LEAD.value)
    stage = LeadStage(preset_stage) if preset_stage in [s.value for s in STAGE_ORDER] else LeadStage.LEAD
    lead = Lead(title="", stage=stage)
    return render_template("leads/form.html", lead=lead, is_new=True, **ctx)


@leads_bp.route("/<int:lead_id>/edit", methods=["GET", "POST"])
@login_required
def edit(lead_id: int):
    lead = Lead.query.get_or_404(lead_id)
    ctx = _form_context()
    if request.method == "POST":
        old_stage = lead.stage
        warnings = _fill_from_form(lead, request.form)
        if not lead.title:
            flash("Укажите название лида.", "danger")
        else:
            lead.log_stage_change(old_stage)
            db.session.commit()
            for w in warnings:
                flash(w.capitalize() + ".", "warning")
            flash(f"Лид «{lead.title}» сохранён.", "success")
            return redirect(url_for("leads.detail", lead_id=lead.id))
    return render_template("leads/form.html", lead=lead, is_new=False, **ctx)


@leads_bp.route("/<int:lead_id>/delete", methods=["POST"])
@login_required
def delete(lead_id: int):
    lead = Lead.query.get_or_404(lead_id)
    db.session.delete(lead)
    db.session.commit()
    flash(f"Лид «{lead.title}» удалён.", "info")
    return redirect(url_for("leads.kanban"))


@leads_bp.route("/clear-all", methods=["POST"])
@login_required
def clear_all():
    leads_count = Lead.query.count()
    db.session.query(LeadMessage).delete()
    db.session.query(Lead).delete()
    db.session.commit()
    flash(f"Удалены ВСЕ лиды: {leads_count} шт.", "info")
    return redirect(request.form.get("next") or url_for("leads.kanban"))
