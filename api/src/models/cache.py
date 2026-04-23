"""Cache models."""

from sqlalchemy import ForeignKey, LargeBinary, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class MvtTileCacheModel(Base, TimestampMixin):
    """Pre-rendered MVT tile cache.

    Keyed by (layer_id, endpoint, z, x, y). No revision in the key — tiles are
    explicitly invalidated by the recompute worker when affected geometries change.
    """

    __tablename__ = "mvt_tile_cache"

    layer_id: Mapped[int] = mapped_column(ForeignKey("layers.id"), primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(10), primary_key=True)
    z: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    x: Mapped[int] = mapped_column(primary_key=True)
    y: Mapped[int] = mapped_column(primary_key=True)
    tile_bytes: Mapped[bytes] = mapped_column(LargeBinary)
