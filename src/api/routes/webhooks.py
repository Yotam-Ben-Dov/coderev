from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, Request, status
from fastapi.responses import JSONResponse

from src.services.review.pipeline import ReviewPipeline

router = APIRouter()
logger = structlog.get_logger()


async def process_pr_review(owner: str, repo: str, pr_number: int) -> None:
    """Background task to process a PR review."""
    logger.info(
        "Processing PR review in background",
        owner=owner,
        repo=repo,
        pr_number=pr_number,
    )

    pipeline = ReviewPipeline()
    try:
        result = await pipeline.execute(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            post_review=True,
        )
        logger.info(
            "Background review completed",
            pr_number=pr_number,
            files_reviewed=result.files_reviewed,
            comments=result.total_comments,
        )
    except Exception as e:
        logger.error(
            "Background review failed",
            pr_number=pr_number,
            error=str(e),
        )
    finally:
        await pipeline.close()


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
) -> JSONResponse:
    """
    Handle GitHub webhook events.

    Currently handles:
    - pull_request.opened
    - pull_request.synchronize
    - pull_request.reopened
    """
    payload: dict[str, Any] = await request.json()

    logger.info(
        "Received GitHub webhook",
        event=x_github_event,
        action=payload.get("action"),
    )

    if x_github_event == "pull_request":
        action = payload.get("action")
        if action in ("opened", "synchronize", "reopened"):
            # Extract PR info
            pr_number = payload.get("number")
            repo_data = payload.get("repository", {})
            repo_full_name = repo_data.get("full_name", "")

            if "/" in repo_full_name and pr_number is not None:
                owner, repo = repo_full_name.split("/", 1)

                logger.info(
                    "Queuing PR review",
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    action=action,
                )

                # Queue background task
                background_tasks.add_task(
                    process_pr_review,
                    owner=owner,
                    repo=repo,
                    pr_number=int(pr_number),
                )

                return JSONResponse(
                    status_code=status.HTTP_202_ACCEPTED,
                    content={"message": "Review queued", "pr_number": pr_number},
                )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Event received"},
    )
