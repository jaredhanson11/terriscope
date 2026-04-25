"""Upload schemas."""

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.models.uploads import MapUploadModel


class MapUploadParsing(BaseModel):
    """Returned by both POST /maps/uploads and GET /maps/uploads/{id} while parsing."""

    document_id: str
    status: Literal["parsing"]

    @staticmethod
    def create(upload: "MapUploadModel") -> "MapUploadParsing":
        return MapUploadParsing(document_id=upload.id, status="parsing")


class MapUploadReady(BaseModel):
    """Returned by GET /maps/uploads/{id} once parsing is complete.

    The frontend uses headers + suggested_layers to render the wizard configuration
    step, and preview_rows to show the user a sample of their data.
    """

    document_id: str
    status: Literal["ready"]
    headers: list[str]
    suggested_layers: list[str]
    """Ordered subset of headers identified as hierarchy columns, high → low (e.g. Region → Territory → Zip)."""
    preview_rows: list[list[str | int | float | None]]
    """First 20 data rows from the selected sheet."""
    row_count: int
    warnings: list[str]

    @staticmethod
    def create(upload: "MapUploadModel") -> "MapUploadReady":
        return MapUploadReady(
            document_id=upload.id,
            status="ready",
            headers=upload.headers or [],
            suggested_layers=upload.suggested_layers or [],
            preview_rows=upload.preview_rows or [],
            row_count=upload.row_count or 0,
            warnings=upload.warnings or [],
        )


class MapUploadFailed(BaseModel):
    """Returned by GET /maps/uploads/{id} when parsing failed."""

    document_id: str
    status: Literal["failed"]
    error: str
    error_reason: str | None = None

    @staticmethod
    def create(upload: "MapUploadModel") -> "MapUploadFailed":
        return MapUploadFailed(
            document_id=upload.id,
            status="failed",
            error=upload.error or "UNKNOWN_ERROR",
            error_reason=upload.error_reason,
        )


MapUploadStatus = Annotated[
    MapUploadParsing | MapUploadReady | MapUploadFailed,
    Field(discriminator="status"),
]
"""Discriminated union on 'status' for GET /maps/uploads/{id} responses."""


class MapImportState(BaseModel):
    """Import lifecycle state embedded in Map responses.

    Covers the import phase (after POST /maps). The parse phase lives on MapUploadStatus.
    Non-nullable on Map — all maps in this system are created via the upload flow.
    """

    status: Literal["importing", "complete", "failed"]
    step: str | None = None
    """Current processing step label, set while status == 'importing'."""
    warnings: list[str] | None = None
    """Post-import warnings (e.g. unrecognized zip codes). Set when status == 'complete'."""
    error: str | None = None
    """Error message. Set when status == 'failed'."""

    @staticmethod
    def create(upload: "MapUploadModel") -> "MapImportState":
        """Build MapImportState from a MapUploadModel in the importing/complete/failed phase."""
        match upload.status:
            case "importing":
                return MapImportState(status="importing", step=upload.import_step)
            case "complete":
                return MapImportState(status="complete", warnings=upload.warnings or [])
            case "failed":
                return MapImportState(status="failed", error=upload.error)
            case _:
                # Should not reach here for a map that has been created.
                # Treat pre-import states as still importing.
                return MapImportState(status="importing", step=None)
