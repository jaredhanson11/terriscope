"""API app setup.

This file is responsible for initializing the FastAPI object and setting up any configuration such as middlewares, logging config, etc.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from src.app.analytics import configure_analytics
from src.app.exceptions import configure_exceptions
from src.app.openapi import configure_openapi

from .config import app_settings
from .cors import configure_cors
from .logging import configure_logging

app = FastAPI(title="Terriscope API", debug=app_settings.debug)

# Trust the X-Forwarded-* headers from your proxies/load balancers
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# Mount static files
static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir), html=True), name="static")

# Additional configurations
configure_cors(app=app)
configure_logging(app=app)
configure_openapi(app=app)
configure_exceptions(app=app)
configure_analytics(app=app)
