"""Add agent task orchestration.

Revision ID: 0010_orchestration
Revises: 0009_proposals
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0010_orchestration";down_revision:str|None="0009_proposals";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.create_table("agent_tasks",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("agent_id",sa.Uuid(),sa.ForeignKey("agents.id",ondelete="SET NULL"),nullable=True),sa.Column("created_by",sa.Uuid(),sa.ForeignKey("users.id",ondelete="SET NULL"),nullable=True),sa.Column("task_type",sa.String(60),nullable=False),sa.Column("title",sa.String(180),nullable=False),sa.Column("priority",sa.String(20),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("input_data",sa.JSON(),nullable=False),sa.Column("result_data",sa.JSON(),nullable=True),sa.Column("error",sa.Text(),nullable=True),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("started_at",sa.DateTime(timezone=True),nullable=True),sa.Column("completed_at",sa.DateTime(timezone=True),nullable=True));op.create_index("ix_agent_tasks_organization_id","agent_tasks",["organization_id"]);op.create_index("ix_agent_tasks_agent_id","agent_tasks",["agent_id"]);op.create_index("ix_agent_tasks_created_by","agent_tasks",["created_by"]);op.create_index("ix_agent_task_tenant_status","agent_tasks",["organization_id","status"])
def downgrade()->None:op.drop_table("agent_tasks")
