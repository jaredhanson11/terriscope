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
