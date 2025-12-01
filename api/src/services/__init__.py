"""Services module."""

from typing import Annotated

from fastapi import Depends

from src.app.database import DatabaseSession
from src.services.computation import ComputationService

from .graph import GraphService


def get_graph_service(db: DatabaseSession) -> GraphService:
    """Get graph service."""
    return GraphService(db=db)


GraphServiceDependency = Annotated[GraphService, Depends(get_graph_service)]


def get_computation_service(db: DatabaseSession) -> ComputationService:
    """Get computation service."""
    return ComputationService(db=db)


ComputationServiceDependency = Annotated[ComputationService, Depends(get_computation_service)]
