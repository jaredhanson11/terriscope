"""Layers models."""

from typing import Any

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, intpk


class LayerModel(Base):
    """Defines a layer in the hierarchy (e.g., Territory, Region, Zip)."""

    __tablename__ = "layers"

    id: Mapped[intpk] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(unique=True)
    order: Mapped[int]
    """Order of the layer (aka 0 will always be zip, 1 will usually be territory, etc.)"""

    parent_layer_id: Mapped[int | None] = mapped_column(ForeignKey("layers.id"))

    __table_args__ = (UniqueConstraint("order"),)


class NodeModel(Base):
    """Node."""

    __tablename__ = "nodes"

    id: Mapped[intpk] = mapped_column(init=False)
    layer_id: Mapped[int] = mapped_column(ForeignKey("layers.id"))
    name: Mapped[str]
    geom: Mapped[WKBElement] = mapped_column(Geometry(srid=4326), nullable=True)
    color: Mapped[str]
    data: Mapped[dict[Any, Any]] = mapped_column(JSONB, server_default="{}")
    is_default: Mapped[bool] = mapped_column(server_default="FALSE")


class DependencyModel(Base):
    """Dependency between entities."""

    __tablename__ = "layer_entity_dependencies"

    id: Mapped[intpk] = mapped_column(init=False)
    parent_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"))
    child_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"))
    # order: Mapped[int]
