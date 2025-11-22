"""Base model."""

import enum
from datetime import UTC, datetime
from typing import Annotated, ClassVar, Literal

import sqlalchemy
from sqlalchemy import DateTime, Integer, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

# Helper types for model colums
intpk = Annotated[int, mapped_column(Integer, primary_key=True, autoincrement=True)]


class Base(MappedAsDataclass, DeclarativeBase):
    """Base sqlalchemy model class.

    This class serves as the base for all SQLAlchemy declarative models in the application.
    It includes a custom metadata naming convention for indexes, unique constraints,
    check constraints, foreign keys, and primary keys.
    """

    """Base model class."""

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_`%(constraint_name)s`",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )

    type_annotation_map: ClassVar = {
        Literal: sqlalchemy.Enum(enum.Enum, create_constraint=False, native_enum=False),
        datetime: DateTime(timezone=True),
    }


class TimestampMixin(MappedAsDataclass):
    """Timestamp mixin class.

    This class provides timestamp columns for created_at and updated_at.
    """

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), init=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=lambda: datetime.now(tz=UTC), init=False
    )
