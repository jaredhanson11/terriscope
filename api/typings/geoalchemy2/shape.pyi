from geoalchemy2.elements import WKBElement
from shapely.geometry.base import BaseGeometry

def from_shape(shape: BaseGeometry, srid: int = -1, extended: bool | None = False) -> WKBElement: ...
