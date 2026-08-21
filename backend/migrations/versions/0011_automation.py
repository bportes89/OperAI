"""Add idempotency to automated tasks.

Revision ID: 0011_automation
Revises: 0010_orchestration
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0011_automation";down_revision:str|None="0010_orchestration";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.add_column("agent_tasks",sa.Column("idempotency_key",sa.String(180),nullable=True));op.create_unique_constraint("uq_agent_task_tenant_idempotency","agent_tasks",["organization_id","idempotency_key"])
def downgrade()->None:op.drop_constraint("uq_agent_task_tenant_idempotency","agent_tasks",type_="unique");op.drop_column("agent_tasks","idempotency_key")
