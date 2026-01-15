"""Review-related Celery tasks."""

import asyncio
from typing import Any

import structlog
from celery import Task
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.core.exceptions import GitHubNotFoundError, GitHubAuthenticationError
from src.core.config import settings

from src.services.review.pipeline import ReviewPipeline
from src.worker.celery_app import celery_app

logger = structlog.get_logger()


def get_worker_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Create a session factory for Celery workers.
    
    Uses NullPool to avoid connection pooling issues with event loops.
    Each task gets a fresh connection that's properly closed.
    """
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,  # No connection pooling for workers
        echo=settings.debug,
    )
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


class AsyncTask(Task):
    """Base task class that handles async execution properly."""
    
    abstract = True
    
    def run_async(self, coro: Any) -> Any:
        """Run an async coroutine in the task."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            # Clean up pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            
            # Allow cancelled tasks to complete
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()


@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="src.worker.tasks.review_tasks.process_review",
    autoretry_for=(Exception,),
    dont_autoretry_for=(GitHubNotFoundError, GitHubAuthenticationError),
    retry_backoff=True,
    retry_backoff_max=600,
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
        # Create fresh session factory for this task
        session_factory = get_worker_session_factory()
        
        async with session_factory() as session:
            pipeline = ReviewPipeline(session=session)
            try:
                result = await pipeline.execute(
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    post_review=post_review,
                    skip_if_reviewed=skip_if_reviewed,
                )
                
                # Commit the session
                await session.commit()
                
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
            except Exception as e:
                await session.rollback()
                raise
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