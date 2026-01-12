"""GitHub webhook handlers."""

import hashlib
import hmac
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.worker.tasks.review_tasks import process_review

router = APIRouter()
logger = structlog.get_logger()


def verify_github_signature(payload: bytes, signature: str | None) -> bool:
    """
    Verify GitHub webhook signature.
    
    Args:
        payload: Raw request body
        signature: X-Hub-Signature-256 header value
    
    Returns:
        True if signature is valid or webhook secret is not configured
    """
    # If no webhook secret configured, skip verification (development mode)
    if not hasattr(settings, "github_webhook_secret") or not settings.github_webhook_secret:
        return True
    
    if not signature:
        return False
    
    secret = settings.github_webhook_secret.get_secret_value().encode()
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(expected, signature)


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_github_delivery: str | None = Header(None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> JSONResponse:
    """
    Handle GitHub webhook events.

    Currently handles:
    - pull_request.opened
    - pull_request.synchronize
    - pull_request.reopened
    
    Events are queued to Celery for async processing.
    """
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify signature (if configured)
    if not verify_github_signature(body, x_hub_signature_256):
        logger.warning("Invalid webhook signature", delivery_id=x_github_delivery)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )
    
    payload: dict[str, Any] = await request.json()

    logger.info(
        "Received GitHub webhook",
        event=x_github_event,
        action=payload.get("action"),
        delivery_id=x_github_delivery,
    )

    if x_github_event == "ping":
        # GitHub sends a ping event when webhook is first configured
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "pong", "zen": payload.get("zen")},
        )

    if x_github_event == "pull_request":
        action = payload.get("action")
        
        # Only process on open, sync, or reopen
        if action in ("opened", "synchronize", "reopened"):
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

                # Queue task to Celery
                task = process_review.delay(
                    owner=owner,
                    repo=repo,
                    pr_number=int(pr_number),
                    post_review=True,
                    skip_if_reviewed=True,
                )

                return JSONResponse(
                    status_code=status.HTTP_202_ACCEPTED,
                    content={
                        "message": "Review queued",
                        "task_id": task.id,
                        "pr_number": pr_number,
                    },
                )

    # Event received but not processed
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Event received", "processed": False},
    )


@router.get("/github/health")
async def webhook_health() -> dict[str, str]:
    """Health check for webhook endpoint."""
    return {"status": "healthy"}