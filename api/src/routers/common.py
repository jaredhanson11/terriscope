"""Common routes."""

import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy.sql import text

import src
from src.app.database import DatabaseSession
from src.routers.dtos.common import HeartbeatResponseDTO, VersionResponseDTO, WorkerVersionDTO
from src.workers import celery_app, version

logger = logging.getLogger(__name__)

common_router = APIRouter(prefix="/v1.0", tags=["Common"])


@common_router.get(path="/heartbeat", response_model=HeartbeatResponseDTO)
async def heartbeat():
    """This route is used to check the server is up and running."""
    return HeartbeatResponseDTO(timenow=datetime.now(tz=UTC))


@common_router.get(path="/db-heartbeat")
def db_heartbeat(db: DatabaseSession):
    """This route is used to check the connection to the database is working."""
    result = db.execute(text("SELECT NOW();"))
    return HeartbeatResponseDTO(timenow=result.all()[0][0])


@common_router.get(path="/versions", response_model=VersionResponseDTO)
def versions():
    """This route returns the version of the current running API."""
    ROOT_PATH = Path(src.__file__).resolve().parent.parent
    api_version: str | None = None
    worker_versions: list[WorkerVersionDTO] = []

    try:
        with open(ROOT_PATH / "git-version.txt") as f:
            api_version = f.read().strip()
    except Exception:
        logger.warning("Could not read API version file", exc_info=True)

    try:
        broadcast = celery_app.control.broadcast(version.__name__, reply=True) or []
        for worker_reply in broadcast:
            for worker in worker_reply:
                worker_versions.append(WorkerVersionDTO(name=worker, version=worker_reply[worker]))
    except Exception:
        logger.warning("Something went wrong getting worker versions.", exc_info=True)

    return VersionResponseDTO(
        api=api_version,
        workers=worker_versions,
    )
