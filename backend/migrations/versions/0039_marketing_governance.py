"""Marketing governance: ad ceiling, LGPD consent, crisis, account checklist.

Revision ID: 0039_marketing_governance
Revises: 0038_marketing_conversion
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0039_marketing_governance"
down_revision: str | None = "0038_marketing_conversion"
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
        "marketing_leads",
        "consent_lgpd",
        "consent_lgpd BOOLEAN NOT NULL DEFAULT false",
    )
    _add_column_if_missing(
        "marketing_leads",
        "consent_at",
        "consent_at TIMESTAMPTZ",
    )
    _add_column_if_missing(
        "marketing_leads",
        "is_crisis",
        "is_crisis BOOLEAN NOT NULL DEFAULT false",
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS marketing_governance (
              id UUID PRIMARY KEY,
              organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
              updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
              monthly_ad_ceiling_cents INTEGER NOT NULL DEFAULT 0,
              spent_cents INTEGER NOT NULL DEFAULT 0,
              crisis_escalation BOOLEAN NOT NULL DEFAULT true,
              lgpd_note TEXT,
              account_checklist JSON NOT NULL DEFAULT '{}',
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              CONSTRAINT uq_marketing_governance_org UNIQUE (organization_id)
            );
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_marketing_governance_organization_id
            ON marketing_governance (organization_id);
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS marketing_spend_requests (
              id UUID PRIMARY KEY,
              organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
              created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
              channel VARCHAR(40) NOT NULL,
              description VARCHAR(240) NOT NULL,
              amount_cents INTEGER NOT NULL,
              status VARCHAR(30) NOT NULL DEFAULT 'pending',
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              reviewed_at TIMESTAMPTZ
            );
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_marketing_spend_tenant_status
            ON marketing_spend_requests (organization_id, status);
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS marketing_spend_requests"))
    op.execute(sa.text("DROP TABLE IF EXISTS marketing_governance"))
