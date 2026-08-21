"""Add governed marketing campaigns.

Revision ID: 0012_marketing
Revises: 0011_automation
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0012_marketing";down_revision:str|None="0011_automation";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.create_table("marketing_campaigns",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("created_by",sa.Uuid(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("agent_id",sa.Uuid(),sa.ForeignKey("agents.id",ondelete="SET NULL"),nullable=True),sa.Column("name",sa.String(180),nullable=False),sa.Column("channel",sa.String(30),nullable=False),sa.Column("audience",sa.String(240),nullable=False),sa.Column("content",sa.Text(),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("scheduled_at",sa.DateTime(timezone=True),nullable=True),sa.Column("sent_count",sa.Integer(),nullable=False),sa.Column("delivered_count",sa.Integer(),nullable=False),sa.Column("response_count",sa.Integer(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False));op.create_index("ix_marketing_campaigns_organization_id","marketing_campaigns",["organization_id"]);op.create_index("ix_marketing_campaigns_created_by","marketing_campaigns",["created_by"]);op.create_index("ix_marketing_campaigns_agent_id","marketing_campaigns",["agent_id"]);op.create_index("ix_marketing_campaign_tenant_status","marketing_campaigns",["organization_id","status"])
def downgrade()->None:op.drop_table("marketing_campaigns")
