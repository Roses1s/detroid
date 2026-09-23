"""Компания — юр. лицо / клиент (ЭТАП 3)."""
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

    contacts = db.relationship("Contact", back_populates="company", lazy="dynamic")
    leads = db.relationship("Lead", back_populates="company", lazy="dynamic")
    requests = db.relationship("Request", back_populates="company", lazy="dynamic")

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "inn": self.inn,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "website": self.website,
            "notes": self.notes,
            "contacts_count": self.contacts.count(),
            "leads_count": self.leads.count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Company {self.name}>"
