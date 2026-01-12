"""Review-related Celery tasks."""

import asyncio
from typing import Any

import structlog
from celery import Task

from src.db.session import get_session_context
from src.services.review.pipeline import ReviewPipeline
from src.worker.celery_app import celery_app

logger = structlog.get_logger()


class AsyncTask(Task):
    """Base task class that handles async execution."""

    abstract = True

    def run_async(self, coro):
        """Run an async coroutine in the task."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="src.worker.tasks.review_tasks.process_review",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,  # Max 10 minutes between retries
    retry_jitter=True,
)
def process_review(
    self: AsyncTask,
    owner: str,
    repo: str,
    pr_number: int,
    post_review: bool = True,
    skip_if_reviewed: bool = True,
) -> dict[str, Any]:
    """
    Process a code review asynchronously.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        post_review: Whether to post review to GitHub
        skip_if_reviewed: Skip if already reviewed at this SHA

    Returns:
        Dictionary with review results
    """
    logger.info(
        "Starting review task",
        task_id=self.request.id,
        owner=owner,
        repo=repo,
        pr_number=pr_number,
    )

    async def _execute() -> dict[str, Any]:
        async with get_session_context() as session:
            pipeline = ReviewPipeline(session=session)
            try:
                result = await pipeline.execute(
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    post_review=post_review,
                    skip_if_reviewed=skip_if_reviewed,
                )

                return {
                    "status": "completed",
                    "review_id": result.review_id,
                    "pr_number": result.pr_number,
                    "pr_title": result.pr_title,
                    "files_reviewed": result.files_reviewed,
                    "total_comments": result.total_comments,
                    "verdict": result.verdict,
                    "model_used": result.model_used,
                    "total_tokens": result.total_tokens,
                    "total_cost_usd": result.total_cost_usd,
                    "review_posted": result.review_posted,
                    "github_review_id": result.github_review_id,
                    "latency_ms": result.latency_ms,
                }
            finally:
                await pipeline.close()

    try:
        result = self.run_async(_execute())
        logger.info(
            "Review task completed",
            task_id=self.request.id,
            result=result,
        )
        return result
    except Exception as e:
        logger.error(
            "Review task failed",
            task_id=self.request.id,
            error=str(e),
            retry_count=self.request.retries,
        )
        raise


@celery_app.task(name="src.worker.tasks.review_tasks.health_check")
def health_check() -> dict[str, str]:
    """Simple health check task for monitoring."""
    return {"status": "healthy", "worker": "active"}
