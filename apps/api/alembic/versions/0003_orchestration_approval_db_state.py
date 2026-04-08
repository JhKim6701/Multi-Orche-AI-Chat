"""persist approval state on orchestration run

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orchestration_runs", sa.Column("approval_status", sa.String(length=40), nullable=True))
    op.add_column("orchestration_runs", sa.Column("pending_payload_json", sa.JSON(), nullable=True))
    op.add_column("orchestration_runs", sa.Column("approval_decided_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("orchestration_runs", "approval_decided_at")
    op.drop_column("orchestration_runs", "pending_payload_json")
    op.drop_column("orchestration_runs", "approval_status")
