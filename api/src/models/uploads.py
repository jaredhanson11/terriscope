"""Map upload model."""

from typing import Any, Literal

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, uuidpk


class MapUploadModel(Base, TimestampMixin):
    """Tracks the full lifecycle of a map file upload: parse → configure → import.

    Owns all import-time configuration (layer_config, data_config) so that the
    original intent of an import is always auditable independent of how the map
    evolves after creation.

    status progression:
        parsing   — file is in S3, background parse task is running
        ready     — parse complete, user can configure wizard
        importing — POST /maps called, import worker is running
        complete  — import done
        failed    — any phase failed (check error / error_reason)
    """

    __tablename__ = "map_uploads"

    id: Mapped[uuidpk] = mapped_column(init=False)
    s3_key: Mapped[str]
    original_filename: Mapped[str]
    tab_index: Mapped[int]

    status: Mapped[Literal["parsing", "ready", "importing", "complete", "failed"]]

    # Populated by process_upload_task on success
    headers: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=None)
    suggested_layers: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=None)
    preview_rows: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True, default=None)
    row_count: Mapped[int | None] = mapped_column(nullable=True, default=None)

    # Set by POST /maps when the user finalises wizard configuration
    layer_config: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True, default=None)
    """Snapshot of layer setup at import time: [{"name": str, "header": str}, ...]"""
    data_config: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True, default=None)
    """Snapshot of data field setup at import time: [{"name": str, "header": str, "type": str, "aggregations": [...]}]"""

    # Populated on failure (either parse or import phase)
    error: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    error_reason: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    # Populated during / after the import phase
    import_step: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    warnings: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=None)

    __table_args__ = (Index("idx_map_uploads_s3_key", "s3_key"),)
