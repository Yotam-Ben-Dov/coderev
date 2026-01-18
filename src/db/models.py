"""SQLAlchemy models for CodeRev."""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Base Classes and Mixins
# =============================================================================


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin that adds soft delete support."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
        index=True,
    )

    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark the record as deleted."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None


# =============================================================================
# Enums
# =============================================================================


class ReviewStatus(str, Enum):
    """Status of a code review."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewVerdict(str, Enum):
    """Verdict of a code review."""

    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    COMMENT = "comment"


class CommentCategory(str, Enum):
    """Category of a review comment."""

    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    SUGGESTION = "suggestion"
    DOCUMENTATION = "documentation"


class CommentSeverity(str, Enum):
    """Severity of a review comment."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


# =============================================================================
# Models
# =============================================================================


class Repository(Base, TimestampMixin, SoftDeleteMixin):
    """A GitHub repository being tracked for code reviews."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # GitHub identifiers
    github_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)

    # Settings (JSON for flexibility)
    settings: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default="{}",
    )

    # Relationships
    reviews: Mapped[list["Review"]] = relationship(
        "Review",
        back_populates="repository",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (Index("ix_repositories_owner_name", "owner", "name"),)

    def __repr__(self) -> str:
        return f"<Repository {self.full_name}>"


class Review(Base, TimestampMixin, SoftDeleteMixin):
    """A code review for a pull request."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    repository_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Pull request info
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pr_title: Mapped[str] = mapped_column(String(500), nullable=False)
    pr_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    head_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    base_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Review status and results
    status: Mapped[ReviewStatus] = mapped_column(
        String(50),
        default=ReviewStatus.PENDING,
        nullable=False,
    )
    verdict: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Files reviewed
    files_reviewed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # LLM tracking
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Performance tracking
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # GitHub integration
    github_review_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Completion timestamp
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(
        "Repository",
        back_populates="reviews",
    )
    comments: Mapped[list["ReviewComment"]] = relationship(
        "ReviewComment",
        back_populates="review",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_reviews_repository_pr", "repository_id", "pr_number"),
        Index("ix_reviews_status", "status"),
        Index("ix_reviews_created_at", "created_at"),
        Index("ix_reviews_head_sha", "head_sha"),
    )

    @property
    def is_complete(self) -> bool:
        """Check if the review is complete."""
        return self.status in (ReviewStatus.COMPLETED, ReviewStatus.FAILED)

    def __repr__(self) -> str:
        return f"<Review #{self.pr_number} ({self.status})>"


class ReviewComment(Base, TimestampMixin):
    """An individual comment from a code review."""

    __tablename__ = "review_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    review_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Comment location
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Comment content
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)

    # Agent tracking (for multi-agent system)
    agent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    review: Mapped["Review"] = relationship(
        "Review",
        back_populates="comments",
    )

    # Indexes
    __table_args__ = (
        Index("ix_review_comments_review_id", "review_id"),
        Index("ix_review_comments_category", "category"),
        Index("ix_review_comments_severity", "severity"),
    )

    def __repr__(self) -> str:
        return f"<ReviewComment {self.file_path}:{self.line_number}>"


class PromptVersion(Base, TimestampMixin, SoftDeleteMixin):
    """Versioned prompts for A/B testing."""

    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Version identifier
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Prompt content
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)

    # Targeting (which agent/use case)
    agent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # A/B testing
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)
    traffic_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Performance metrics (aggregated)
    total_uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_tokens: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Indexes
    __table_args__ = (
        Index("ix_prompt_versions_active", "is_active"),
        Index("ix_prompt_versions_agent_type", "agent_type"),
    )

    def __repr__(self) -> str:
        return f"<PromptVersion {self.version}>"


# =============================================================================
# Event Listeners
# =============================================================================


@event.listens_for(Review, "before_update")
def update_review_totals(mapper, connection, target: Review) -> None:  # noqa: ARG001
    """Update computed fields before saving."""
    target.tokens_total = target.tokens_input + target.tokens_output
