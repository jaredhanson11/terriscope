"""Layers models."""

from typing import Any

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import ForeignKey, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, column_property, declared_attr, mapped_column

from src.models.base import Base, intpk


class LayerModel(Base):
    """Defines a layer in the hierarchy (e.g., Territory, Region, Zip)."""

    __tablename__ = "layers"

    id: Mapped[intpk] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(unique=True)
    order: Mapped[int]
    """Order of the layer (aka 0 will always be zip, 1 will usually be territory, etc.)"""

    __table_args__ = (UniqueConstraint("order"),)


class NodeModel(Base):
    """Node."""

    __tablename__ = "nodes"

    id: Mapped[intpk] = mapped_column(init=False)
    layer_id: Mapped[int] = mapped_column(ForeignKey("layers.id"))
    name: Mapped[str]
    color: Mapped[str]

    data: Mapped[dict[Any, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        deferred=True,
    )
    geom: Mapped[WKBElement | None] = mapped_column(
        Geometry(srid=4326),
        nullable=True,
        deferred=True,
    )

    parent_node_id: Mapped[int | None] = mapped_column(ForeignKey("nodes.id"), nullable=True)

    @declared_attr
    def child_count(cls):
        """Eagerly-loadable count of children using correlated subquery."""
        nodes = cls.__table__
        return column_property(
            select(func.count())
            .select_from(nodes)
            .where(nodes.c.parent_node_id == cls.id)
            .correlate_except(nodes)
            .scalar_subquery()
        )
