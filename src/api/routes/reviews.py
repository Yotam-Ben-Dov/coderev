"""Review API endpoints."""

from typing import Any

import structlog
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.db.repositories import ReviewRepository
from src.services.review.pipeline import ReviewPipeline
from src.worker.celery_app import celery_app
from src.worker.tasks.review_tasks import process_review

router = APIRouter()
logger = structlog.get_logger()


# =============================================================================
# Request/Response Models
# =============================================================================


class ReviewRequest(BaseModel):
    """Request to trigger a code review."""

    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    pr_number: int = Field(..., gt=0, description="Pull request number")
    post_review: bool = Field(
        default=True,
        description="Whether to post the review to GitHub",
    )
    async_mode: bool = Field(
        default=True,
        description="Process asynchronously via task queue",
    )


class ReviewResponse(BaseModel):
    """Response after triggering a review."""

    review_id: int | None = None
    task_id: str | None = None
    pr_number: int
    pr_title: str | None = None
    status: str
    files_reviewed: int | None = None
    total_comments: int | None = None
    verdict: str | None = None
    summary: str | None = None
    model_used: str | None = None
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    review_posted: bool | None = None
    github_review_id: int | None = None


class TaskStatusResponse(BaseModel):
    """Response for task status check."""

    task_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None


class ReviewStatsResponse(BaseModel):
    """Response for review statistics."""

    total_reviews: int
    total_cost_usd: float
    total_tokens: int
    avg_latency_ms: float
    avg_cost_usd: float
    period_days: int


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_review(
    request: ReviewRequest,
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """
    Trigger a code review for a pull request.

    By default, reviews are processed asynchronously via the task queue.
    Set async_mode=false for synchronous processing (useful for testing).
    """
    logger.info(
        "Review requested",
        owner=request.owner,
        repo=request.repo,
        pr_number=request.pr_number,
        async_mode=request.async_mode,
    )

    if request.async_mode:
        # Queue task to Celery
        task = process_review.delay(
            owner=request.owner,
            repo=request.repo,
            pr_number=request.pr_number,
            post_review=request.post_review,
        )

        return ReviewResponse(
            task_id=task.id,
            pr_number=request.pr_number,
            status="queued",
        )

    # Synchronous processing
    pipeline = ReviewPipeline(session=db)

    try:
        result = await pipeline.execute(
            owner=request.owner,
            repo=request.repo,
            pr_number=request.pr_number,
            post_review=request.post_review,
        )
    except Exception as e:
        logger.error("Review failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
    finally:
        await pipeline.close()

    return ReviewResponse(
        review_id=result.review_id,
        pr_number=result.pr_number,
        pr_title=result.pr_title,
        status="completed",
        files_reviewed=result.files_reviewed,
        total_comments=result.total_comments,
        verdict=result.verdict,
        summary=result.summary,
        model_used=result.model_used,
        total_tokens=result.total_tokens,
        total_cost_usd=result.total_cost_usd,
        review_posted=result.review_posted,
        github_review_id=result.github_review_id,
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Get the status of an async review task.

    Possible statuses:
    - PENDING: Task is waiting to be processed
    - STARTED: Task has started processing
    - SUCCESS: Task completed successfully
    - FAILURE: Task failed
    - RETRY: Task is being retried
    """
    task_result = AsyncResult(task_id, app=celery_app)

    response = TaskStatusResponse(
        task_id=task_id,
        status=task_result.status,
    )

    if task_result.successful():
        response.result = task_result.result
    elif task_result.failed():
        response.error = str(task_result.result)

    return response


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Get a review by ID."""
    repo = ReviewRepository(db)
    review = await repo.get_by_id(review_id)

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review {review_id} not found",
        )

    return ReviewResponse(
        review_id=review.id,
        pr_number=review.pr_number,
        pr_title=review.pr_title,
        status=review.status,
        files_reviewed=review.files_reviewed,
        total_comments=review.total_comments,
        verdict=review.verdict,
        summary=review.summary,
        model_used=review.model_used,
        total_tokens=review.tokens_total,
        total_cost_usd=review.cost_usd,
        review_posted=review.github_review_id is not None,
        github_review_id=review.github_review_id,
    )


@router.get("/stats/summary", response_model=ReviewStatsResponse)
async def get_review_stats(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
) -> ReviewStatsResponse:
    """Get review statistics."""
    repo = ReviewRepository(db)
    stats = await repo.get_stats(days=days)

    return ReviewStatsResponse(**stats)
