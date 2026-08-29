"""CRM: origem de campanha nas oportunidades.

Revision ID: 0041_crm_opportunity_source
Revises: 0040_marketing_growth
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0041_crm_opportunity_source"
down_revision: str | None = "0040_marketing_growth"
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
    _add_column_if_missing("opportunities", "source_title", "source_title VARCHAR(180)")
    _add_column_if_missing("opportunities", "source_channel", "source_channel VARCHAR(40)")
    _add_column_if_missing(
        "opportunities",
        "source_campaign_id",
        "source_campaign_id UUID REFERENCES marketing_campaigns(id) ON DELETE SET NULL",
    )
    op.execute(
        sa.text(
            """
            DO $$ BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'ix_opportunities_source_campaign_id'
              ) THEN
                CREATE INDEX ix_opportunities_source_campaign_id ON opportunities (source_campaign_id);
              END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_opportunities_source_campaign_id"))
    op.execute(sa.text("ALTER TABLE opportunities DROP COLUMN IF EXISTS source_campaign_id"))
    op.execute(sa.text("ALTER TABLE opportunities DROP COLUMN IF EXISTS source_channel"))
    op.execute(sa.text("ALTER TABLE opportunities DROP COLUMN IF EXISTS source_title"))
