"""Main API module.

This file is responsible for importing the configured FastAPI object and adding all routers.
"""

from .app import app
from .routers import (
    common_router,
    docs_router,
)

app.include_router(common_router)
app.include_router(docs_router)
