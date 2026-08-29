"""Align Start plan agent limit with the 4 product presets.

Revision ID: 0043_plan_limits_start
Revises: 0042_organization_brand_kit
"""
from collections.abc import Sequence
import json
import sqlalchemy as sa
from alembic import op

revision: str = "0043_plan_limits_start"
down_revision: str | None = "0042_organization_brand_kit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Start precisa dos 4 tipos de agente do produto (Gestor, WA, Comercial, Cobrança)
    op.execute(
        sa.text(
            """
            UPDATE saas_plans
            SET limits = CAST(:limits AS json),
                features = CAST(:features AS json)
            WHERE slug = 'start'
            """
        ).bindparams(
            limits=json.dumps({"agents": 4, "users": 2, "documents": 50}),
            features=json.dumps(
                ["4 agentes", "atendimento", "conhecimento", "BYOK"]
            ),
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE saas_plans
            SET limits = CAST(:limits AS json),
                features = CAST(:features AS json)
            WHERE slug = 'start'
            """
        ).bindparams(
            limits=json.dumps({"agents": 1, "users": 2, "documents": 50}),
            features=json.dumps(["atendimento", "conhecimento", "BYOK"]),
        )
    )
