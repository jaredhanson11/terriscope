"""Database session management."""

import logging
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import app_settings

logger = logging.getLogger(__name__)


def get_db_driver(app_name: str = "api") -> tuple[Engine, sessionmaker[Session]]:
    """Create a new engine + session factory.

    Called at startup for the FastAPI app and post-fork in Celery workers so
    each worker process gets its own connection pool.
    """
    engine = create_engine(
        app_settings.database.db_url,
        echo=app_settings.database.echo,
        connect_args={"application_name": app_name},
        pool_size=20,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, session_factory


# Module-level singletons used by the FastAPI app.
engine, SessionLocal = get_db_driver("api")


def get_db() -> Generator[Session, None]:
    """Get a database session."""
    with SessionLocal() as session:
        try:
            yield session
        finally:
            session.close()


DatabaseSession = Annotated[Session, Depends(get_db)]
