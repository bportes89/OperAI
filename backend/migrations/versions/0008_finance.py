"""Add accounts receivable and payments.

Revision ID: 0008_finance
Revises: 0007_calendar
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0008_finance";down_revision:str|None="0007_calendar";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.create_table("receivables",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("contact_id",sa.Uuid(),sa.ForeignKey("contacts.id",ondelete="SET NULL"),nullable=True),sa.Column("created_by",sa.Uuid(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("customer_name",sa.String(180),nullable=False),sa.Column("description",sa.String(240),nullable=False),sa.Column("amount_cents",sa.Integer(),nullable=False),sa.Column("due_date",sa.Date(),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("paid_at",sa.DateTime(timezone=True),nullable=True),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False));op.create_index("ix_receivables_organization_id","receivables",["organization_id"]);op.create_index("ix_receivables_contact_id","receivables",["contact_id"]);op.create_index("ix_receivables_created_by","receivables",["created_by"]);op.create_index("ix_receivable_tenant_due","receivables",["organization_id","due_date"])
    op.create_table("receivable_payments",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("receivable_id",sa.Uuid(),sa.ForeignKey("receivables.id",ondelete="CASCADE"),nullable=False),sa.Column("amount_cents",sa.Integer(),nullable=False),sa.Column("method",sa.String(30),nullable=False),sa.Column("paid_at",sa.DateTime(timezone=True),nullable=False),sa.Column("created_by",sa.Uuid(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False));op.create_index("ix_receivable_payments_organization_id","receivable_payments",["organization_id"]);op.create_index("ix_receivable_payments_receivable_id","receivable_payments",["receivable_id"]);op.create_index("ix_receivable_payments_created_by","receivable_payments",["created_by"])
def downgrade()->None:op.drop_table("receivable_payments");op.drop_table("receivables")
