"""Пользователь системы (менеджер / администратор)."""
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False, default="")
    role = db.Column(db.String(20), nullable=False, default="manager")  # admin | manager
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Лиды, за которые отвечает менеджер
    leads = db.relationship("Lead", back_populates="manager", lazy="dynamic")
    requests = db.relationship("Request", back_populates="manager", lazy="dynamic")
    # Избранные фильтры поиска (Odoo: Favorites)
    saved_filters = db.relationship("SavedFilter", back_populates="user", lazy="dynamic",
                                    cascade="all, delete-orphan")

    # ── Пароль ──────────────────────────────────────────
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def display_name(self) -> str:
        return self.full_name or self.username

    def get_id(self):  # Flask-Login требует строку
        return str(self.id)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username}>"
