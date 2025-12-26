"""Generate the openapi spec on app startup."""

import json
import logging
import os
from typing import Any

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def openapi_generator(app: FastAPI) -> dict[str, Any]:
    """Generate the openapi.json schema on startup ."""
    return app.openapi()


def save_openapi(app: FastAPI) -> None:
    """Generate the openapi.json schema on startup and save it locally."""
    # filepath is /app/openapi.json in the docker image. In the git repo this is /api/openapi.json
    openapi_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "openapi.json"))

    with open(openapi_file_path, "w") as openapi_file:
        json.dump(openapi_generator(app), openapi_file, indent=2)


def configure_openapi(app: FastAPI) -> None:
    """Add the event handler to generate the openapi.json schema on startup.

    This event handler will only be added when the app is run in development mode.
    """
    if app.debug:
        app.add_event_handler("startup", lambda: save_openapi(app=app))  # type: ignore  # noqa: PGH003
    else:
        logger.warning("OpenAPI generation is disabled in production.")
