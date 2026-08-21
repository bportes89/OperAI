"""Add tenant-scoped AI agents.

Revision ID: 0002_agents
Revises: 0001_initial
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0002_agents"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table("agents",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("name",sa.String(120),nullable=False),sa.Column("agent_type",sa.String(50),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("model",sa.String(80),nullable=False),sa.Column("instructions",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("organization_id","name"))
    op.create_index("ix_agents_organization_id","agents",["organization_id"])
    op.create_index("ix_agent_tenant_status","agents",["organization_id","status"])

def downgrade() -> None:op.drop_table("agents")
