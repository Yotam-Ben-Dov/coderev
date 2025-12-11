from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, Request, status
from fastapi.responses import JSONResponse

router = APIRouter()
logger = structlog.get_logger()


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
) -> JSONResponse:
    """
    Handle GitHub webhook events.
    
    For now, we're using PAT-based polling, but this endpoint
    is ready for when we add webhook support.
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
            # TODO: Queue review task
            logger.info(
                "PR event received",
                action=action,
                pr_number=payload.get("number"),
                repo=payload.get("repository", {}).get("full_name"),
            )
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={"message": "Review queued"},
            )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Event received"},
    )