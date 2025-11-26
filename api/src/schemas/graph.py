"""Graph schemas."""

from collections.abc import Sequence

from pydantic import BaseModel


class Layer(BaseModel):
    """Layer."""

    id: int
    name: str
    order: int


class Node(BaseModel):
    """Node."""

    id: int
    layer_id: int
    name: str
    color: str


class NodeWithChildren(Node):
    """NodeWithChildren."""

    children: "Sequence[Node]"
