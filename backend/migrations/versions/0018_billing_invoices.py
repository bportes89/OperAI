"""Add recurring invoices and billing payments.

Revision ID: 0018_billing_invoices
Revises: 0017_saas_billing
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0018_billing_invoices";down_revision:str|None="0017_saas_billing";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.create_table("billing_invoices",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("subscription_id",sa.Uuid(),sa.ForeignKey("organization_subscriptions.id",ondelete="CASCADE"),nullable=False),sa.Column("period",sa.String(7),nullable=False),sa.Column("description",sa.String(240),nullable=False),sa.Column("amount_cents",sa.Integer(),nullable=False),sa.Column("status",sa.String(30),nullable=False,server_default="open"),sa.Column("due_date",sa.Date(),nullable=False),sa.Column("paid_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("organization_id","period"));op.create_index("ix_billing_invoices_organization_id","billing_invoices",["organization_id"]);op.create_index("ix_billing_invoices_subscription_id","billing_invoices",["subscription_id"]);op.create_index("ix_billing_invoice_tenant_status","billing_invoices",["organization_id","status"])
    op.create_table("billing_payments",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("invoice_id",sa.Uuid(),sa.ForeignKey("billing_invoices.id",ondelete="CASCADE"),nullable=False),sa.Column("provider",sa.String(40),nullable=False,server_default="manual"),sa.Column("external_id",sa.String(180)),sa.Column("method",sa.String(30),nullable=False),sa.Column("amount_cents",sa.Integer(),nullable=False),sa.Column("status",sa.String(30),nullable=False,server_default="confirmed"),sa.Column("paid_at",sa.DateTime(timezone=True),nullable=False),sa.Column("created_by",sa.Uuid(),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("provider","external_id"));op.create_index("ix_billing_payments_organization_id","billing_payments",["organization_id"]);op.create_index("ix_billing_payments_invoice_id","billing_payments",["invoice_id"]);op.create_index("ix_billing_payments_created_by","billing_payments",["created_by"])
def downgrade()->None:
    op.drop_table("billing_payments");op.drop_table("billing_invoices")
