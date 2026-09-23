"""Вход / смена пароля / выход — безопасность."""

import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

_failed_attempts: dict[str, deque] = defaultdict(deque)


def _login_locked(ip: str, max_failures: int, lock_seconds: int) -> bool:
    times = _failed_attempts[ip]
    if not times:
        return False
    now = time.time()
    while times and now - times[0] > lock_seconds:
        times.popleft()
    return len(times) >= max_failures


def _login_failed(ip: str) -> None:
    _failed_attempts[ip].append(time.time())


def _login_succeeded(ip: str) -> None:
    _failed_attempts.pop(ip, None)


def _safe_next(value: str | None) -> str | None:
    """Только относительный путь внутри сайта, без //, \\ и схем."""
    if not value:
        return None
    # Блокируем абсолютные URL и протоколы
    if value.startswith("//") or value.startswith("\\\\"):
        return None
    if "\\" in value:
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return None
    if not value.startswith("/"):
        return None
    # Блокируем попытки выйти за пределы через // в середине после декодирования
    if "//" in value:
        return None
    return value


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        ip = request.remote_addr or "?"
        if _login_locked(ip, current_app.config["LOGIN_MAX_FAILURES"], current_app.config["LOGIN_LOCK_SECONDS"]):
            flash("Слишком много неудачных попыток. Попробуйте через несколько минут.", "warning")
            return render_template("auth/login.html"), 429
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if len(email) > 120 or len(password) > 200:
            flash("Неверный email или пароль.", "danger")
            return render_template("auth/login.html")
        user = User.query.filter_by(email=email).first()
        if user and user.is_active and user.check_password(password):
            _login_succeeded(ip)
            login_user(user, remember=bool(request.form.get("remember")))
            flash(f"Добро пожаловать, {user.display_name}!", "success")
            next_page = _safe_next(request.args.get("next")) or url_for("main.dashboard")
            return redirect(next_page)
        _login_failed(ip)
        flash("Неверный email или пароль.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    flash("Регистрация закрыта. Попросите администратора создать вам аккаунт.", "warning")
    return redirect(url_for("auth.login"))


@auth_bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_pwd = request.form.get("password") or ""
        new = request.form.get("new_password") or ""
        new2 = request.form.get("new_password2") or ""
        error = None
        if not current_user.check_password(current_pwd):
            error = "Текущий пароль указан неверно."
        elif len(new) < 6:
            error = "Новый пароль должен быть не короче 6 символов."
        elif len(new) > 128:
            error = "Новый пароль слишком длинный (макс 128)."
        elif new != new2:
            error = "Новые пароли не совпадают."
        elif new == current_pwd:
            error = "Новый пароль должен отличаться от старого."
        if error:
            flash(error, "danger")
        else:
            current_user.set_password(new)
            db.session.commit()
            flash("Пароль изменён.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth/password.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("auth.login"))
