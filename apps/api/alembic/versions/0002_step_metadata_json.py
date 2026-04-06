"""add structured step metadata json

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orchestration_steps", sa.Column("step_metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("orchestration_steps", "step_metadata_json")
