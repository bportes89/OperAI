"""Add local embeddings to knowledge chunks.

Revision ID: 0004_embeddings
Revises: 0003_knowledge
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0004_embeddings";down_revision:str|None="0003_knowledge";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:op.add_column("knowledge_chunks",sa.Column("embedding",sa.JSON(),nullable=True))
def downgrade()->None:op.drop_column("knowledge_chunks","embedding")
