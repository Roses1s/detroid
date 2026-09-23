"""stage4 shipment fields company chatter

Revision ID: fed3043032f3
Revises: e81da3fca094
Create Date: 2026-09-22

ЭТАП 4: новые поля перевозки, компания-клиент, лента перевозки.
Отвязка при удалении лида/компании/контакта — на уровне routes
(как у лидов), поэтому существующие FK не трогаем.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'fed3043032f3'
down_revision = 'e81da3fca094'
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    """Есть ли таблица в базе (для идемпотентной миграции)."""
    if op.get_context().as_sql:
        return False  # offline-режим: проверить нельзя, рисуем CREATE TABLE
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade():
    # Тип messagekind обычно уже создан миграцией ленты лидов (e81da3fca094),
    # но на базах, поднятых через create_all, его может не быть.
    # Создаём, ТОЛЬКО если отсутствует (иначе PostgreSQL упадёт).
    bind = op.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        sa.Enum("NOTE", "MESSAGE", name="messagekind").create(bind, checkfirst=True)
    # Таблица могла уже появиться через db.create_all() в seed (мимо миграций)
    # на пострадавших базах — тогда пропускаем создание, чтобы не упасть
    # с "relation/table already exists". Данные при этом не трогаем.
    if not _table_exists("shipment_messages"):
        op.create_table(
            'shipment_messages',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('shipment_id', sa.Integer(), nullable=False),
            sa.Column('author_id', sa.Integer(), nullable=True),
            # ВАЖНО: именно postgresql.ENUM, а не sa.Enum! У обычного sa.Enum
            # флага create_type нет вовсе — он молча игнорируется, и PostgreSQL
            # падает с DuplicateObject (см. named_types.py: _check_for_name_in_memos).
            sa.Column('kind', postgresql.ENUM('NOTE', 'MESSAGE', name='messagekind', create_type=False), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['author_id'], ['users.id']),
            sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
    with op.batch_alter_table('shipments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('client_price', sa.Numeric(precision=14, scale=2), nullable=True))
        batch_op.add_column(sa.Column('carrier', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('driver_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('driver_phone', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('vehicle_number', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('company_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        batch_op.create_foreign_key('fk_shipments_company_id', 'companies', ['company_id'], ['id'])


def downgrade():
    with op.batch_alter_table('shipments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_shipments_company_id', type_='foreignkey')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('company_id')
        batch_op.drop_column('vehicle_number')
        batch_op.drop_column('driver_phone')
        batch_op.drop_column('driver_name')
        batch_op.drop_column('carrier')
        batch_op.drop_column('client_price')

    op.drop_table('shipment_messages')
