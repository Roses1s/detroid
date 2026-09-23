"""Заявка на перевозку + лента общения по заявке.

ИСТОРИЯ: модуль вырос из «Грузоперевозок» (ЭТАП 4), поэтому имена таблиц
в БД сознательно НЕ переименованы (shipments, shipment_messages) — это
избавило от рискованного переименования таблиц на PostgreSQL.
В коде и интерфейсе сущность называется «Заявка» / Request.
"""
import enum
from datetime import datetime

from ..extensions import db
from .lead import MessageKind


class RequestStatus(str, enum.Enum):
    """Статусы заявки. Порядок важен — это порядок колонок канбана."""

    DRAFT = "draft"                  # Черновик
    NEW = "new"                      # Новая
    CARRIER_FOUND = "carrier_found"  # Перевозчик найден
    INVOICED = "invoiced"            # Счёт выставлен
    PAID = "paid"                    # Платёж получен
    CANCELLED = "cancelled"          # Отменена

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

    @property
    def css_class(self) -> str:
        return {
            "draft": "req-draft",
            "new": "req-new",
            "carrier_found": "req-carrier",
            "invoiced": "req-invoiced",
            "paid": "req-paid",
            "cancelled": "req-cancelled",
        }[self.value]


# Порядок колонок на канбане
STATUS_ORDER = [
    RequestStatus.DRAFT,
    RequestStatus.NEW,
    RequestStatus.CARRIER_FOUND,
    RequestStatus.INVOICED,
    RequestStatus.PAID,
    RequestStatus.CANCELLED,
]


class Request(db.Model):
    __tablename__ = "shipments"  # см. комментарий в шапке файла

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), unique=True, nullable=True)  # З-0001, выдаётся при создании
    title = db.Column(db.String(200), nullable=False)
    origin = db.Column(db.String(200), nullable=False, default="")       # откуда
    destination = db.Column(db.String(200), nullable=False, default="")  # куда
    cargo_type = db.Column(db.String(100), default="")
    weight = db.Column(db.Numeric(12, 3), nullable=True)   # кг
    volume = db.Column(db.Numeric(12, 3), nullable=True)   # м³
    transport_type = db.Column(db.String(60), default="")  # авто, ж/д, авиа, море
    status = db.Column(db.Enum(RequestStatus), nullable=False, default=RequestStatus.DRAFT)
    load_date = db.Column(db.Date, nullable=True)
    unload_date = db.Column(db.Date, nullable=True)

    # Деньги: цена клиенту и себестоимость перевозчика, маржа считается сама
    client_price = db.Column(db.Numeric(14, 2), default=0)
    cost = db.Column(db.Numeric(14, 2), default=0)

    # Наёмный перевозчик — простые текстовые поля (без справочников)
    carrier = db.Column(db.String(200), default="")
    driver_name = db.Column(db.String(200), default="")
    driver_phone = db.Column(db.String(60), default="")
    vehicle_number = db.Column(db.String(60), default="")

    # Ответственный (продавец)
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    manager = db.relationship("User", back_populates="requests")

    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True)
    lead = db.relationship("Lead", back_populates="requests")

    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    company = db.relationship("Company", back_populates="requests")

    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=True)
    contact = db.relationship("Contact", back_populates="requests")

    notes = db.Column(db.Text, default="")

    # Лента общения (новые сверху при выборке с сортировкой)
    messages = db.relationship(
        "RequestMessage", back_populates="request", lazy="dynamic",
        cascade="all, delete-orphan",
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    @property
    def margin(self) -> float:
        """Маржа = цена клиенту − себестоимость."""
        return float(self.client_price or 0) - float(self.cost or 0)

    @property
    def route(self) -> str:
        return f"{self.origin} → {self.destination}".strip(" →")

    @property
    def next_status(self):
        """Следующий статус для кнопки «Следующий статус» (None — некуда)."""
        order = [
            RequestStatus.DRAFT,
            RequestStatus.NEW,
            RequestStatus.CARRIER_FOUND,
            RequestStatus.INVOICED,
            RequestStatus.PAID,
        ]
        if self.status in order:
            idx = order.index(self.status)
            if idx < len(order) - 1:
                return order[idx + 1]
        return None

    def assign_number(self) -> None:
        """Номер вида З-0001. Вызывать после flush (нужен id)."""
        if not self.number and self.id:
            self.number = f"З-{self.id:04d}"

    def log_status_change(self, old_status) -> None:
        """Системная запись в ленту о смене статуса.

        Вызывать после смены self.status, commit — снаружи.
        """
        if old_status == self.status:
            return
        old_title = old_status.title if old_status else "—"
        new_title = self.status.title if self.status else "—"
        db.session.add(
            RequestMessage(
                request=self,
                author=None,  # системная запись
                kind=MessageKind.NOTE,
                body=f"🔀 Статус изменён: {old_title} → {new_title}",
            )
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "number": self.number,
            "title": self.title,
            "origin": self.origin,
            "destination": self.destination,
            "route": self.route,
            "cargo_type": self.cargo_type,
            "weight": float(self.weight) if self.weight is not None else None,
            "volume": float(self.volume) if self.volume is not None else None,
            "transport_type": self.transport_type,
            "status": self.status.value if self.status else RequestStatus.DRAFT.value,
            "status_title": self.status.title if self.status else "",
            "load_date": self.load_date.isoformat() if self.load_date else None,
            "unload_date": self.unload_date.isoformat() if self.unload_date else None,
            "client_price": float(self.client_price or 0),
            "cost": float(self.cost or 0),
            "margin": self.margin,
            "carrier": self.carrier,
            "driver_name": self.driver_name,
            "driver_phone": self.driver_phone,
            "vehicle_number": self.vehicle_number,
            "manager_id": self.manager_id,
            "manager_name": self.manager.display_name if self.manager else None,
            "lead_id": self.lead_id,
            "company_id": self.company_id,
            "company_name": self.company.name if self.company else None,
            "contact_id": self.contact_id,
            "contact_name": self.contact.full_name if self.contact else None,
            "notes": self.notes,
            "messages_count": self.messages.count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Request {self.id} {self.number} {self.origin}->{self.destination}>"


class RequestMessage(db.Model):
    """Одна запись в ленте заявки: заметка или сообщение."""

    __tablename__ = "shipment_messages"  # см. комментарий в шапке файла

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column("shipment_id", db.Integer,
                           db.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    request = db.relationship("Request", back_populates="messages")

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    author = db.relationship("User")

    kind = db.Column(db.Enum(MessageKind), nullable=False, default=MessageKind.NOTE)
    body = db.Column(db.Text, nullable=False, default="")

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def author_name(self) -> str:
        return self.author.display_name if self.author else "Система"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "kind": self.kind.value if self.kind else MessageKind.NOTE.value,
            "kind_title": self.kind.title if self.kind else "",
            "body": self.body,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RequestMessage {self.id} request={self.request_id}>"
