"""Background tasks for PPT exports."""

import logging

from sqlalchemy import select

from src.models.exports import MapExportModel, MapExportSlideModel
from src.models.graph import LayerModel, MapModel
from src.services.ppt_builder import build_pptx_buffer
from src.services.s3 import S3Service
from src.workers import DatabaseTask, celery_app

logger = logging.getLogger(__name__)

_S3_PREFIX = "map-exports"


@celery_app.task(base=DatabaseTask, bind=True, queue="terramaps", name="src.workers.tasks.exports.generate_ppt_task")
def generate_ppt_task(self: DatabaseTask, export_id: str) -> None:  # type: ignore[misc]
    """Assemble the .pptx for an export and upload it to S3.

    Sets status='complete' + pptx_s3_key on success, status='failed' + error on failure.
    """
    export = self.db.get(MapExportModel, export_id)
    if not export:
        logger.error("generate_ppt_task: export %s not found", export_id)
        return

    try:
        slides = (
            self.db.execute(
                select(MapExportSlideModel)
                .where(MapExportSlideModel.export_id == export_id)
                .order_by(MapExportSlideModel.order)
            )
            .scalars()
            .all()
        )

        s3 = S3Service()
        map_model = self.db.get(MapModel, export.map_id)
        cover_title = map_model.name if map_model else "Territory Report"
        layer_names = {
            layer.id: layer.name
            for layer in self.db.execute(
                select(LayerModel).where(LayerModel.map_id == export.map_id)
            ).scalars().all()
        }
        buf = build_pptx_buffer(slides, s3, cover_title=cover_title, layer_names=layer_names)

        s3_key = f"{_S3_PREFIX}/{export_id}/report.pptx"
        s3.upload_private_file(
            file=buf,
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            key=s3_key,
        )

        export.pptx_s3_key = s3_key
        export.status = "complete"
        export.error = None
        self.db.commit()
        logger.info("generate_ppt_task [%s]: complete (%d slides)", export_id, len(slides))

    except Exception as exc:
        logger.exception("generate_ppt_task [%s]: failed", export_id)
        self.db.rollback()
        export.status = "failed"
        export.error = str(exc)
        self.db.commit()
        raise
