"""Add business calendar.

Revision ID: 0007_calendar
Revises: 0006_inbox
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0007_calendar";down_revision:str|None="0006_inbox";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.create_table("calendar_events",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("created_by",sa.Uuid(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("agent_id",sa.Uuid(),sa.ForeignKey("agents.id",ondelete="SET NULL"),nullable=True),sa.Column("title",sa.String(180),nullable=False),sa.Column("description",sa.Text(),nullable=True),sa.Column("starts_at",sa.DateTime(timezone=True),nullable=False),sa.Column("ends_at",sa.DateTime(timezone=True),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("priority",sa.String(20),nullable=False),sa.Column("reminder_minutes",sa.Integer(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False));op.create_index("ix_calendar_events_organization_id","calendar_events",["organization_id"]);op.create_index("ix_calendar_events_created_by","calendar_events",["created_by"]);op.create_index("ix_calendar_events_agent_id","calendar_events",["agent_id"]);op.create_index("ix_calendar_event_tenant_start","calendar_events",["organization_id","starts_at"])
def downgrade()->None:op.drop_table("calendar_events")
