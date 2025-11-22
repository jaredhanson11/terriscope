"""Analytics middlewares."""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Configure logging
logger = logging.getLogger(__name__)


class _ResponseTimeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        """Initialize the middleware."""
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Measure the response time of the request."""
        start_time: float = time.perf_counter()
        response: Response = await call_next(request)
        end_time: float = time.perf_counter()
        duration: float = (end_time - start_time) * 1000  # Convert to milliseconds

        logger.debug(
            f"{request.method} {request.url.path}{f"?{request.url.query}" if request.url.query else ""} returned {response.status_code} in {duration:.2f}ms"
        )

        return response


def configure_analytics(app: FastAPI) -> None:
    """Configure analytics middlewares."""
    app.add_middleware(_ResponseTimeMiddleware)
