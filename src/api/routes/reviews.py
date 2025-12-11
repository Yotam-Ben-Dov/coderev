import structlog
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

router = APIRouter()
logger = structlog.get_logger()


class ReviewRequest(BaseModel):
    """Request to trigger a manual code review."""

    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    pr_number: int = Field(..., gt=0, description="Pull request number")


class ReviewResponse(BaseModel):
    """Response after queuing a review."""

    message: str
    review_id: str | None = None


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_review(request: ReviewRequest) -> ReviewResponse:
    """
    Manually trigger a code review for a pull request.
    
    This endpoint allows users to request a review via API
    instead of waiting for a webhook event.
    """
    logger.info(
        "Manual review requested",
        owner=request.owner,
        repo=request.repo,
        pr_number=request.pr_number,
    )

    # TODO: Queue review task and return review_id
    return ReviewResponse(
        message=f"Review queued for {request.owner}/{request.repo}#{request.pr_number}",
        review_id=None,  # Will be implemented with Celery
    )


@router.get("/{review_id}")
async def get_review_status(review_id: str) -> dict:
    """
    Get the status of a queued review.
    
    TODO: Implement once database layer is ready.
    """
    return {
        "review_id": review_id,
        "status": "not_implemented",
    }