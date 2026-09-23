"""Избранные фильтры поиска (таблица saved_filters).

Revision ID: e8f2a4c6d0b3
Revises: c7d3e5f1a9b2

«Избранное» в панели поиска как в Odoo: пользователь сохраняет
текущий набор фильтров под именем и вызывает в один клик.
"""
from alembic import op
import sqlalchemy as sa

revision = "e8f2a4c6d0b3"
down_revision = "c7d3e5f1a9b2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "saved_filters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("target", sa.String(20), nullable=False, server_default="leads"),
        sa.Column("params", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("saved_filters")
