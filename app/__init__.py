"""Фабрика Flask-приложения — глобальное обновление: только канбан лидов и пользователи."""

import hashlib
import os
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import csrf, db, login_manager, migrate


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(app.root_path, "migrations"))
    login_manager.init_app(app)
    csrf.init_app(app)

    from .models import User  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify({"error": "auth required"}), 401
        return redirect(url_for("auth.login", next=request.path))

    # Маршруты — оставляем только канбан лидов и пользователи для админа
    # Все остальные модули (компании, заявки, контакты, отчеты) удалены — будем добавлять с нуля как скажешь
    from .routes.api import api_bp
    from .routes.auth import auth_bp
    from .routes.leads import leads_bp
    from .routes.main import main_bp
    from .routes.users import users_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(leads_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(users_bp)

    # Старые модули отключены — возвращают 410 если кто-то зайдет по старой ссылке
    # from .routes.contacts import contacts_bp
    # from .routes.requests import legacy_bp, requests_bp
    # app.register_blueprint(contacts_bp)
    # app.register_blueprint(requests_bp)
    # app.register_blueprint(legacy_bp)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    @app.context_processor
    def inject_globals():
        from .models.lead import LeadStage

        return {
            "app_name": app.config.get("APP_NAME", "Detroid CRM"),
            "LeadStage": LeadStage,
        }

    @app.template_filter("money")
    def money_filter(value):
        if value is None:
            return "—"
        try:
            return f"{float(value):,.0f} ₽".replace(",", " ")
        except (TypeError, ValueError):
            return str(value)

    @app.template_filter("tag_color")
    def tag_color_filter(tag: str) -> int:
        digest = hashlib.md5(str(tag).encode("utf-8")).hexdigest()
        return int(digest, 16) % 12

    @app.template_filter("timeago")
    def timeago_filter(value) -> str:
        if not value:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        now = datetime.utcnow()
        delta = (now - value).total_seconds()
        if delta < 0:
            delta = 0
        if delta < 60:
            return "только что"
        if delta < 3600:
            minutes = int(delta // 60)
            return f"{minutes} {plural_ru(minutes, 'минуту', 'минуты', 'минут')} назад"
        if delta < 86400:
            hours = int(delta // 3600)
            return f"{hours} {plural_ru(hours, 'час', 'часа', 'часов')} назад"
        days = int(delta // 86400)
        if days == 1:
            return "вчера"
        if days < 7:
            return f"{days} {plural_ru(days, 'день', 'дня', 'дней')} назад"
        if days < 30:
            weeks = max(1, days // 7)
            return f"{weeks} {plural_ru(weeks, 'неделю', 'недели', 'недель')} назад"
        if days < 365:
            months = max(1, days // 30)
            return f"{months} {plural_ru(months, 'месяц', 'месяца', 'месяцев')} назад"
        return value.strftime("%d.%m.%Y")

    @app.template_filter("ru_date")
    def ru_date_filter(value) -> str:
        if not value:
            return ""
        months = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля",
            5: "мая", 6: "июня", 7: "июля", 8: "августа",
            9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
        }
        return f"{value.day} {months.get(value.month, '')} {value.year} г."

    @app.template_filter("avatar_color")
    def avatar_color_filter(name: str) -> int:
        digest = hashlib.md5(str(name or "?").encode("utf-8")).hexdigest()
        return int(digest, 16) % 8

    return app


def plural_ru(number: int, one: str, few: str, many: str) -> str:
    number = abs(number) % 100
    n1 = number % 10
    if 10 < number < 20:
        return many
    if 1 < n1 < 5:
        return few
    if n1 == 1:
        return one
    return many
