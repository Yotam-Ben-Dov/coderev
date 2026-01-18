"""Celery worker package for CodeRev."""

from src.worker.celery_app import celery_app

__all__ = ["celery_app"]
