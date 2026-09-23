"""Лид (потенциальная сделка) + лента общения (chatter как в Odoo)."""
import enum
# NB: datetime.utcnow() сознательно (весь проект на нём; в Python 3.12 он
# deprecated, но переход на aware-даты поменяет смысл уже записанных дат —
# делать отдельной миграцией при переходе на новые версии).
from datetime import datetime

from ..extensions import db


class LeadStage(str, enum.Enum):
    """Стадии воронки холодных звонков. Порядок важен — это порядок колонок канбана."""

    LEAD = "lead"                  # Лид
    NO_ANSWER = "no_answer"        # Не дозвонились
    GATEKEEPER = "gatekeeper"      # Не прошёл секретаря
    LPR = "lpr"                    # Вышел на ЛПР
    POTENTIAL = "potential"        # Потенциальный клиент
    GONE = "gone"                  # Уехали

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


# Порядок колонок на канбане
STAGE_ORDER = [
    LeadStage.LEAD,
    LeadStage.NO_ANSWER,
    LeadStage.GATEKEEPER,
    LeadStage.LPR,
    LeadStage.POTENTIAL,
    LeadStage.GONE,
]


class MessageKind(str, enum.Enum):
    """Тип записи в ленте: внутренняя заметка или сообщение клиенту."""

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
    title = db.Column(db.String(200), nullable=False)          # название сделки
    contact_name = db.Column(db.String(120), default="")       # имя контакта (текст)
    phone = db.Column(db.String(40), default="")
    email = db.Column(db.String(120), default="")
    source = db.Column(db.String(60), default="")              # сайт, звонок, рекомендация...
    expected_revenue = db.Column(db.Numeric(14, 2), default=0)  # ожидаемая сумма
    stage = db.Column(db.Enum(LeadStage), nullable=False, default=LeadStage.LEAD)
    priority = db.Column(db.Integer, nullable=False, default=0)  # 0..3 — звёзды
    tags = db.Column(db.String(255), default="")               # теги через запятую
    notes = db.Column(db.Text, default="")

    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    manager = db.relationship("User", back_populates="leads")

    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    company = db.relationship("Company", back_populates="leads")

    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=True)
    contact = db.relationship("Contact", back_populates="leads")

    # Лента общения (новые сверху при выборке с сортировкой)
    messages = db.relationship(
        "LeadMessage", back_populates="lead", lazy="dynamic",
        cascade="all, delete-orphan",
    )

    # Заявки, созданные из лида
    requests = db.relationship(
        "Request", back_populates="lead", lazy="dynamic",
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           onupdate=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)  # резерв: финальных стадий нет, не заполняется

    # ── Хелперы ─────────────────────────────────────────
    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]

    @tag_list.setter
    def tag_list(self, values: list[str]) -> None:
        self.tags = ", ".join(v.strip() for v in values if v.strip())

    def log_stage_change(self, old_stage) -> None:
        """Системная запись в ленту о смене стадии.

        Вызывать после смены self.stage, commit — снаружи.
        """
        if old_stage == self.stage:
            return
        old_title = old_stage.title if old_stage else "—"
        new_title = self.stage.title if self.stage else "—"
        db.session.add(
            LeadMessage(
                lead=self,
                author=None,  # системная запись
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
            "company_id": self.company_id,
            "company_name": self.company.name if self.company else None,
            "contact_id": self.contact_id,
            "contact_name_full": self.contact.full_name if self.contact else None,
            "messages_count": self.messages.count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Lead {self.id} {self.title}>"


class LeadMessage(db.Model):
    """Одна запись в ленте лида (chatter): заметка или сообщение."""

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
