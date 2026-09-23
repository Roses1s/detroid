"""Все модели — импорт для Alembic и удобного доступа.

Активные: User, Lead, LeadMessage, LeadStage, MessageKind, SavedFilter
Legacy (таблицы остаются для совместимости, код не используется): Company, Contact, Request, RequestMessage, RequestStatus
"""

from .company import Company  # legacy
from .contact import Contact  # legacy
from .lead import Lead, LeadMessage, LeadStage, MessageKind
from .request import Request, RequestMessage, RequestStatus  # legacy
from .saved_filter import SavedFilter
from .user import User

__all__ = [
    "User",
    "Lead",
    "LeadStage",
    "LeadMessage",
    "MessageKind",
    "SavedFilter",
    # legacy — не удалять импорт, нужен для миграций
    "Company",
    "Contact",
    "Request",
    "RequestMessage",
    "RequestStatus",
]
