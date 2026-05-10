"""DTOS for spatial operations."""

from geojson_pydantic import Polygon
from pydantic import BaseModel


class SpatialSelectRequest(BaseModel):
    layer_id: int
    polygon: Polygon


class SpatialSelectResponse(BaseModel):
    count: int
    nodes: list[int]
    """Node IDs — populated for order>=1 layers. Empty for zip layers."""
    zip_codes: list[str] = []
    """Zip code strings — populated for order=0 (zip) layers. Empty for node layers."""


class SpatialSummaryRequest(BaseModel):
    layer_id: int
    node_ids: list[int] = []
    """Node IDs — required for order>=1 layers."""
    zip_codes: list[str] = []
    """Zip code strings — required for order=0 (zip) layers."""


class SpatialSummaryResponse(BaseModel):
    count: int
    data: dict[str, dict[str, float]]
    """Per-field rollup, shape: {field: {sum, avg, min, max}}. Same shape as NodeModel.data."""
