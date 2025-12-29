"""Geography models."""

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ZipCodeGeography(Base):
    """Zip code geography model."""

    __tablename__ = "geography_zip_codes"

    zip_code: Mapped[str] = mapped_column(String(5), primary_key=True)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(srid=4326),
        nullable=True,
    )
