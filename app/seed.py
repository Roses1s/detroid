"""Демо-данные — после сброса только администратор."""

import os
import secrets
import string

from . import create_app
from .extensions import db
from .models import User

DEMO_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")


def _admin_password() -> str:
    env_password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if env_password:
        return env_password
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


def _seed_admin() -> User:
    admin = User.query.filter_by(email=DEMO_EMAIL).first()
    if not admin:
        password = _admin_password()
        admin = User(
            username="admin",
            email=DEMO_EMAIL,
            full_name="Администратор",
            role="admin",
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        if os.environ.get("ADMIN_PASSWORD"):
            print(f"[seed] создан {DEMO_EMAIL} (пароль из ADMIN_PASSWORD)")
        else:
            print(f"[seed] создан {DEMO_EMAIL}")
            print(f"[seed] ПАРОЛЬ: {password}")
    else:
        print("[seed] админ уже есть")
    return admin


def seed() -> None:
    app = create_app()
    with app.app_context():
        _seed_admin()


if __name__ == "__main__":
    seed()
