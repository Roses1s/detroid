"""Вход / смена пароля / выход.

Безопасность (этап «ревью»):
- регистрация закрыта — аккаунты создаёт только администратор (/users/);
- брутфорс входа ограничен: после нескольких неудач — пауза по IP;
- параметр next после входа разрешён только внутри сайта;
- выход — через POST (вместе с CSRF-защитой).
"""
import time
from collections import defaultdict, deque

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Журнал неудачных попыток входа: IP -> времена попыток (в памяти, до перезапуска)
_failed_attempts: dict[str, deque] = defaultdict(deque)


def _login_locked(ip: str, max_failures: int, lock_seconds: int) -> bool:
    """Идёт ли сейчас блокировка входа для этого IP."""
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
    """Разрешаем редирект после входа только внутри сайта (относительный путь)."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return None
    return value


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        ip = request.remote_addr or "?"
        if _login_locked(ip, current_app.config["LOGIN_MAX_FAILURES"],
                         current_app.config["LOGIN_LOCK_SECONDS"]):
            flash("Слишком много неудачных попыток. Попробуйте через несколько минут.", "warning")
            return render_template("auth/login.html"), 429
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
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
    """Регистрация закрыта: аккаунты создаёт администратор в разделе «Пользователи»."""
    flash("Регистрация закрыта. Попросите администратора создать вам аккаунт.", "warning")
    return redirect(url_for("auth.login"))


@auth_bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    """Смена собственного пароля."""
    if request.method == "POST":
        current = request.form.get("password") or ""
        new = request.form.get("new_password") or ""
        new2 = request.form.get("new_password2") or ""
        error = None
        if not current_user.check_password(current):
            error = "Текущий пароль указан неверно."
        elif len(new) < 6:
            error = "Новый пароль должен быть не короче 6 символов."
        elif new != new2:
            error = "Новые пароли не совпадают."
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
    """Только POST: GET-выход можно было бы вызвать чужой страницей/картинкой."""
    logout_user()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("auth.login"))
