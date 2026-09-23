"""Фабрика — мягкий сброс: только дизайн Odoo + auth + users."""

import hashlib
import logging
import os
import re
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import csrf, db, login_manager, migrate


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if app.config["SECRET_KEY"] == "dev-secret-key-change-me":
        app.logger.warning("SECRET_KEY default! Set in .env")

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

    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.users import users_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    @app.after_request
    def minify_html(response):
        ctype = response.content_type or ""
        if "text/html" not in ctype:
            return response
        try:
            html = response.get_data(as_text=True)
        except Exception:
            return response
        if "<textarea" in html or "<pre" in html:
            html = re.sub(r'<!--(?!\[if).*?-->', '', html, flags=re.DOTALL)
            html = "\n".join(line.rstrip() for line in html.splitlines() if line.strip() != "")
            response.set_data(html)
            return response
        html = re.sub(r'<!--(?!\[if).*?-->', '', html, flags=re.DOTALL)
        html = re.sub(r'>\s+<', '><', html)
        html = "".join(line.strip() for line in html.splitlines() if line.strip())
        html = re.sub(r'\s{2,}', ' ', html)
        response.set_data(html)
        return response

    @app.context_processor
    def inject_globals():
        return {"app_name": app.config.get("APP_NAME", "Detroid CRM")}

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
