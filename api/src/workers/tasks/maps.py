"""Background tasks for map operations."""

import logging
import uuid

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


def _get_layers(task: DatabaseTask, map_id: int) -> list[LayerModel]:
    return list(
        task.db
        .execute(
            select(LayerModel)
            .where(LayerModel.map_id == map_id, LayerModel.order >= 1)
            .order_by(LayerModel.order.asc())
        )
        .scalars()
        .all()
    )


def _run_geometry_computation(
    task: DatabaseTask,
    job: MapJobModel,
    map_id: int,
    force: bool,
    step_prefix: str,
) -> list[LayerModel]:
    """Recompute geometries for all order>=1 layers bottom-to-top.

    Returns the list of layers so callers can reuse it (e.g. for data
    computation in the import task).  Bumps ``tile_version`` on completion.
    """
    map_model = task.db.get(MapModel, map_id)
    if not map_model:
        raise ValueError(f"Map {map_id} not found")

    layers = _get_layers(task, map_id)

    if not layers:
        _set_job_status(task, job, "complete", step="Done — no parent layers to compute")
        return []

    computation = ComputationService(db=task.db)

    for layer in layers:
        step_label = f"{step_prefix}: {layer.name}"
        logger.info("[%s]: %s", job.id, step_label)
        _set_job_status(task, job, "processing", step=step_label)
        result = computation.bulk_recompute_layer(layer_id=layer.id, force=force)
        logger.info("[%s]: geometry result %s", job.id, result)

    map_model.tile_version += 1
    task.db.flush()
    task.db.commit()

    return layers


def _run_data_computation(
    task: DatabaseTask,
    job: MapJobModel,
    map_id: int,
    force: bool,
    step_prefix: str,
    layers: list[LayerModel] | None = None,
) -> None:
    """Recompute data aggregations for all order>=1 layers bottom-to-top."""
    map_model = task.db.get(MapModel, map_id)
    if not map_model:
        raise ValueError(f"Map {map_id} not found")

    data_field_config: list[dict[str, object]] = map_model.data_field_config or []  # type: ignore[assignment]
    if not data_field_config:
        _set_job_status(task, job, "complete", step="Done — no data fields")
        return

    if layers is None:
        layers = _get_layers(task, map_id)

    if not layers:
        _set_job_status(task, job, "complete", step="Done — no parent layers")
        return

    computation = ComputationService(db=task.db)

    for layer in layers:
        step_label = f"{step_prefix}: {layer.name}"
        logger.info("[%s]: %s", job.id, step_label)
        _set_job_status(task, job, "processing", step=step_label)
        result = computation.bulk_recompute_data_layer(
            layer_id=layer.id,
            data_field_config=data_field_config,
            force=force,
        )
        logger.info("[%s]: data result %s", job.id, result)


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
        layers = _run_geometry_computation(
            task=self,
            job=job,
            map_id=map_id,
            force=True,
            step_prefix="Computing geometry",
        )
        if layers:
            _run_data_computation(
                task=self,
                job=job,
                map_id=map_id,
                force=True,
                step_prefix="Computing data",
                layers=layers,
            )
        _set_job_status(self, job, "complete", step="Done")
        logger.info("[%s]: complete", job_id)
    except Exception as exc:
        logger.exception("import_map_task [%s]: failed", job_id)
        _set_job_status(self, job, "failed", error=str(exc))
        raise


@celery_app.task(base=DatabaseTask, bind=True, queue="terramaps", name="src.workers.tasks.maps.recompute_geometry_task")
def recompute_geometry_task(self: DatabaseTask, job_id: str, map_id: int) -> None:  # type: ignore[misc]
    """Incrementally recompute geometry after structural edits.

    Triggered after bulk node operations (move, merge, delete, zip reassign).
    Uses force=False so only nodes whose input signatures changed are updated.
    On success, enqueues a recompute_data_task if the map has data fields.
    """
    job = self.db.get(MapJobModel, job_id)
    if not job:
        logger.error("recompute_geometry_task: job %s not found", job_id)
        return

    try:
        _set_job_status(self, job, "processing", step="Starting")
        layers = _run_geometry_computation(
            task=self,
            job=job,
            map_id=map_id,
            force=False,
            step_prefix="Recomputing geometry",
        )
        _set_job_status(self, job, "complete", step="Done")
        logger.info("[%s]: geometry complete", job_id)

        if layers:
            map_model = self.db.get(MapModel, map_id)
            has_data_fields = bool(map_model and map_model.data_field_config)
            if has_data_fields:
                data_job_id = str(uuid.uuid4())
                data_job = MapJobModel(
                    id=data_job_id,
                    map_id=map_id,
                    job_type="recompute_data",
                    status="pending",
                    step=None,
                    error=None,
                )
                self.db.add(data_job)
                self.db.commit()
                recompute_data_task.delay(data_job_id, map_id)
                logger.info("[%s]: dispatched data job %s", job_id, data_job_id)
    except Exception as exc:
        logger.exception("recompute_geometry_task [%s]: failed", job_id)
        _set_job_status(self, job, "failed", error=str(exc))
        raise


@celery_app.task(base=DatabaseTask, bind=True, queue="terramaps", name="src.workers.tasks.maps.recompute_data_task")
def recompute_data_task(self: DatabaseTask, job_id: str, map_id: int) -> None:  # type: ignore[misc]
    """Incrementally recompute data aggregations after geometry is updated.

    Chained automatically by recompute_geometry_task on success.
    Uses force=False so only nodes whose data input signatures changed are updated.
    """
    job = self.db.get(MapJobModel, job_id)
    if not job:
        logger.error("recompute_data_task: job %s not found", job_id)
        return

    try:
        _set_job_status(self, job, "processing", step="Starting")
        _run_data_computation(
            task=self,
            job=job,
            map_id=map_id,
            force=False,
            step_prefix="Recomputing data",
        )
        _set_job_status(self, job, "complete", step="Done")
        logger.info("[%s]: data complete", job_id)
    except Exception as exc:
        logger.exception("recompute_data_task [%s]: failed", job_id)
        _set_job_status(self, job, "failed", error=str(exc))
        raise
