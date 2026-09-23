"""Индексы для фильтров и сортировок.

Поля, по которым постоянно строятся WHERE/ORDER BY (поиск, фильтры,
канбан, списки). Без индексов каждый такой запрос сканирует всю таблицу.

Revision ID: a3f5d9c21e77
Revises: e8f2a4c6d0b3
"""
from alembic import op

revision = "a3f5d9c21e77"
down_revision = "e8f2a4c6d0b3"
branch_labels = None
depends_on = None


def upgrade():
    # Лиды: стадия/менеджер — фильтры и группировка, created/updated — сортировки
    op.create_index("ix_leads_stage", "leads", ["stage"])
    op.create_index("ix_leads_manager_id", "leads", ["manager_id"])
    op.create_index("ix_leads_priority", "leads", ["priority"])
    op.create_index("ix_leads_created_at", "leads", ["created_at"])
    op.create_index("ix_leads_updated_at", "leads", ["updated_at"])
    # Заявки: статус/продавец — фильтры и канбан, даты — сортировки
    op.create_index("ix_shipments_status", "shipments", ["status"])
    op.create_index("ix_shipments_manager_id", "shipments", ["manager_id"])
    op.create_index("ix_shipments_updated_at", "shipments", ["updated_at"])
    op.create_index("ix_shipments_load_date", "shipments", ["load_date"])
    # Избранные фильтры всегда выбираются по пользователю + разделу
    op.create_index("ix_saved_filters_user_target", "saved_filters", ["user_id", "target"])
    # Контакты — по компании
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"])


def downgrade():
    op.drop_index("ix_contacts_company_id", table_name="contacts")
    op.drop_index("ix_saved_filters_user_target", table_name="saved_filters")
    op.drop_index("ix_shipments_load_date", table_name="shipments")
    op.drop_index("ix_shipments_updated_at", table_name="shipments")
    op.drop_index("ix_shipments_manager_id", table_name="shipments")
    op.drop_index("ix_shipments_status", table_name="shipments")
    op.drop_index("ix_leads_updated_at", table_name="leads")
    op.drop_index("ix_leads_created_at", table_name="leads")
    op.drop_index("ix_leads_priority", table_name="leads")
    op.drop_index("ix_leads_manager_id", table_name="leads")
    op.drop_index("ix_leads_stage", table_name="leads")
