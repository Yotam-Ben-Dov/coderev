from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.services.review.pipeline import ReviewPipeline

router = APIRouter()
logger = structlog.get_logger()


class ReviewRequest(BaseModel):
    """Request to trigger a manual code review."""

    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    pr_number: int = Field(..., gt=0, description="Pull request number")
    post_review: bool = Field(
        default=True,
        description="Whether to post the review to GitHub",
    )


class ReviewResponse(BaseModel):
    """Response after completing a review."""

    pr_number: int
    pr_title: str
    files_reviewed: int
    total_comments: int
    verdict: str
    summary: str
    model_used: str
    total_tokens: int
    total_cost_usd: float
    review_posted: bool
    github_review_id: int | None = None


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
)
async def trigger_review(request: ReviewRequest) -> ReviewResponse:
    """
    Trigger a code review for a pull request.

    This endpoint:
    1. Fetches the PR diff from GitHub
    2. Parses and filters Python files
    3. Sends each file to the LLM for review
    4. Posts the review back to GitHub (if post_review=True)
    """
    logger.info(
        "Review requested",
        owner=request.owner,
        repo=request.repo,
        pr_number=request.pr_number,
    )

    pipeline = ReviewPipeline()

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
        pr_number=result.pr_number,
        pr_title=result.pr_title,
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


@router.get("/{review_id}")
async def get_review_status(review_id: str) -> dict[str, Any]:
    """
    Get the status of a review.

    TODO: Implement once database layer is ready.
    """
    return {
        "review_id": review_id,
        "status": "not_implemented",
    }
