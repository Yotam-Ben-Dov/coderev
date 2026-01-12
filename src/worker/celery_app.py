"""Celery application configuration."""

from celery import Celery

from src.core.config import settings

# Create Celery app
celery_app = Celery(
    "coderev",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.worker.tasks.review_tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,  # Requeue if worker dies
    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_concurrency=4,  # Number of concurrent workers
    # Task routing (for future scaling)
    task_routes={
        "src.worker.tasks.review_tasks.*": {"queue": "reviews"},
    },
    # Default queue
    task_default_queue="default",
    # Retry settings
    task_annotations={
        "src.worker.tasks.review_tasks.process_review": {
            "max_retries": 3,
            "default_retry_delay": 60,  # 1 minute
        },
    },
)

# Optional: Beat schedule for periodic tasks (future use)
celery_app.conf.beat_schedule = {
    # Example: Clean up old reviews every day
    # "cleanup-old-reviews": {
    #     "task": "src.worker.tasks.review_tasks.cleanup_old_reviews",
    #     "schedule": 86400,  # Every 24 hours
    # },
}
