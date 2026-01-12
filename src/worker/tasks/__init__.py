"""Celery tasks for CodeRev."""

from src.worker.tasks.review_tasks import process_review

__all__ = ["process_review"]