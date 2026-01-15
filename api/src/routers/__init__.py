"""Routers package."""

from .accounts import accounts_router
from .auth import auth_router
from .common import common_router
from .docs import docs_router
from .graph import graph_router
from .maps import maps_router
from .mvt import mvt_router

__all__ = [
    "accounts_router",
    "auth_router",
    "common_router",
    "docs_router",
    "graph_router",
    "maps_router",
    "mvt_router",
]
