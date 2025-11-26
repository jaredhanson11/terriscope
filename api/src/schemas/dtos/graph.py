"""Graph dtos."""

from pydantic import BaseModel


class CreateLayer(BaseModel):
    """CreateLayer."""

    name: str


class CreateNode(BaseModel):
    """CreateNode."""

    layer_id: int
    parent_node_id: int | None
    name: str
    color: str
