"""Setup for CORS."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import app_settings

logger = logging.getLogger(__name__)


def configure_cors(app: FastAPI) -> None:
    """Configure CORS to allow known origins sending request cookies."""
    allowed_origins = [str(origin).removesuffix("/") for origin in app_settings.cors.allowed_origins]
    logger.debug(f"CORS configured to allow origins: {allowed_origins}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # remove and uncomment next two lines at some point
        # allow_origins=allowed_origins,
        # allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
