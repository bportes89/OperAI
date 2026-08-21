"""Add persistent agent conversations.

Revision ID: 0005_conversations
Revises: 0004_embeddings
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0005_conversations";down_revision:str|None="0004_embeddings";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.create_table("conversations",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("agent_id",sa.Uuid(),sa.ForeignKey("agents.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",sa.Uuid(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("title",sa.String(180),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_conversations_organization_id","conversations",["organization_id"]);op.create_index("ix_conversations_agent_id","conversations",["agent_id"]);op.create_index("ix_conversations_user_id","conversations",["user_id"]);op.create_index("ix_conversation_tenant_agent","conversations",["organization_id","agent_id"])
    op.create_table("conversation_messages",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("conversation_id",sa.Uuid(),sa.ForeignKey("conversations.id",ondelete="CASCADE"),nullable=False),sa.Column("role",sa.String(20),nullable=False),sa.Column("content",sa.Text(),nullable=False),sa.Column("sources",sa.JSON(),nullable=True),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_conversation_messages_organization_id","conversation_messages",["organization_id"]);op.create_index("ix_conversation_messages_conversation_id","conversation_messages",["conversation_id"]);op.create_index("ix_message_tenant_conversation","conversation_messages",["organization_id","conversation_id"])
def downgrade()->None:op.drop_table("conversation_messages");op.drop_table("conversations")
