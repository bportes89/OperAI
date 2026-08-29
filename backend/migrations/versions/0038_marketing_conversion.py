"""Marketing conversion: interest → lead → CRM handoff.

Revision ID: 0038_marketing_conversion
Revises: 0037_marketing_essencial
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0038_marketing_conversion"
down_revision: str | None = "0037_marketing_essencial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS marketing_leads (
              id UUID PRIMARY KEY,
              organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
              created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              campaign_id UUID REFERENCES marketing_campaigns(id) ON DELETE SET NULL,
              contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
              opportunity_id UUID REFERENCES opportunities(id) ON DELETE SET NULL,
              source_title VARCHAR(180) NOT NULL,
              source_channel VARCHAR(30) NOT NULL DEFAULT 'social',
              contact_name VARCHAR(160) NOT NULL,
              phone VARCHAR(30),
              email VARCHAR(255),
              note TEXT,
              status VARCHAR(30) NOT NULL DEFAULT 'handed_off',
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_marketing_leads_organization_id
            ON marketing_leads (organization_id);
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_marketing_lead_tenant_created
            ON marketing_leads (organization_id, created_at);
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS marketing_leads"))
