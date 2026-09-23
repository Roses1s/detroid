"""Сохранённый фильтр поиска («Избранное» как в Odoo).

Хранит querystring: q, stage, manager_id, priority, group_by, flt...
Только для лидов — единственный активный модуль.
"""

from datetime import datetime

from ..extensions import db


class SavedFilter(db.Model):
    __tablename__ = "saved_filters"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user = db.relationship("User", back_populates="saved_filters")

    name = db.Column(db.String(80), nullable=False)
    target = db.Column(db.String(20), nullable=False, default="leads")  # сейчас только leads
    params = db.Column(db.Text, nullable=False, default="")

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "target": self.target,
            "params": self.params or "",
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SavedFilter {self.id} {self.target}:{self.name}>"
