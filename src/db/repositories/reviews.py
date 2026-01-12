"""Repository for reviews and review comments."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Review, ReviewComment, ReviewStatus
from src.db.repositories.base import BaseRepository


class ReviewRepository(BaseRepository[Review]):
    """Repository for Review model operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Review, session)

    async def get_with_comments(self, id: int) -> Review | None:
        """Get a review with its comments loaded."""
        query = select(Review).options(selectinload(Review.comments)).where(Review.id == id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_pr(
        self,
        repository_id: int,
        pr_number: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[Review]:
        """Get all reviews for a specific PR."""
        query = select(Review).where(
            Review.repository_id == repository_id,
            Review.pr_number == pr_number,
        )

        if not include_deleted:
            query = query.where(Review.deleted_at.is_(None))

        query = query.order_by(Review.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_latest_for_pr(
        self,
        repository_id: int,
        pr_number: int,
    ) -> Review | None:
        """Get the most recent review for a PR."""
        query = (
            select(Review)
            .where(
                Review.repository_id == repository_id,
                Review.pr_number == pr_number,
                Review.deleted_at.is_(None),
            )
            .order_by(Review.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_sha(
        self,
        repository_id: int,
        head_sha: str,
    ) -> Review | None:
        """Get a review by commit SHA."""
        query = select(Review).where(
            Review.repository_id == repository_id,
            Review.head_sha == head_sha,
            Review.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def exists_for_sha(
        self,
        repository_id: int,
        head_sha: str,
    ) -> bool:
        """Check if a review already exists for a commit SHA."""
        query = (
            select(func.count())
            .select_from(Review)
            .where(
                Review.repository_id == repository_id,
                Review.head_sha == head_sha,
                Review.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(query)
        return (result.scalar() or 0) > 0

    async def list_by_repository(
        self,
        repository_id: int,
        *,
        status: ReviewStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[Review]:
        """List reviews for a repository with optional filtering."""
        query = select(Review).where(
            Review.repository_id == repository_id,
            Review.deleted_at.is_(None),
        )

        if status:
            query = query.where(Review.status == status.value)

        query = query.order_by(Review.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_pending(self, limit: int = 100) -> Sequence[Review]:
        """List all pending reviews."""
        query = (
            select(Review)
            .where(
                Review.status == ReviewStatus.PENDING.value,
                Review.deleted_at.is_(None),
            )
            .order_by(Review.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def mark_in_progress(self, id: int) -> Review | None:
        """Mark a review as in progress."""
        return await self.update(id, status=ReviewStatus.IN_PROGRESS.value)

    async def mark_completed(
        self,
        id: int,
        *,
        verdict: str,
        summary: str,
        files_reviewed: int,
        total_comments: int,
        model_used: str,
        tokens_input: int,
        tokens_output: int,
        cost_usd: float,
        latency_ms: int,
        github_review_id: int | None = None,
    ) -> Review | None:
        """Mark a review as completed with results."""
        return await self.update(
            id,
            status=ReviewStatus.COMPLETED.value,
            verdict=verdict,
            summary=summary,
            files_reviewed=files_reviewed,
            total_comments=total_comments,
            model_used=model_used,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            github_review_id=github_review_id,
            completed_at=datetime.now(UTC),
        )

    async def mark_failed(
        self,
        id: int,
        error_message: str,
    ) -> Review | None:
        """Mark a review as failed."""
        return await self.update(
            id,
            status=ReviewStatus.FAILED.value,
            error_message=error_message,
            completed_at=datetime.now(UTC),
        )

    # =========================================================================
    # Analytics Queries
    # =========================================================================

    async def get_stats(
        self,
        repository_id: int | None = None,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Get review statistics.

        Returns:
            Dictionary with total_reviews, total_cost, total_tokens, etc.
        """
        since = datetime.now(UTC) - timedelta(days=days)

        conditions = [
            Review.deleted_at.is_(None),
            Review.created_at >= since,
        ]
        if repository_id:
            conditions.append(Review.repository_id == repository_id)

        query = select(
            func.count(Review.id).label("total_reviews"),
            func.sum(Review.cost_usd).label("total_cost"),
            func.sum(Review.tokens_total).label("total_tokens"),
            func.avg(Review.latency_ms).label("avg_latency_ms"),
            func.avg(Review.cost_usd).label("avg_cost"),
        ).where(and_(*conditions))

        result = await self.session.execute(query)
        row = result.one()

        return {
            "total_reviews": row.total_reviews or 0,
            "total_cost_usd": float(row.total_cost or 0),
            "total_tokens": row.total_tokens or 0,
            "avg_latency_ms": float(row.avg_latency_ms or 0),
            "avg_cost_usd": float(row.avg_cost or 0),
            "period_days": days,
        }

    async def get_cost_by_model(
        self,
        days: int = 30,
    ) -> Sequence[dict[str, Any]]:
        """Get cost breakdown by model."""
        since = datetime.now(UTC) - timedelta(days=days)

        query = (
            select(
                Review.model_used,
                func.count(Review.id).label("review_count"),
                func.sum(Review.cost_usd).label("total_cost"),
                func.sum(Review.tokens_total).label("total_tokens"),
            )
            .where(
                Review.deleted_at.is_(None),
                Review.created_at >= since,
                Review.model_used.isnot(None),
            )
            .group_by(Review.model_used)
            .order_by(func.sum(Review.cost_usd).desc())
        )

        result = await self.session.execute(query)
        return [
            {
                "model": row.model_used,
                "review_count": row.review_count,
                "total_cost_usd": float(row.total_cost or 0),
                "total_tokens": row.total_tokens or 0,
            }
            for row in result.all()
        ]

    async def get_verdict_distribution(
        self,
        repository_id: int | None = None,
        days: int = 30,
    ) -> dict[str, int]:
        """Get distribution of review verdicts."""
        since = datetime.now(UTC) - timedelta(days=days)

        conditions = [
            Review.deleted_at.is_(None),
            Review.created_at >= since,
            Review.verdict.isnot(None),
        ]
        if repository_id:
            conditions.append(Review.repository_id == repository_id)

        query = (
            select(Review.verdict, func.count(Review.id))
            .where(and_(*conditions))
            .group_by(Review.verdict)
        )

        result = await self.session.execute(query)
        return {row[0]: row[1] for row in result.all()}


class ReviewCommentRepository(BaseRepository[ReviewComment]):
    """Repository for ReviewComment model operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ReviewComment, session)

    async def get_by_review(self, review_id: int) -> Sequence[ReviewComment]:
        """Get all comments for a review."""
        query = (
            select(ReviewComment)
            .where(ReviewComment.review_id == review_id)
            .order_by(ReviewComment.file_path, ReviewComment.line_number)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def create_many(
        self,
        review_id: int,
        comments: list[dict[str, Any]],
    ) -> Sequence[ReviewComment]:
        """Create multiple comments at once."""
        instances = [ReviewComment(review_id=review_id, **comment) for comment in comments]
        self.session.add_all(instances)
        await self.session.flush()
        return instances

    async def get_by_category(
        self,
        review_id: int,
        category: str,
    ) -> Sequence[ReviewComment]:
        """Get comments by category."""
        query = select(ReviewComment).where(
            ReviewComment.review_id == review_id,
            ReviewComment.category == category,
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_severity(
        self,
        review_id: int,
        severity: str,
    ) -> Sequence[ReviewComment]:
        """Get comments by severity."""
        query = select(ReviewComment).where(
            ReviewComment.review_id == review_id,
            ReviewComment.severity == severity,
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_by_severity(self, review_id: int) -> dict[str, int]:
        """Count comments by severity for a review."""
        query = (
            select(ReviewComment.severity, func.count(ReviewComment.id))
            .where(ReviewComment.review_id == review_id)
            .group_by(ReviewComment.severity)
        )
        result = await self.session.execute(query)
        return {row[0]: row[1] for row in result.all()}

    async def get_by_agent(
        self,
        review_id: int,
        agent_type: str,
    ) -> Sequence[ReviewComment]:
        """Get comments generated by a specific agent."""
        query = select(ReviewComment).where(
            ReviewComment.review_id == review_id,
            ReviewComment.agent_type == agent_type,
        )
        result = await self.session.execute(query)
        return result.scalars().all()
