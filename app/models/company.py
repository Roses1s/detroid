"""LEGACY: Компания — отключена, таблица остаётся для совместимости миграций.

Модуль удалён в рамках глобального обновления: оставляем только лиды.
Таблица companies не используется в активном коде, но не удаляется из БД чтобы не ломать старые миграции.
Будет удалена отдельной миграцией когда владелец решит, или переиспользована под новый модуль.
"""

from datetime import datetime

from ..extensions import db


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    inn = db.Column(db.String(20), default="")
    phone = db.Column(db.String(40), default="")
    email = db.Column(db.String(120), default="")
    address = db.Column(db.String(255), default="")
    website = db.Column(db.String(120), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Company {self.name}>"
