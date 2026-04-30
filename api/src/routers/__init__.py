"""Routers package."""

from .accounts import accounts_router
from .auth import auth_router
from .common import common_router
from .docs import docs_router
from .exports import exports_router
from .graph import graph_router
from .invites import map_invites_router, me_invites_router
from .maps import maps_router
from .members import map_members_router
from .mvt import mvt_router
from .ppt_exports import ppt_exports_router
from .spatial import spatial_router
from .uploads import uploads_router

__all__ = [
    "accounts_router",
    "auth_router",
    "common_router",
    "docs_router",
    "exports_router",
    "graph_router",
    "map_invites_router",
    "map_members_router",
    "maps_router",
    "me_invites_router",
    "mvt_router",
    "ppt_exports_router",
    "spatial_router",
    "uploads_router",
]
