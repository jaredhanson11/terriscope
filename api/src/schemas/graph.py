"""Graph schemas."""

from typing import Any

from pydantic import BaseModel


class Layer(BaseModel):
    """Layer."""

    id: int
    name: str
    order: int
    parent_layer_id: int | None


class Node(BaseModel):
    """Node."""

    id: int
    layer_id: int
    parent_node_id: int | None
    name: str
    color: str
    data: dict[Any, Any]
