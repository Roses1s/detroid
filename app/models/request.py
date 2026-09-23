"""LEGACY: Заявка на перевозку — отключена.

Таблица shipments и shipment_messages остаются для совместимости миграций.
Модуль удалён: оставляем только лиды. Код ниже не используется в активных маршрутах,
но нужен чтобы Alembic видел таблицы.

Если решите вернуть заявки — восстановите из git истории до коммита bf448e4.
"""

import enum
from datetime import datetime

from ..extensions import db
from .lead import MessageKind


class RequestStatus(str, enum.Enum):
    DRAFT = "draft"
    NEW = "new"
    CARRIER_FOUND = "carrier_found"
    INVOICED = "invoiced"
    PAID = "paid"
    CANCELLED = "cancelled"

    @property
    def title(self) -> str:
        return {
            "draft": "Черновик",
            "new": "Новая",
            "carrier_found": "Перевозчик найден",
            "invoiced": "Счёт выставлен",
            "paid": "Платёж получен",
            "cancelled": "Отменена",
        }[self.value]


STATUS_ORDER = [
    RequestStatus.DRAFT,
    RequestStatus.NEW,
    RequestStatus.CARRIER_FOUND,
    RequestStatus.INVOICED,
    RequestStatus.PAID,
    RequestStatus.CANCELLED,
]


class Request(db.Model):
    __tablename__ = "shipments"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), unique=True, nullable=True)
    title = db.Column(db.String(200), nullable=False)
    origin = db.Column(db.String(200), nullable=False, default="")
    destination = db.Column(db.String(200), nullable=False, default="")
    cargo_type = db.Column(db.String(100), default="")
    weight = db.Column(db.Numeric(12, 3), nullable=True)
    volume = db.Column(db.Numeric(12, 3), nullable=True)
    transport_type = db.Column(db.String(60), default="")
    status = db.Column(db.Enum(RequestStatus), nullable=False, default=RequestStatus.DRAFT)
    load_date = db.Column(db.Date, nullable=True)
    unload_date = db.Column(db.Date, nullable=True)
    client_price = db.Column(db.Numeric(14, 2), default=0)
    cost = db.Column(db.Numeric(14, 2), default=0)
    carrier = db.Column(db.String(200), default="")
    driver_name = db.Column(db.String(200), default="")
    driver_phone = db.Column(db.String(60), default="")
    vehicle_number = db.Column(db.String(60), default="")
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=True)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Request {self.id}>"


class RequestMessage(db.Model):
    __tablename__ = "shipment_messages"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column("shipment_id", db.Integer, db.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    kind = db.Column(db.Enum(MessageKind), nullable=False, default=MessageKind.NOTE)
    body = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RequestMessage {self.id}>"
