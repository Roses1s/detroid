"""Воронка лидов: стадии холодных звонков.

Revision ID: c7d3e5f1a9b2
Revises: b8e2f4a6c1d3

Общая воронка (Новый/Квалификация/Предложение/Выигран/Проигран)
заменяется воронкой холодных звонков:
Лид → Не дозвонились → Не прошёл секретаря → Вышел на ЛПР →
Потенциальный клиент → Уехали.

Переезд данных (в БД лежат ИМЕНА enum, заглавными — так пишет SQLAlchemy):
  NEW → LEAD,  QUALIFICATION → LPR,  PROPOSAL → POTENTIAL,
  WON → POTENTIAL,  LOST → GONE.
Старые метки enum в PostgreSQL остаются в типе мёртвым грузом
(удалить значение из PG-enum нельзя) — это безвредно.
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d3e5f1a9b2"
down_revision = "b8e2f4a6c1d3"
branch_labels = None
depends_on = None

NEW_LABELS = ["LEAD", "NO_ANSWER", "GATEKEEPER", "LPR", "POTENTIAL", "GONE"]

STAGE_MAP = {
    "NEW": "LEAD",
    "QUALIFICATION": "LPR",
    "PROPOSAL": "POTENTIAL",
    "WON": "POTENTIAL",
    "LOST": "GONE",
}

# Обратный переезд (с потерями: POTENTIAL ← PROPOSAL+WON схлопываются)
DOWNGRADE_MAP = {
    "LEAD": "NEW",
    "NO_ANSWER": "NEW",
    "GATEKEEPER": "NEW",
    "LPR": "QUALIFICATION",
    "POTENTIAL": "PROPOSAL",
    "GONE": "LOST",
}


def upgrade():
    bind = op.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        # ALTER TYPE ... ADD VALUE запрещено внутри транзакции,
        # поэтому отдельный autocommit-блок. Добавляем только те
        # метки, которых ещё нет (идемпотентность).
        if op.get_context().as_sql:
            existing = set()  # offline: проверить нельзя, рисуем все ADD VALUE
        else:
            existing = {
                row[0]
                for row in bind.execute(sa.text(
                    "SELECT enumlabel FROM pg_enum "
                    "WHERE enumtypid = 'leadstage'::regtype"
                )).fetchall()
            }
        with op.get_context().autocommit_block():
            for label in NEW_LABELS:
                if label not in existing:
                    op.execute(sa.text(f"ALTER TYPE leadstage ADD VALUE '{label}'"))
    # На SQLite enum хранится обычной строкой — просто переписываем значения.
    # На PG к этому моменту все новые метки уже есть в типе.
    for old, new in STAGE_MAP.items():
        op.execute(
            sa.text("UPDATE leads SET stage = :new WHERE stage = :old")
            .bindparams(new=new, old=old)
        )


def downgrade():
    for new, old in DOWNGRADE_MAP.items():
        op.execute(
            sa.text("UPDATE leads SET stage = :old WHERE stage = :new")
            .bindparams(new=new, old=old)
        )
    # Метки PG-enum не удаляем: PostgreSQL это не умеет.
