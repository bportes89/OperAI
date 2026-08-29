"""Marketing Essencial playbook: diagnosis → discovery → plan.

Revision ID: 0037_marketing_essencial
Revises: 0036_saas_sellable
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0037_marketing_essencial"
down_revision: str | None = "0036_saas_sellable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS marketing_playbooks (
              id UUID PRIMARY KEY,
              organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
              created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
              package VARCHAR(40) NOT NULL DEFAULT 'essencial',
              step VARCHAR(40) NOT NULL DEFAULT 'diagnosis',
              diagnosis JSON NOT NULL DEFAULT '{}',
              discovery JSON NOT NULL DEFAULT '{}',
              diagnosis_summary TEXT,
              action_plan TEXT,
              posts JSON,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              CONSTRAINT uq_marketing_playbooks_org UNIQUE (organization_id)
            );
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_marketing_playbooks_organization_id
            ON marketing_playbooks (organization_id);
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS marketing_playbooks"))
