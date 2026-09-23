"""Общие расширения Flask. Создаются здесь, инициализируются в create_app()."""
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"  # куда слать неавторизованных
login_manager.login_message = "Войдите, чтобы продолжить."
login_manager.login_message_category = "warning"
csrf = CSRFProtect()
