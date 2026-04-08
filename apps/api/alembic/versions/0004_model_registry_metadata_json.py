"""add metadata_json to model_registry

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_registry", sa.Column("metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("model_registry", "metadata_json")

