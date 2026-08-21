"""Add agent execution observability.

Revision ID: 0022_agent_observability
Revises: 0021_governance_approvals
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0022_agent_observability";down_revision:str|None="0021_governance_approvals";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.create_table("agent_run_metrics",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("task_id",sa.Uuid(),sa.ForeignKey("agent_tasks.id",ondelete="CASCADE"),nullable=False),sa.Column("agent_id",sa.Uuid(),sa.ForeignKey("agents.id",ondelete="SET NULL")),sa.Column("model",sa.String(80),nullable=False,server_default="local-orchestrator"),sa.Column("prompt_tokens",sa.Integer(),nullable=False,server_default="0"),sa.Column("completion_tokens",sa.Integer(),nullable=False,server_default="0"),sa.Column("cost_micros",sa.Integer(),nullable=False,server_default="0"),sa.Column("latency_ms",sa.Integer(),nullable=False,server_default="0"),sa.Column("quality_score",sa.Integer()),sa.Column("evaluation_note",sa.Text()),sa.Column("evaluated_by",sa.Uuid(),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("evaluated_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("organization_id","task_id"));op.create_index("ix_agent_run_metrics_organization_id","agent_run_metrics",["organization_id"]);op.create_index("ix_agent_run_metrics_task_id","agent_run_metrics",["task_id"]);op.create_index("ix_agent_run_metrics_agent_id","agent_run_metrics",["agent_id"]);op.create_index("ix_agent_run_metrics_evaluated_by","agent_run_metrics",["evaluated_by"]);op.create_index("ix_agent_run_metric_tenant_created","agent_run_metrics",["organization_id","created_at"])
def downgrade()->None:op.drop_table("agent_run_metrics")
