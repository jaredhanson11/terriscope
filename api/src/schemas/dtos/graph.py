"""Graph dtos."""

from typing import Annotated

from pydantic import BaseModel, Field


class CreateLayer(BaseModel):
    """CreateLayer."""

    name: str
    order: Annotated[int, Field(gt=0)]


class CreateNode(BaseModel):
    """CreateNode."""

    layer_id: int
    parent_node_id: int
    name: str
    color: str
