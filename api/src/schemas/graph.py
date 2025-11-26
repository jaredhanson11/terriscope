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
    parent_node_id: int | None = None
    child_count: int = 0


class PaginatedNodes(BaseModel):
    """Paginated nodes response."""

    nodes: list[Node]
    total: int
    page: int
    page_size: int
    total_pages: int
