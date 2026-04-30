"""Main API module.

This file is responsible for importing the configured FastAPI object and adding all routers.
"""

from .app import app
from .routers import (
    accounts_router,
    auth_router,
    common_router,
    docs_router,
    exports_router,
    graph_router,
    map_invites_router,
    map_members_router,
    maps_router,
    me_invites_router,
    mvt_router,
    ppt_exports_router,
    spatial_router,
    uploads_router,
)

app.include_router(common_router)
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(docs_router)
app.include_router(graph_router)
app.include_router(mvt_router)
app.include_router(maps_router)
app.include_router(map_invites_router)
app.include_router(map_members_router)
app.include_router(me_invites_router)
app.include_router(spatial_router)
app.include_router(exports_router)
app.include_router(ppt_exports_router)
app.include_router(uploads_router)
