"""Database session management."""

import logging
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import app_settings

logger = logging.getLogger(__name__)

engine = create_engine(app_settings.database.db_url, echo=app_settings.database.echo)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None]:
    """Get a database session."""
    with SessionLocal() as session:
        try:
            yield session
        finally:
            session.close()


DatabaseSession = Annotated[Session, Depends(get_db)]
