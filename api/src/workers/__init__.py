"""Celery app configuration and worker lifecycle."""

import logging
from typing import Any

from celery import Celery, signals
from celery.app.task import Task
from celery.signals import setup_logging, task_postrun
from kombu import Queue
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.app.config import app_settings
from src.app.database import get_db_driver
from src.app.logging import configure_logging

# https://github.com/sbdchd/celery-types?tab=readme-ov-file#install
Task.__class_getitem__ = classmethod(lambda cls, *args, **kwargs: cls)  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

celery_app = Celery(
    broker=app_settings.celery.broker_url,
    task_ignore_result=True,
)

celery_app.conf.task_queues = [
    Queue("terramaps", routing_key="terramaps"),
]

celery_app.conf.task_default_queue = "terramaps"
celery_app.conf.task_default_exchange = "terramaps"
celery_app.conf.task_default_routing_key = "terramaps"
celery_app.conf.task_acks_late = True

# Auto-discover tasks — looks for a `tasks` submodule in each listed package
celery_app.autodiscover_tasks(["src.workers"])


# ---------------------------------------------------------------------------
# Worker DB pool — recreated post-fork so each worker process owns its pool
# ---------------------------------------------------------------------------

engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


@signals.worker_process_init.connect
def init_db_pool(*args: Any, **kwargs: Any) -> None:
    """Recreate database engine after fork to avoid sharing connections."""
    global engine, SessionLocal
    engine, SessionLocal = get_db_driver("celery-worker")


@signals.worker_process_shutdown.connect
def destroy_db_pool(**kwargs: Any) -> None:
    """Dispose the connection pool when the worker process shuts down."""
    global engine
    if engine:
        engine.dispose()


# ---------------------------------------------------------------------------
# DatabaseTask — base class that opens/closes a DB session per task
# ---------------------------------------------------------------------------


class DatabaseTask(Task[Any, Any]):
    """Base task that provides a per-task database session via ``self.db``.

    The session is opened in ``before_start`` and closed by the
    ``close_db_session`` signal handler after every run (success or failure).
    """

    db: Session

    def before_start(self, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        """Open a database session before the task body runs."""
        super().before_start(task_id, args, kwargs)  # type: ignore[reportAttributeAccessIssue]
        if not SessionLocal:
            msg = "SessionLocal is None — worker DB pool was not initialised."
            raise RuntimeError(msg)
        logger.debug("Opening DB session for task %s", task_id)
        self.db = SessionLocal()


@task_postrun.connect
def close_db_session(
    sender: Task[Any, Any],
    task_id: str,
    **kwargs: Any,
) -> None:
    """Close the DB session after every task, whether it succeeded or failed."""
    db: Session | None = getattr(sender, "db", None)
    if db is not None:
        logger.debug("Closing DB session for task %s", task_id)
        db.close()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


@setup_logging.connect()
def setup_celery_logging(*args: Any, **kwargs: Any) -> None:
    """Route Celery log records through the app's logging configuration."""
    configure_logging(celery_app)
