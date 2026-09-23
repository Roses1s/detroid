"""Лид — единственный активный модуль CRM + лента общения (chatter как в Odoo).

Очищен в рамках глобального обновления: удалены связи с компаниями, контактами и заявками.
Эти модули отключены и будут добавляться с нуля по указанию владельца.
"""

import enum
from datetime import datetime

from ..extensions import db


class LeadStage(str, enum.Enum):
    """Стадии воронки. Порядок важен — это порядок колонок канбана. Все стадии равноправны."""

    LEAD = "lead"
    NO_ANSWER = "no_answer"
    GATEKEEPER = "gatekeeper"
    LPR = "lpr"
    POTENTIAL = "potential"
    GONE = "gone"

    @property
    def title(self) -> str:
        return {
            "lead": "Лид",
            "no_answer": "Не дозвонились",
            "gatekeeper": "Не прошёл секретаря",
            "lpr": "Вышел на ЛПР",
            "potential": "Потенциальный клиент",
            "gone": "Уехали",
        }[self.value]

    @property
    def css_class(self) -> str:
        return {
            "lead": "stage-lead",
            "no_answer": "stage-no-answer",
            "gatekeeper": "stage-gatekeeper",
            "lpr": "stage-lpr",
            "potential": "stage-potential",
            "gone": "stage-gone",
        }[self.value]


STAGE_ORDER = [
    LeadStage.LEAD,
    LeadStage.NO_ANSWER,
    LeadStage.GATEKEEPER,
    LeadStage.LPR,
    LeadStage.POTENTIAL,
    LeadStage.GONE,
]


class MessageKind(str, enum.Enum):
    NOTE = "note"
    MESSAGE = "message"

    @property
    def title(self) -> str:
        return {"note": "Заметка", "message": "Сообщение"}[self.value]

    @property
    def icon(self) -> str:
        return {"note": "📝", "message": "✉️"}[self.value]


class Lead(db.Model):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    contact_name = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    email = db.Column(db.String(120), default="")
    source = db.Column(db.String(60), default="")
    expected_revenue = db.Column(db.Numeric(14, 2), default=0)
    stage = db.Column(db.Enum(LeadStage), nullable=False, default=LeadStage.LEAD)
    priority = db.Column(db.Integer, nullable=False, default=0)  # 0..3
    tags = db.Column(db.String(255), default="")
    notes = db.Column(db.Text, default="")

    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    manager = db.relationship("User", back_populates="leads")

    # Лента общения
    messages = db.relationship(
        "LeadMessage", back_populates="lead", lazy="dynamic",
        cascade="all, delete-orphan",
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Legacy поля оставлены в БД для совместимости миграций, но не используются в коде.
    # Если в старых данных есть company_id/contact_id — они игнорируются.
    # Чтобы SQLAlchemy не падал, колонки могут оставаться в таблице, но relationship удалён.
    # Мы явно НЕ объявляем company_id/contact_id здесь, чтобы не тянуть мертвый код.
    # Миграции знают о старых колонках, но ORM их не трогает.

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]

    @tag_list.setter
    def tag_list(self, values: list[str]) -> None:
        self.tags = ", ".join(v.strip() for v in values if v.strip())

    def log_stage_change(self, old_stage) -> None:
        if old_stage == self.stage:
            return
        old_title = old_stage.title if old_stage else "—"
        new_title = self.stage.title if self.stage else "—"
        db.session.add(
            LeadMessage(
                lead=self,
                author=None,
                kind=MessageKind.NOTE,
                body=f"🔀 Стадия изменена: {old_title} → {new_title}",
            )
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "contact_name": self.contact_name,
            "phone": self.phone,
            "email": self.email,
            "source": self.source,
            "expected_revenue": float(self.expected_revenue or 0),
            "stage": self.stage.value if self.stage else LeadStage.LEAD.value,
            "stage_title": self.stage.title if self.stage else "",
            "priority": self.priority,
            "tags": self.tag_list,
            "notes": self.notes,
            "manager_id": self.manager_id,
            "manager_name": self.manager.display_name if self.manager else None,
            "messages_count": self.messages.count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Lead {self.id} {self.title}>"


class LeadMessage(db.Model):
    __tablename__ = "lead_messages"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    lead = db.relationship("Lead", back_populates="messages")

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
            "lead_id": self.lead_id,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "kind": self.kind.value if self.kind else MessageKind.NOTE.value,
            "kind_title": self.kind.title if self.kind else "",
            "body": self.body,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LeadMessage {self.id} lead={self.lead_id}>"
