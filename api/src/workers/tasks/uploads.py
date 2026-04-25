"""Background tasks for upload processing."""

import io
import logging

import pandas as pd

from src.models.uploads import MapUploadModel
from src.services.s3 import S3Service
from src.workers import DatabaseTask, celery_app

logger = logging.getLogger(__name__)


def _to_python(val: object) -> str | int | float | None:
    """Convert a pandas cell value to a JSON-safe Python native."""
    if val is None:
        return None
    try:
        if pd.isna(val):  # type: ignore[arg-type]
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, bool):
        return int(val)
    if hasattr(val, "item"):
        val = val.item()  # type: ignore[union-attr]  # unwrap numpy scalar
    if isinstance(val, float):
        return val
    if isinstance(val, int):
        return val
    return str(val)


@celery_app.task(base=DatabaseTask, bind=True, queue="terramaps")
def process_upload_task(self: DatabaseTask, upload_id: str) -> None:  # type: ignore[misc]
    r"""Parse an uploaded spreadsheet and populate MapUploadModel with results.

    Runs in the background immediately after POST /maps/uploads. On success
    the upload transitions to 'ready'; on any failure it transitions to 'failed'.
    """
    upload = self.db.get(MapUploadModel, upload_id)
    if not upload:
        logger.error("process_upload_task: upload %s not found", upload_id)
        return

    try:
        s3 = S3Service()
        body = s3.get_private_object(key=upload.s3_key)
        file_bytes = io.BytesIO(body.read())

        df: pd.DataFrame = pd.read_excel(
            file_bytes,
            sheet_name=upload.tab_index,
            header=0,
            dtype=object,
            nrows=None,
        )

        headers: list[str] = [str(c) for c in df.columns.tolist()]
        row_count: int = len(df)

        preview_rows: list[list[str | int | float | None]] = [
            [_to_python(cell) for cell in row]
            for row in df.head(20).itertuples(index=False, name=None)
        ]

        # TODO: implement a more sophisticated suggested-layers heuristic here
        # (e.g. cardinality analysis, zip-pattern detection, numeric column exclusion).
        # For now: suggest the first four headers as the layer columns.
        suggested_layers = headers[:4]

        upload.status = "ready"
        upload.headers = headers
        upload.suggested_layers = suggested_layers
        upload.preview_rows = preview_rows
        upload.row_count = row_count
        self.db.commit()

    except Exception as exc:
        logger.exception("process_upload_task [%s]: failed", upload_id)
        upload.status = "failed"
        upload.error = type(exc).__name__
        upload.error_reason = str(exc)
        self.db.commit()
