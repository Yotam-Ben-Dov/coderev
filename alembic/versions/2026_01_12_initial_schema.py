"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-12 15:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # === repositories table ===
    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("github_id", sa.Integer(), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=512), nullable=False),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("full_name"),
        sa.UniqueConstraint("github_id"),
    )
    op.create_index(
        "ix_repositories_owner_name",
        "repositories",
        ["owner", "name"],
    )
    op.create_index(
        "ix_repositories_deleted_at",
        "repositories",
        ["deleted_at"],
    )

    # === reviews table ===
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("pr_title", sa.String(length=500), nullable=False),
        sa.Column("pr_url", sa.String(length=1000), nullable=True),
        sa.Column("head_sha", sa.String(length=40), nullable=False),
        sa.Column("base_sha", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("verdict", sa.String(length=50), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("files_reviewed", sa.Integer(), nullable=False, default=0),
        sa.Column("total_comments", sa.Integer(), nullable=False, default=0),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=False, default=0),
        sa.Column("tokens_output", sa.Integer(), nullable=False, default=0),
        sa.Column("tokens_total", sa.Integer(), nullable=False, default=0),
        sa.Column("cost_usd", sa.Float(), nullable=False, default=0.0),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("github_review_id", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reviews_repository_pr",
        "reviews",
        ["repository_id", "pr_number"],
    )
    op.create_index("ix_reviews_status", "reviews", ["status"])
    op.create_index("ix_reviews_created_at", "reviews", ["created_at"])
    op.create_index("ix_reviews_head_sha", "reviews", ["head_sha"])
    op.create_index("ix_reviews_deleted_at", "reviews", ["deleted_at"])

    # === review_comments table ===
    op.create_table(
        "review_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("agent_type", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_review_comments_review_id",
        "review_comments",
        ["review_id"],
    )
    op.create_index(
        "ix_review_comments_category",
        "review_comments",
        ["category"],
    )
    op.create_index(
        "ix_review_comments_severity",
        "review_comments",
        ["severity"],
    )

    # === prompt_versions table ===
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("agent_type", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=False),
        sa.Column("traffic_percentage", sa.Integer(), nullable=False, default=0),
        sa.Column("total_uses", sa.Integer(), nullable=False, default=0),
        sa.Column("avg_tokens", sa.Float(), nullable=False, default=0.0),
        sa.Column("avg_cost_usd", sa.Float(), nullable=False, default=0.0),
        sa.Column("avg_latency_ms", sa.Float(), nullable=False, default=0.0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )
    op.create_index(
        "ix_prompt_versions_active",
        "prompt_versions",
        ["is_active"],
    )
    op.create_index(
        "ix_prompt_versions_agent_type",
        "prompt_versions",
        ["agent_type"],
    )
    op.create_index(
        "ix_prompt_versions_deleted_at",
        "prompt_versions",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_table("review_comments")
    op.drop_table("reviews")
    op.drop_table("prompt_versions")
    op.drop_table("repositories")
