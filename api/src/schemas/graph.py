"""Graph schemas."""

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel


class DataFieldConfig(BaseModel):
    """Data field config entry stored on a map."""

    field: str
    type: Literal["text", "number"]
    aggregations: list[Literal["sum", "avg"]]


class Map(BaseModel):
    """Map."""

    id: int
    name: str
    data_field_config: list[DataFieldConfig] | None = None


class Layer(BaseModel):
    """Layer."""

    id: int
    map_id: int
    name: str
    order: int


class Node(BaseModel):
    """Node."""

    id: int | Literal["default"]
    layer_id: int
    name: str
    color: str
    parent_node_id: int | None = None
    child_count: int = 0


class PaginatedNodes(BaseModel):
    """Paginated nodes response."""

    nodes: Sequence[Node]
    total: int
    page: int
    page_size: int
    total_pages: int
