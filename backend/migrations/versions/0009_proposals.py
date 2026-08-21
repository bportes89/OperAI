"""Add commercial proposals.

Revision ID: 0009_proposals
Revises: 0008_finance
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0009_proposals";down_revision:str|None="0008_finance";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.create_table("proposals",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("created_by",sa.Uuid(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("opportunity_id",sa.Uuid(),sa.ForeignKey("opportunities.id",ondelete="SET NULL"),nullable=True),sa.Column("customer_name",sa.String(180),nullable=False),sa.Column("title",sa.String(180),nullable=False),sa.Column("notes",sa.Text(),nullable=True),sa.Column("valid_until",sa.Date(),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("total_cents",sa.Integer(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False));op.create_index("ix_proposals_organization_id","proposals",["organization_id"]);op.create_index("ix_proposals_created_by","proposals",["created_by"]);op.create_index("ix_proposals_opportunity_id","proposals",["opportunity_id"]);op.create_index("ix_proposal_tenant_status","proposals",["organization_id","status"])
    op.create_table("proposal_items",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("proposal_id",sa.Uuid(),sa.ForeignKey("proposals.id",ondelete="CASCADE"),nullable=False),sa.Column("description",sa.String(240),nullable=False),sa.Column("quantity",sa.Integer(),nullable=False),sa.Column("unit_price_cents",sa.Integer(),nullable=False),sa.Column("total_cents",sa.Integer(),nullable=False));op.create_index("ix_proposal_items_organization_id","proposal_items",["organization_id"]);op.create_index("ix_proposal_items_proposal_id","proposal_items",["proposal_id"])
def downgrade()->None:op.drop_table("proposal_items");op.drop_table("proposals")
