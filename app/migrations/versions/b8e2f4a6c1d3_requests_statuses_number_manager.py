"""requests: новые статусы заявок, номер, ответственный

Revision ID: b8e2f4a6c1d3
Revises: fed3043032f3
Create Date: 2026-09-22

«Грузоперевозки» -> «Заявки»:
- статусы исполнения (planned/loading/...) -> статусы заявки
  (new/carrier_found/invoiced/paid), данные переезжают маппингом;
- новые колонки: number (З-0001), manager_id (ответственный).
Имена таблиц НЕ меняем (см. models/request.py).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8e2f4a6c1d3'
down_revision = 'fed3043032f3'
branch_labels = None
depends_on = None

# Старые значения -> новые (переезд данных)
STATUS_MAP = {
    'PLANNED': 'NEW',
    'LOADING': 'CARRIER_FOUND',
    'IN_TRANSIT': 'CARRIER_FOUND',
    'UNLOADING': 'CARRIER_FOUND',
    'DELIVERED': 'PAID',
}
NEW_LABELS = ['NEW', 'CARRIER_FOUND', 'INVOICED', 'PAID']


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
                    "WHERE enumtypid = 'shipmentstatus'::regtype"
                )).fetchall()
            }
        with op.get_context().autocommit_block():
            for label in NEW_LABELS:
                if label not in existing:
                    op.execute(sa.text(
                        f"ALTER TYPE shipmentstatus ADD VALUE '{label}'"
                    ))

    # Переезд данных (на SQLite статусы — обычные строки, тот же SQL).
    for old, new in STATUS_MAP.items():
        op.execute(sa.text(
            "UPDATE shipments SET status = :new WHERE status = :old"
        ).bindparams(new=new, old=old))

    with op.batch_alter_table('shipments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('number', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('manager_id', sa.Integer(), nullable=True))
        batch_op.create_unique_constraint('uq_shipments_number', ['number'])
        batch_op.create_foreign_key('fk_shipments_manager_id', 'users', ['manager_id'], ['id'])

    # Номера существующим строкам: З-0001, З-0002... (формат — в Python,
    # т.к. LPAD есть только в PostgreSQL).
    # В offline-режиме (--sql) SELECT выполнять не на чем (мок возвращает None),
    # поэтому бэкфилл пропускаем: для просмотра SQL он не нужен.
    if op.get_context().as_sql:
        op.execute(sa.text("-- offline: backfill number З-%04d пропущен (см. комментарий в миграции)"))
    else:
        connection = op.get_bind()
        rows = connection.execute(sa.text("SELECT id FROM shipments ORDER BY id")).fetchall()
        for (row_id,) in rows:
            connection.execute(
                sa.text("UPDATE shipments SET number = :number WHERE id = :id"),
                {"number": f"З-{row_id:04d}", "id": row_id},
            )


def downgrade():
    # Обратный маппинг (приблизительный: invoiced/paid -> delivered).
    for old, new in {'NEW': 'PLANNED', 'CARRIER_FOUND': 'IN_TRANSIT',
                     'INVOICED': 'DELIVERED', 'PAID': 'DELIVERED'}.items():
        op.execute(sa.text(
            "UPDATE shipments SET status = :old WHERE status = :new"
        ).bindparams(old=old, new=new))

    with op.batch_alter_table('shipments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_shipments_manager_id', type_='foreignkey')
        batch_op.drop_constraint('uq_shipments_number', type_='unique')
        batch_op.drop_column('manager_id')
        batch_op.drop_column('number')

    # Убрать добавленные метки из типа shipmentstatus PostgreSQL не умеет
    # (нужно пересоздавать тип) — они просто останутся неиспользуемыми.
