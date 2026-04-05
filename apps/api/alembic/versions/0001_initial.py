"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-05
"""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


roleenum = sa.Enum("user", "assistant", "system", "orchestrator", name="roleenum")


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "chat_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("chat_thread_id", sa.Integer(), sa.ForeignKey("chat_threads.id"), nullable=False),
        sa.Column("role", roleenum, nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("plain_text_cache", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("model_role", sa.String(length=120), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("chat_thread_id", sa.Integer(), sa.ForeignKey("chat_threads.id"), nullable=False),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("asset_type", sa.String(length=50), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False),
        sa.Column("derived_metadata_json", sa.JSON(), nullable=True),
        sa.Column("producing_model", sa.String(length=120), nullable=True),
        sa.Column("producing_role", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


    op.create_table(
        "asset_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("chat_thread_id", sa.Integer(), sa.ForeignKey("chat_threads.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "model_registry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_name", sa.String(length=140), nullable=False, unique=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("downloaded", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("supports_vision", sa.Boolean(), nullable=False),
        sa.Column("supports_tools", sa.Boolean(), nullable=False),
        sa.Column("supports_embeddings", sa.Boolean(), nullable=False),
        sa.Column("supports_reasoning", sa.Boolean(), nullable=False),
        sa.Column("preferred_roles_json", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "orchestration_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("chat_thread_id", sa.Integer(), sa.ForeignKey("chat_threads.id"), nullable=False),
        sa.Column("user_message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("graph_name", sa.String(length=100), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("final_message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=True),
    )

    op.create_table(
        "orchestration_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("orchestration_run_id", sa.Integer(), sa.ForeignKey("orchestration_runs.id"), nullable=False),
        sa.Column("step_name", sa.String(length=100), nullable=False),
        sa.Column("assigned_role", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
    )

    op.create_index("ix_projects_name", "projects", ["name"])
    op.create_index("ix_chat_threads_project_id", "chat_threads", ["project_id"])
    op.create_index("ix_messages_chat_thread_id", "messages", ["chat_thread_id"])
    op.create_index("ix_messages_chat_sequence", "messages", ["chat_thread_id", "sequence_no"])
    op.create_index("ix_assets_chat_thread_id", "assets", ["chat_thread_id"])
    op.create_index("ix_model_registry_model_name", "model_registry", ["model_name"], unique=True)
    op.create_index("ix_asset_chunks_asset_id", "asset_chunks", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_model_registry_model_name", table_name="model_registry")
    op.drop_index("ix_asset_chunks_asset_id", table_name="asset_chunks")
    op.drop_index("ix_assets_chat_thread_id", table_name="assets")
    op.drop_index("ix_messages_chat_sequence", table_name="messages")
    op.drop_index("ix_messages_chat_thread_id", table_name="messages")
    op.drop_index("ix_chat_threads_project_id", table_name="chat_threads")
    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_table("orchestration_steps")
    op.drop_table("orchestration_runs")
    op.drop_table("model_registry")
    op.drop_table("asset_chunks")
    op.drop_table("assets")
    op.drop_table("messages")
    op.drop_table("chat_threads")
    op.drop_table("projects")
    roleenum.drop(op.get_bind(), checkfirst=False)
