"""Graph schemas."""

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, field_validator


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


class ZipAssignment(BaseModel):
    """A zip code's assignment state on a map layer.

    Represents a zip_assignments row. Implicit zips (no row) are only visible
    via MVT tiles and are not returned by the API as individual objects.
    """

    zip_code: str
    layer_id: int
    parent_node_id: int | None = None
    color: str
    data: dict[str, Any] | None = None

    @field_validator("zip_code")
    @classmethod
    def pad_zip_code(cls, v: str) -> str:
        """Ensure zip codes are always zero-padded to 5 characters."""
        return v.zfill(5)


class PaginatedZipAssignments(BaseModel):
    """Paginated zip assignments response."""

    zip_assignments: Sequence[ZipAssignment]
    total: int
    page: int
    page_size: int
    total_pages: int
