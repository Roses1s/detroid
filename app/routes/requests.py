"""Страницы заявок: список (как заказы в Odoo), канбан, карточка, форма, лента.

В шаблонах объект заявки называется `req` (имя `request` занято Flask).
"""
from datetime import date
from itertools import groupby

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Company, Lead, User
from ..models.lead import MessageKind
from ..models.request import STATUS_ORDER, RequestMessage, RequestStatus
from ..models.request import Request as RequestModel

requests_bp = Blueprint("requests", __name__, url_prefix="/requests")

PER_PAGE = 80

# Жадная загрузка связей: карточка заявки дёргает менеджера/компанию/лид
# Контакты убраны из логики CRM
_EAGER = (
    selectinload(RequestModel.manager),
    selectinload(RequestModel.company),
    selectinload(RequestModel.lead),
)

# Порядок автовыдвижения статуса кнопкой «Следующий статус» из списка
ADVANCE_ORDER = [
    RequestStatus.DRAFT,
    RequestStatus.NEW,
    RequestStatus.CARRIER_FOUND,
    RequestStatus.INVOICED,
    RequestStatus.PAID,
]


def _filtered_query():
    """Базовый запрос с учётом поиска и фильтров (GET-параметры)."""
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    manager_id = (request.args.get("manager_id") or "").strip()

    query = RequestModel.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                RequestModel.number.ilike(like),
                RequestModel.title.ilike(like),
                RequestModel.origin.ilike(like),
                RequestModel.destination.ilike(like),
                RequestModel.cargo_type.ilike(like),
                RequestModel.carrier.ilike(like),
                RequestModel.driver_name.ilike(like),
                RequestModel.vehicle_number.ilike(like),
            )
        )
    if status:
        try:
            query = query.filter(RequestModel.status == RequestStatus(status))
        except ValueError:
            pass
    if manager_id:
        if manager_id == "me":
            query = query.filter(RequestModel.manager_id == current_user.id)
        elif manager_id == "none":
            query = query.filter(RequestModel.manager_id.is_(None))
        elif manager_id.isdigit():
            query = query.filter(RequestModel.manager_id == int(manager_id))
    return query


def _search_context():
    """Контекст для поиска: продавцы, счётчики статусов, активные фильтры."""
    managers = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    rows = (
        db.session.query(RequestModel.status, func.count(RequestModel.id))
        .group_by(RequestModel.status)
        .all()
    )
    status_counts = {status.value: count for status, count in rows if status}
    active_manager = request.args.get("manager_id", "")
    active_manager_name = ""
    if active_manager == "me":
        active_manager_name = "Мои заявки"
    elif active_manager == "none":
        active_manager_name = "Без продавца"
    elif active_manager.isdigit():
        manager = db.session.get(User, int(active_manager))
        if manager:
            active_manager_name = manager.display_name
    return {
        "managers": managers,
        "status_counts": status_counts,
        "active_status": request.args.get("status", ""),
        "active_manager": active_manager,
        "active_manager_name": active_manager_name,
        "search_q": request.args.get("q", ""),
        "statuses": STATUS_ORDER,
    }


@requests_bp.route("/")
@login_required
def index():
    """Список заявок (основной вид, как заказы в Odoo): таблица + пейджер."""
    page = request.args.get("page", "1")
    page = int(page) if page.isdigit() and int(page) > 0 else 1
    # Пагинация на уровне БД: считаем и режем в SQL, а не грузим всё в память
    base = _filtered_query()
    total = base.count()
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, pages)
    items = (
        base.options(*_EAGER)
        .order_by(RequestModel.updated_at.desc())
        .offset((page - 1) * PER_PAGE)
        .limit(PER_PAGE)
        .all()
    )
    # Итоги по ВСЕМУ фильтру (не по странице) — двумя SQL-запросами
    grand_total = float(
        base.with_entities(func.coalesce(func.sum(RequestModel.client_price), 0)).scalar()
    )
    grand_margin = float(
        base.with_entities(
            func.coalesce(func.sum(RequestModel.client_price - RequestModel.cost), 0)
        ).scalar()
    )
    return render_template(
        "requests/list.html", requests=items, page=page, pages=pages, total=total,
        grand_total=grand_total, grand_margin=grand_margin, per_page=PER_PAGE,
        view="list", **_search_context()
    )


@requests_bp.route("/kanban")
@login_required
def kanban():
    """Канбан-доска: колонки = статусы, карточки = заявки."""
    base = _filtered_query()
    columns = []
    for status in STATUS_ORDER:
        reqs = (
            base.options(*_EAGER)
            .filter(RequestModel.status == status)
            .order_by(RequestModel.load_date.asc(), RequestModel.updated_at.desc())
            .all()
        )
        total = sum(float(r.client_price or 0) for r in reqs)
        columns.append({"status": status, "requests": reqs, "total": total})
    return render_template("requests/kanban.html", columns=columns, view="kanban", **_search_context())


@requests_bp.route("/<int:request_id>")
@login_required
def detail(request_id: int):
    """Карточка заявки: информация слева, лента общения справа."""
    req = RequestModel.query.get_or_404(request_id)
    messages = req.messages.order_by(RequestMessage.created_at.desc()).all()
    # Группируем ленту по дням (разделители дат как в карточке лида)
    days = [
        (day, list(group))
        for day, group in groupby(messages, key=lambda m: m.created_at.date() if m.created_at else None)
    ]
    return render_template(
        "requests/detail.html", req=req, days=days, statuses=STATUS_ORDER,
        advance_to=req.next_status,
    )


@requests_bp.route("/<int:request_id>/status", methods=["POST"])
@login_required
def move_status(request_id: int):
    """Смена статуса из статусбара-стрелок (как в Odoo)."""
    req = RequestModel.query.get_or_404(request_id)
    try:
        new_status = RequestStatus((request.form.get("status") or "").strip())
    except ValueError:
        flash("Неизвестный статус.", "danger")
        return redirect(url_for("requests.detail", request_id=req.id))
    old_status = req.status
    req.status = new_status
    req.log_status_change(old_status)
    db.session.commit()
    flash(f"Статус: {new_status.title}.", "success")
    return redirect(url_for("requests.detail", request_id=req.id))


@requests_bp.route("/<int:request_id>/advance", methods=["POST"])
@login_required
def advance(request_id: int):
    """Кнопка «Следующий статус» из списка заявок."""
    req = RequestModel.query.get_or_404(request_id)
    if req.status in ADVANCE_ORDER:
        idx = ADVANCE_ORDER.index(req.status)
        if idx < len(ADVANCE_ORDER) - 1:
            old_status = req.status
            req.status = ADVANCE_ORDER[idx + 1]
            req.log_status_change(old_status)
            db.session.commit()
            flash(f"Заявка {req.number or req.title}: {req.status.title}.", "success")
        else:
            flash("Заявка уже в финальном статусе.", "info")
    else:
        flash("Отменённую заявку двигать некуда.", "warning")
    return redirect(request.form.get("next") or url_for("requests.index"))


@requests_bp.route("/bulk-delete", methods=["POST"])
@login_required
def bulk_delete():
    """Массовое удаление выбранных чекбоксами заявок. Доступно всем пользователям."""
    ids = [int(v) for v in request.form.getlist("ids") if v.isdigit()]
    if ids:
        reqs = RequestModel.query.filter(RequestModel.id.in_(ids)).all()
        for req in reqs:
            db.session.delete(req)
        db.session.commit()
        flash(f"Удалено заявок: {len(reqs)}.", "info")
    return redirect(request.form.get("next") or url_for("requests.index"))


@requests_bp.route("/clear-all", methods=["POST"])
@login_required
def clear_all():
    """Удалить ВСЕ заявки в CRM — доступно всем пользователям (первый шаг глобального обновления)."""
    count = RequestModel.query.count()
    # Удаляем все сообщения заявок сначала (каскад, но явно)
    db.session.query(RequestMessage).delete()
    db.session.query(RequestModel).delete()
    db.session.commit()
    flash(f"Удалены ВСЕ заявки: {count} шт. Контакты уже убраны из логики.", "info")
    return redirect(request.form.get("next") or url_for("requests.index"))


@requests_bp.route("/<int:request_id>/notes", methods=["POST"])
@login_required
def add_note(request_id: int):
    """Добавить запись в ленту (заметка или сообщение)."""
    req = RequestModel.query.get_or_404(request_id)
    body = (request.form.get("body") or "").strip()
    kind_value = (request.form.get("kind") or MessageKind.NOTE.value).strip()
    if not body:
        flash("Напишите текст записи — пустую добавлять нечего.", "warning")
    else:
        try:
            kind = MessageKind(kind_value)
        except ValueError:
            kind = MessageKind.NOTE
        db.session.add(RequestMessage(request=req, author=current_user, kind=kind, body=body))
        db.session.commit()
        flash("Запись добавлена в ленту.", "success")
    return redirect(url_for("requests.detail", request_id=req.id) + "#chatter")


@requests_bp.route("/notes/<int:message_id>/delete", methods=["POST"])
@login_required
def delete_note(message_id: int):
    """Удалить запись из ленты (только свою; админ — любую)."""
    msg = RequestMessage.query.get_or_404(message_id)
    request_id = msg.request_id
    if msg.author_id != current_user.id and current_user.role != "admin":
        flash("Удалять можно только свои записи.", "danger")
    else:
        db.session.delete(msg)
        db.session.commit()
        flash("Запись удалена.", "info")
    return redirect(url_for("requests.detail", request_id=request_id) + "#chatter")


def _parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_float(value, default=0.0):
    try:
        return float((value or "") or default)
    except (TypeError, ValueError):
        return default


def _fill_from_form(req: RequestModel, form) -> list[str]:
    """Копирует поля формы в заявку. Возвращает предупреждения о поддельных ссылках.
    
    Контакты убраны из CRM — contact_id больше не используется.
    """
    warnings = []
    req.title = (form.get("title") or "").strip()
    req.origin = (form.get("origin") or "").strip()
    req.destination = (form.get("destination") or "").strip()
    req.cargo_type = (form.get("cargo_type") or "").strip()
    req.transport_type = (form.get("transport_type") or "").strip()
    req.notes = (form.get("notes") or "").strip()
    weight = (form.get("weight") or "").strip()
    req.weight = _parse_float(weight) if weight else None
    volume = (form.get("volume") or "").strip()
    req.volume = _parse_float(volume) if volume else None
    req.client_price = _parse_float(form.get("client_price"))
    req.cost = _parse_float(form.get("cost"))
    req.load_date = _parse_date(form.get("load_date"))
    req.unload_date = _parse_date(form.get("unload_date"))
    req.carrier = (form.get("carrier") or "").strip()
    req.driver_name = (form.get("driver_name") or "").strip()
    req.driver_phone = (form.get("driver_phone") or "").strip()
    req.vehicle_number = (form.get("vehicle_number") or "").strip()
    status_value = (form.get("status") or "").strip()
    if status_value:
        try:
            req.status = RequestStatus(status_value)
        except ValueError:
            pass
    # Внешние ключи — только существующие записи (поддельные id не сохраняем)
    manager_value = (form.get("manager_id") or "").strip()
    if manager_value.isdigit() and db.session.get(User, int(manager_value)):
        req.manager_id = int(manager_value)
    else:
        if manager_value:
            warnings.append("указанный продавец не найден — поле очищено")
        req.manager_id = None
    lead_value = (form.get("lead_id") or "").strip()
    if lead_value.isdigit() and db.session.get(Lead, int(lead_value)):
        req.lead_id = int(lead_value)
    else:
        if lead_value:
            warnings.append("указанный лид не найден — поле очищено")
        req.lead_id = None
    company_value = (form.get("company_id") or "").strip()
    if company_value.isdigit() and db.session.get(Company, int(company_value)):
        req.company_id = int(company_value)
    else:
        if company_value:
            warnings.append("указанная компания не найдена — поле очищено")
        req.company_id = None
    # Контакты убраны — чистим поле
    if hasattr(req, 'contact_id'):
        req.contact_id = None
    return warnings


def _form_context():
    """Списки для выпадающих меню формы заявки. Контакты убраны."""
    return {
        "managers": User.query.filter_by(is_active=True).order_by(User.full_name).all(),
        "leads": Lead.query.order_by(Lead.updated_at.desc()).all(),
        "companies": Company.query.order_by(Company.name).all(),
        "statuses": STATUS_ORDER,
    }


def _prefill_from_lead(req: RequestModel, lead_id: str) -> None:
    """Подставить данные из лида (кнопка «Создать заявку» в лиде)."""
    if not lead_id or not lead_id.isdigit():
        return
    lead = db.session.get(Lead, int(lead_id))
    if not lead:
        return
    req.lead_id = lead.id
    req.title = lead.title
    req.manager_id = lead.manager_id
    req.company_id = lead.company_id
    req.client_price = float(lead.expected_revenue or 0)


@requests_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    ctx = _form_context()
    if request.method == "POST":
        req = RequestModel(manager_id=current_user.id)
        warnings = _fill_from_form(req, request.form)
        if form_manager_blank(request.form):
            req.manager_id = current_user.id
        if not req.title:
            flash("Укажите название заявки.", "danger")
            return render_template("requests/form.html", req=req, is_new=True, **ctx)
        db.session.add(req)
        db.session.flush()
        req.assign_number()
        db.session.commit()
        for w in warnings:
            flash(w.capitalize() + ".", "warning")
        flash(f"Заявка {req.number} создана.", "success")
        return redirect(url_for("requests.detail", request_id=req.id))
    preset_status = request.args.get("status", RequestStatus.DRAFT.value)
    req = RequestModel(
        title="",
        status=RequestStatus(preset_status) if preset_status in [s.value for s in STATUS_ORDER] else RequestStatus.DRAFT,
    )
    _prefill_from_lead(req, request.args.get("lead_id", ""))
    return render_template("requests/form.html", req=req, is_new=True, **ctx)


def form_manager_blank(form) -> bool:
    """В форме не выбрали продавца (тогда подставляем себя)."""
    return not (form.get("manager_id") or "").strip()


@requests_bp.route("/<int:request_id>/edit", methods=["GET", "POST"])
@login_required
def edit(request_id: int):
    req = RequestModel.query.get_or_404(request_id)
    ctx = _form_context()
    if request.method == "POST":
        old_status = req.status
        warnings = _fill_from_form(req, request.form)
        if not req.title:
            flash("Укажите название заявки.", "danger")
        else:
            req.log_status_change(old_status)
            db.session.commit()
            for w in warnings:
                flash(w.capitalize() + ".", "warning")
            flash(f"Заявка {req.number or req.title} сохранена.", "success")
            return redirect(url_for("requests.detail", request_id=req.id))
    return render_template("requests/form.html", req=req, is_new=False, **ctx)


@requests_bp.route("/<int:request_id>/delete", methods=["POST"])
@login_required
def delete(request_id: int):
    req = RequestModel.query.get_or_404(request_id)
    label = req.number or req.title  # запомнить ДО удаления: после commit объект мёртв
    db.session.delete(req)
    db.session.commit()
    flash(f"Заявка {label} удалена.", "info")
    return redirect(url_for("requests.index"))


# ── Старые ссылки /shipments/... -> /requests/... (301) ──────
legacy_bp = Blueprint("shipments_legacy", __name__)


@legacy_bp.route("/shipments/", defaults={"path": ""})
@legacy_bp.route("/shipments/<path:path>")
def shipments_redirect(path: str):
    target = "/requests/" + path
    if request.query_string:
        target += "?" + request.query_string.decode("utf-8", "replace")
    return redirect(target, code=301)
