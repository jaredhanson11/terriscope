"""Services module."""

from typing import Annotated

from fastapi import Depends

from src.app.database import DatabaseSession

from .graph import GraphService


def get_graph_service(db: DatabaseSession) -> GraphService:
    """Get a database session."""
    return GraphService(db=db)


GraphServiceDependency = Annotated[GraphService, Depends(get_graph_service)]
