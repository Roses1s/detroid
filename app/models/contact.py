"""Контакт — физическое лицо (ЭТАП 3)."""
from datetime import datetime

from ..extensions import db


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False, default="")
    last_name = db.Column(db.String(80), nullable=False, default="")
    phone = db.Column(db.String(40), default="")
    email = db.Column(db.String(120), default="")
    position = db.Column(db.String(80), default="")  # должность
    notes = db.Column(db.Text, default="")

    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    company = db.relationship("Company", back_populates="contacts")

    leads = db.relationship("Lead", back_populates="contact", lazy="dynamic")
    requests = db.relationship("Request", back_populates="contact", lazy="dynamic")

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or "Без имени"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "phone": self.phone,
            "email": self.email,
            "position": self.position,
            "notes": self.notes,
            "company_id": self.company_id,
            "company_name": self.company.name if self.company else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Contact {self.full_name}>"
