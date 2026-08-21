"""Add webhook dispatch retry metadata.

Revision ID: 0019_webhook_dispatch
Revises: 0018_billing_invoices
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0019_webhook_dispatch";down_revision:str|None="0018_billing_invoices";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.add_column("webhook_deliveries",sa.Column("response_status",sa.Integer(),nullable=True));op.add_column("webhook_deliveries",sa.Column("next_attempt_at",sa.DateTime(timezone=True),nullable=True));op.create_index("ix_webhook_delivery_retry","webhook_deliveries",["status","next_attempt_at"])
def downgrade()->None:
    op.drop_index("ix_webhook_delivery_retry",table_name="webhook_deliveries");op.drop_column("webhook_deliveries","next_attempt_at");op.drop_column("webhook_deliveries","response_status")
