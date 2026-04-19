"""Background tasks for map operations."""

import logging

from celery import shared_task
from sqlalchemy import select

from src.models.graph import LayerModel, MapModel
from src.models.jobs import MapJobModel
from src.services.computation import ComputationService
from src.workers import DatabaseTask, celery_app

logger = logging.getLogger(__name__)


def _set_job_status(
    task: DatabaseTask,
    job: MapJobModel,
    status: str,
    step: str | None = None,
    error: str | None = None,
) -> None:
    """Update job status in-place and flush."""
    job.status = status  # type: ignore[assignment]
    if step is not None:
        job.step = step
    if error is not None:
        job.error = error
    task.db.flush()
    task.db.commit()


def _run_map_computation(
    task: DatabaseTask,
    job: MapJobModel,
    map_id: int,
    force: bool,
    geometry_step_prefix: str,
    data_step_prefix: str,
) -> None:
    """Shared computation driver used by both import and recompute tasks.

    Runs ``bulk_recompute_layer`` (geometry) then ``bulk_recompute_data_layer``
    (data aggregation, if the map has data fields) for every order>=1 layer,
    bottom-to-top.  Commits job status updates after each layer so the UI can
    show per-layer progress.

    Args:
        force: When True, recomputes every node regardless of cached hash
               (used for initial import).  When False, only nodes whose
               input signature has changed are recomputed (used for
               incremental recompute after structural edits).
    """
    job_id = job.id

    map_model = task.db.get(MapModel, map_id)
    if not map_model:
        raise ValueError(f"Map {map_id} not found")

    data_field_config: list[dict[str, object]] = map_model.data_field_config or []  # type: ignore[assignment]
    has_data_fields = bool(data_field_config)

    layers: list[LayerModel] = list(
        task.db
        .execute(
            select(LayerModel)
            .where(LayerModel.map_id == map_id, LayerModel.order >= 1)
            .order_by(LayerModel.order.asc())
        )
        .scalars()
        .all()
    )

    if not layers:
        _set_job_status(task, job, "complete", step="Done — no parent layers to compute")
        return

    computation = ComputationService(db=task.db)

    for layer in layers:
        step_label = f"{geometry_step_prefix}: {layer.name}"
        logger.info("[%s]: %s", job_id, step_label)
        _set_job_status(task, job, "processing", step=step_label)
        result = computation.bulk_recompute_layer(layer_id=layer.id, force=force)
        logger.info("[%s]: geometry result %s", job_id, result)

    if has_data_fields:
        for layer in layers:
            step_label = f"{data_step_prefix}: {layer.name}"
            logger.info("[%s]: %s", job_id, step_label)
            _set_job_status(task, job, "processing", step=step_label)
            result = computation.bulk_recompute_data_layer(
                layer_id=layer.id,
                data_field_config=data_field_config,
                force=force,
            )
            logger.info("[%s]: data result %s", job_id, result)

    map_model.tile_version += 1
    _set_job_status(task, job, "complete", step="Done")
    logger.info("[%s]: complete", job_id)


@celery_app.task(base=DatabaseTask, bind=True, queue="terramaps", name="src.workers.tasks.maps.import_map_task")
def import_map_task(self: DatabaseTask, job_id: str, map_id: int) -> None:  # type: ignore[misc]
    """Compute geometry and data aggregations for a newly imported map.

    Uses force=True so every node is computed from scratch regardless of
    any stale cache keys.
    """
    job = self.db.get(MapJobModel, job_id)
    if not job:
        logger.error("import_map_task: job %s not found", job_id)
        return

    try:
        _set_job_status(self, job, "processing", step="Starting")
        _run_map_computation(
            task=self,
            job=job,
            map_id=map_id,
            force=True,
            geometry_step_prefix="Computing geometry",
            data_step_prefix="Computing data",
        )
    except Exception as exc:
        logger.exception("import_map_task [%s]: failed", job_id)
        _set_job_status(self, job, "failed", error=str(exc))
        raise


@celery_app.task(base=DatabaseTask, bind=True, queue="terramaps", name="src.workers.tasks.maps.recompute_map_task")
def recompute_map_task(self: DatabaseTask, job_id: str, map_id: int) -> None:  # type: ignore[misc]
    """Incrementally recompute geometry and data after structural edits.

    Triggered after bulk node operations (move, merge, delete, zip reassign).
    Uses force=False so only nodes whose input signatures changed are updated,
    making it significantly faster than a full import recompute.
    """
    job = self.db.get(MapJobModel, job_id)
    if not job:
        logger.error("recompute_map_task: job %s not found", job_id)
        return

    try:
        _set_job_status(self, job, "processing", step="Starting")
        _run_map_computation(
            task=self,
            job=job,
            map_id=map_id,
            force=False,
            geometry_step_prefix="Recomputing geometry",
            data_step_prefix="Recomputing data",
        )
    except Exception as exc:
        logger.exception("recompute_map_task [%s]: failed", job_id)
        _set_job_status(self, job, "failed", error=str(exc))
        raise
