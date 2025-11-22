"""Setup for general exception handlers."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """Error response."""

    message: str


def configure_exceptions(app: FastAPI) -> None:
    """Configure exceptions to override FastAPI's default exception handling."""

    def handle_general_error(request: Request, exc: Exception) -> JSONResponse:
        """Handle all exceptions."""
        logger.debug(f"Unhandled Exception: {exc!s}")
        return JSONResponse(status_code=500, content={"message": f"Unhandled Exception: {exc!s}"})

    def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        """Handle HTTP exceptions."""
        return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})

    def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ):
        """Handle validation errors.  Overwrite the default FastAPI handler to return a JSON response for 422 errors."""
        # Log detailed error information for debugging
        logger.error(f"Validation error on request to {request.url}")
        logger.error(f"Request body: {request.body}")
        logger.error(f"Query parameters: {request.query_params}")
        logger.error(f"Validation errors: {exc.errors()}")

        error_msg = "Invalid request."
        if len(exc.errors()) > 0 and exc.errors()[0].get("ctx") and exc.errors()[0]["ctx"].get("reason"):
            error_msg += f" {exc.errors()[0]["ctx"]["reason"]}"

        try:
            return JSONResponse(
                {
                    "message": error_msg,
                    "detail": exc.errors(),  # Include detailed errors in the response
                },
                status_code=422,
            )
        except Exception:
            logger.exception("Error while handling validation.")
            return JSONResponse(
                {"message": error_msg},
                status_code=422,
            )

    app.exception_handlers = {
        Exception: handle_general_error,
        HTTPException: handle_http_exception,
        RequestValidationError: handle_validation_error,
    }
