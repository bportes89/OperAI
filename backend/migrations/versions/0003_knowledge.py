"""Add knowledge documents and chunks.

Revision ID: 0003_knowledge
Revises: 0002_agents
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0003_knowledge";down_revision:str|None="0002_agents";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.create_table("knowledge_documents",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("title",sa.String(180),nullable=False),sa.Column("source_type",sa.String(30),nullable=False),sa.Column("content",sa.Text(),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("chunk_count",sa.Integer(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_knowledge_documents_organization_id","knowledge_documents",["organization_id"]);op.create_index("ix_knowledge_document_tenant_status","knowledge_documents",["organization_id","status"])
    op.create_table("knowledge_chunks",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("document_id",sa.Uuid(),sa.ForeignKey("knowledge_documents.id",ondelete="CASCADE"),nullable=False),sa.Column("position",sa.Integer(),nullable=False),sa.Column("content",sa.Text(),nullable=False),sa.UniqueConstraint("document_id","position"))
    op.create_index("ix_knowledge_chunks_organization_id","knowledge_chunks",["organization_id"]);op.create_index("ix_knowledge_chunks_document_id","knowledge_chunks",["document_id"]);op.create_index("ix_knowledge_chunk_tenant_document","knowledge_chunks",["organization_id","document_id"])
def downgrade()->None:op.drop_table("knowledge_chunks");op.drop_table("knowledge_documents")
