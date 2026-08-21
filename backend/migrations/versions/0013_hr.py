"""Add HR employees and leave requests.

Revision ID: 0013_hr
Revises: 0012_marketing
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision:str="0013_hr";down_revision:str|None="0012_marketing";branch_labels:str|Sequence[str]|None=None;depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.create_table("employees",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("name",sa.String(160),nullable=False),sa.Column("email",sa.String(255),nullable=False),sa.Column("department",sa.String(120),nullable=False),sa.Column("job_title",sa.String(120),nullable=False),sa.Column("hired_at",sa.Date(),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("organization_id","email"));op.create_index("ix_employees_organization_id","employees",["organization_id"]);op.create_index("ix_employee_tenant_status","employees",["organization_id","status"])
    op.create_table("leave_requests",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("organization_id",sa.Uuid(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("employee_id",sa.Uuid(),sa.ForeignKey("employees.id",ondelete="CASCADE"),nullable=False),sa.Column("leave_type",sa.String(30),nullable=False),sa.Column("starts_on",sa.Date(),nullable=False),sa.Column("ends_on",sa.Date(),nullable=False),sa.Column("reason",sa.Text(),nullable=True),sa.Column("status",sa.String(30),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False));op.create_index("ix_leave_requests_organization_id","leave_requests",["organization_id"]);op.create_index("ix_leave_requests_employee_id","leave_requests",["employee_id"]);op.create_index("ix_leave_tenant_status","leave_requests",["organization_id","status"])
def downgrade()->None:op.drop_table("leave_requests");op.drop_table("employees")
