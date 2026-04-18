"""Celery tasks."""

# Import task modules so Celery registers them when this package is loaded.
from src.workers.tasks import maps as _maps  # noqa: F401
