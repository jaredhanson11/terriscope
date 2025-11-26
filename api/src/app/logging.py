"""Setup logging configurations."""

import logging.config
import sys

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI

from .config import app_settings

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "correlation_id": {
            "()": "asgi_correlation_id.CorrelationIdFilter",
            "uuid_length": 32,
            "default_value": "<unknown>",
        },
    },
    "handlers": {
        "default": {
            "formatter": "standard",
            "filters": ["correlation_id"],
            "class": "logging.StreamHandler",
        },
    },
    "formatters": {
        "standard": {
            "format": "%(asctime)s level=%(levelname)-8s logger=%(name)-20s caller=%(funcName)-20s linenumber=%(lineno)-4s request-id=%(correlation_id)-36s message=%(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S%z",
        },
    },
    "loggers": {
        "": {"level": "WARNING", "handlers": ["default"]},
        "src": {"level": app_settings.log_level},
        "uvicorn": {"handlers": ["default"]},
    },
}


def configure_logging(app: FastAPI) -> None:
    """Sets up logging configuration for FastAPI or Celery application."""
    logging.config.dictConfig(LOGGING_CONFIG)
    app.add_middleware(
        CorrelationIdMiddleware,
        header_name="X-Request-ID",
    )
