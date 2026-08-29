"""Marketing growth: engagement insights, SEO checklist, package upgrades.

Revision ID: 0040_marketing_growth
Revises: 0039_marketing_governance
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0040_marketing_growth"
down_revision: str | None = "0039_marketing_governance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_column_if_missing(table: str, column: str, ddl: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$ BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = '{table}' AND column_name = '{column}'
              ) THEN
                ALTER TABLE {table} ADD COLUMN {ddl};
              END IF;
            END $$;
            """
        )
    )


def upgrade() -> None:
    _add_column_if_missing(
        "marketing_governance",
        "seo_checklist",
        "seo_checklist JSON NOT NULL DEFAULT '{}'",
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS marketing_engagements (
              id UUID PRIMARY KEY,
              organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
              created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              campaign_id UUID REFERENCES marketing_campaigns(id) ON DELETE SET NULL,
              channel VARCHAR(30) NOT NULL DEFAULT 'social',
              label VARCHAR(180) NOT NULL,
              views INTEGER NOT NULL DEFAULT 0,
              clicks INTEGER NOT NULL DEFAULT 0,
              likes INTEGER NOT NULL DEFAULT 0,
              comments INTEGER NOT NULL DEFAULT 0,
              best_day VARCHAR(40),
              audience_note TEXT,
              recommendation TEXT,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_marketing_engagement_tenant_created
            ON marketing_engagements (organization_id, created_at);
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS marketing_engagements"))
