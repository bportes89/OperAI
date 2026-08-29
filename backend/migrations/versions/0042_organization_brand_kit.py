"""Kit de marca da organização (identidade para Marketing e agentes).

Revision ID: 0042_organization_brand_kit
Revises: 0041_crm_opportunity_source
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0042_organization_brand_kit"
down_revision: str | None = "0041_crm_opportunity_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS organization_brand_kits (
              organization_id UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
              brand_name VARCHAR(120) NOT NULL DEFAULT '',
              tagline VARCHAR(240) NOT NULL DEFAULT '',
              voice_tone TEXT NOT NULL DEFAULT '',
              primary_color VARCHAR(7) NOT NULL DEFAULT '',
              secondary_color VARCHAR(7) NOT NULL DEFAULT '',
              logo_url VARCHAR(1000) NOT NULL DEFAULT '',
              avoid TEXT NOT NULL DEFAULT '',
              notes TEXT NOT NULL DEFAULT '',
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS organization_brand_kits"))
