"""LEGACY: Контакт — полностью удалён из логики CRM.

Таблица contacts остаётся только для совместимости миграций.
"""

from datetime import datetime

from ..extensions import db


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False, default="")
    last_name = db.Column(db.String(80), nullable=False, default="")
    phone = db.Column(db.String(40), default="")
    email = db.Column(db.String(120), default="")
    position = db.Column(db.String(80), default="")
    notes = db.Column(db.Text, default="")
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or "Без имени"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Contact {self.full_name}>"
