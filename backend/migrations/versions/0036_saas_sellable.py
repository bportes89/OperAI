"""Sellable SaaS plans, Asaas fields, LLM credentials, onboarding, Evolution channels.

Revision ID: 0036_saas_sellable
Revises: 0035_decision_room
"""
from collections.abc import Sequence
import json
import sqlalchemy as sa
from alembic import op

revision: str = "0036_saas_sellable"
down_revision: str | None = "0035_decision_room"
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
        "organization_subscriptions",
        "asaas_customer_id",
        "asaas_customer_id VARCHAR(80)",
    )
    _add_column_if_missing(
        "organization_subscriptions",
        "asaas_subscription_id",
        "asaas_subscription_id VARCHAR(80)",
    )
    _add_column_if_missing(
        "organization_subscriptions",
        "trial_ends_at",
        "trial_ends_at DATE",
    )

    plans = [
        (
            "start",
            19700,
            {"agents": 1, "users": 2, "documents": 50},
            ["atendimento", "conhecimento", "BYOK"],
        ),
        (
            "pro",
            39700,
            {"agents": 4, "users": 5, "documents": 500},
            ["4 agentes", "CRM", "cobrança", "marketing"],
        ),
        (
            "business",
            79700,
            {"agents": 10, "users": 20, "documents": 5000},
            ["Todos do Pro", "limites ampliados", "equipe"],
        ),
    ]
    for slug, price, limits, features in plans:
        op.execute(
            sa.text(
                """
                UPDATE saas_plans
                SET monthly_price_cents = :price,
                    limits = CAST(:limits AS json),
                    features = CAST(:features AS json),
                    active = true
                WHERE slug = :slug
                """
            ).bindparams(
                slug=slug,
                price=price,
                limits=json.dumps(limits),
                features=json.dumps(features),
            )
        )

    op.execute(
        sa.text(
            """
            UPDATE saas_plans
            SET active = false
            WHERE slug = 'enterprise'
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS llm_credentials (
              id UUID PRIMARY KEY,
              organization_id UUID NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
              provider VARCHAR(40) NOT NULL,
              model_name VARCHAR(120) NOT NULL,
              api_key_encrypted TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_llm_credentials_organization_id
            ON llm_credentials (organization_id)
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS organization_onboarding (
              organization_id UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
              step VARCHAR(40) NOT NULL DEFAULT 'welcome',
              completed_at TIMESTAMPTZ,
              checklist JSON NOT NULL DEFAULT '{}'::json
            )
            """
        )
    )

    _add_column_if_missing("channels", "provider", "provider VARCHAR(40) NOT NULL DEFAULT 'webhook'")
    _add_column_if_missing("channels", "instance_name", "instance_name VARCHAR(120)")
    _add_column_if_missing("channels", "config", "config JSON")


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE channels DROP COLUMN IF EXISTS config"))
    op.execute(sa.text("ALTER TABLE channels DROP COLUMN IF EXISTS instance_name"))
    op.execute(sa.text("ALTER TABLE channels DROP COLUMN IF EXISTS provider"))
    op.execute(sa.text("DROP TABLE IF EXISTS organization_onboarding"))
    op.execute(sa.text("DROP TABLE IF EXISTS llm_credentials"))
    op.execute(
        sa.text(
            "ALTER TABLE organization_subscriptions DROP COLUMN IF EXISTS trial_ends_at"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE organization_subscriptions DROP COLUMN IF EXISTS asaas_subscription_id"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE organization_subscriptions DROP COLUMN IF EXISTS asaas_customer_id"
        )
    )
