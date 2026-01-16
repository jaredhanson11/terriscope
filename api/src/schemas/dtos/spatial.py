"""DTOS for spatial operations."""

from geojson_pydantic import Polygon
from pydantic import BaseModel


class SpatialSelectRequest(BaseModel):
    layer_id: int
    polygon: Polygon


class SpatialSelectResponse(BaseModel):
    count: int
    nodes: list[int]
