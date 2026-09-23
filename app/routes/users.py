"""Пользователи — только для админа. Регистрация закрыта."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Lead, LeadMessage, User

users_bp = Blueprint("users", __name__, url_prefix="/users")


def _require_admin():
    if current_user.role != "admin":
        abort(404)


@users_bp.route("/")
@login_required
def index():
    _require_admin()
    users = User.query.order_by(User.id).all()
    return render_template("users/index.html", users=users)


@users_bp.route("/new", methods=["POST"])
@login_required
def create():
    _require_admin()
    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    full_name = (request.form.get("full_name") or "").strip()
    role = request.form.get("role") or "manager"
    password = request.form.get("password") or ""

    error = None
    if not username or not email or not password:
        error = "Заполните имя пользователя, email и пароль."
    elif len(password) < 6:
        error = "Пароль должен быть не короче 6 символов."
    elif role not in ("admin", "manager"):
        error = "Неизвестная роль."
    elif User.query.filter_by(email=email).first():
        error = "Пользователь с таким email уже существует."
    elif User.query.filter_by(username=username).first():
        error = "Такое имя пользователя уже занято."

    if error:
        flash(error, "danger")
    else:
        user = User(username=username, email=email, full_name=full_name or username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f"Пользователь «{user.display_name}» создан.", "success")
    return redirect(url_for("users.index"))


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit(user_id: int):
    _require_admin()
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        full_name = (request.form.get("full_name") or "").strip()
        role = request.form.get("role") or "manager"
        password = request.form.get("password") or ""

        error = None
        if not username or not email:
            error = "Заполните логин и email."
        elif role not in ("admin", "manager"):
            error = "Неизвестная роль."
        elif user.id == current_user.id and role != "admin":
            error = "Нельзя лишить администраторских прав самого себя."
        elif password and len(password) < 6:
            error = "Пароль должен быть не короче 6 символов."
        elif User.query.filter(User.email == email, User.id != user.id).first():
            error = "Такой email уже занят другим пользователем."
        elif User.query.filter(User.username == username, User.id != user.id).first():
            error = "Такой логин уже занят другим пользователем."

        if error:
            flash(error, "danger")
        else:
            user.username = username
            user.email = email
            user.full_name = full_name or username
            user.role = role
            if password:
                user.set_password(password)
            db.session.commit()
            flash(f"Пользователь «{user.display_name}» сохранён.", "success")
            return redirect(url_for("users.index"))
    return render_template("users/edit.html", user=user)


@users_bp.route("/<int:user_id>/delete", methods=["POST"])
@login_required
def delete(user_id: int):
    _require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Нельзя удалить самого себя.", "warning")
    else:
        label = user.display_name
        # Отвязываем лиды и сообщения, чтобы FK не блокировал удаление
        Lead.query.filter_by(manager_id=user.id).update({"manager_id": None})
        LeadMessage.query.filter_by(author_id=user.id).update({"author_id": None})
        # Legacy таблицы — пробуем отвязать, если есть
        try:
            from ..models.request import Request as Req, RequestMessage as ReqMsg
            Req.query.filter_by(manager_id=user.id).update({"manager_id": None})
            ReqMsg.query.filter_by(author_id=user.id).update({"author_id": None})
        except Exception:
            pass
        db.session.delete(user)
        db.session.commit()
        flash(f"Пользователь «{label}» удалён.", "info")
    return redirect(url_for("users.index"))


@users_bp.route("/<int:user_id>/toggle", methods=["POST"])
@login_required
def toggle(user_id: int):
    _require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Нельзя заблокировать самого себя.", "warning")
    else:
        user.is_active = not user.is_active
        db.session.commit()
        state = "разблокирован" if user.is_active else "заблокирован"
        flash(f"Пользователь «{user.display_name}» {state}.", "info")
    return redirect(url_for("users.index"))
