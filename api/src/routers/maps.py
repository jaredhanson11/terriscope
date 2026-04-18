"""Maps router."""

import hashlib
import json
import uuid
from typing import Any, TypedDict

import pandas as pd
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.app.database import DatabaseSession
from src.models.geography import ZipCodeGeography
from src.models.graph import LayerModel, MapModel, NodeModel, ZipAssignmentModel
from src.models.jobs import MapJobModel
from src.schemas.dtos.graph import CreateLayer
from src.schemas.dtos.maps import DataFieldSetup, ImportMap
from src.schemas.graph import Map, MapJob
from src.services.auth import CurrentUserDependency
from src.services.graph import GraphServiceDependency
from src.services.permissions import PermissionsServiceDependency

maps_router = APIRouter(prefix="/maps", tags=["Maps"])

# Visually distinct palette for territory/region nodes on order>=1 layers.
# Colors are cycled by insertion index within each layer so every territory
# gets a unique color (up to 16; wraps after that).
_TERRITORY_PALETTE = [
    "#E63946", "#F4A261", "#2A9D8F", "#457B9D", "#6A4C93",
    "#F72585", "#4CC9F0", "#7CB518", "#FB8500", "#023E8A",
    "#8338EC", "#FF006E", "#3A86FF", "#06D6A0", "#FFBE0B",
    "#FB5607",
]


class BulkInsertNode(TypedDict):
    """BulkInsertNode — used for order>=1 layers only."""

    layer_id: int
    name: str
    parent_node_id: int | None
    color: str
    data: Any | None
    data_cache_key: str
    data_inputs_cache_key: str
    geom_cache_key: str
    geom_inputs_cache_key: str


class BulkInsertZipAssignment(TypedDict):
    """BulkInsertZipAssignment — used for the order=0 zip layer."""

    layer_id: int
    zip_code: str
    parent_node_id: int | None
    color: str
    data: Any | None
    data_cache_key: str
    data_inputs_cache_key: str


def _compute_leaf_data(
    df_values: pd.DataFrame,
    header: str,
    nodes_df: pd.DataFrame,
    numeric_data_fields: list[DataFieldSetup],
) -> dict[str, dict[str, float | None]]:
    """Compute raw aggregated data for leaf (zip code) nodes."""
    leaf_data_by_name: dict[str, dict[str, float | None]] = {}
    normalized_col = df_values[header].astype(str).str.zfill(5)
    for leaf_name in nodes_df[header].unique():
        matching = df_values[normalized_col == str(leaf_name)]
        data_dict: dict[str, float | None] = {}
        for field in numeric_data_fields:
            vals = pd.to_numeric(matching[field.header], errors="coerce").dropna()
            raw = float(vals.sum()) if not vals.empty else None
            for agg in field.aggregations:
                data_dict[f"{field.name}_{agg}"] = raw
        leaf_data_by_name[str(leaf_name)] = data_dict
    return leaf_data_by_name


def _load_active_job(db: DatabaseSession, map_id: int) -> MapJob | None:
    """Return the most recent non-complete job for a map, or None."""
    job = db.execute(
        select(MapJobModel)
        .where(MapJobModel.map_id == map_id)
        .order_by(MapJobModel.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if job is None or job.status == "complete":
        return None

    return MapJob(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        step=job.step,
        error=job.error,
    )


def _map_to_schema(map_model: MapModel, active_job: MapJob | None) -> Map:
    """Convert a MapModel ORM object to a Map schema, attaching job state."""
    return Map(
        id=map_model.id,
        name=map_model.name,
        tile_version=map_model.tile_version,
        data_field_config=map_model.data_field_config,
        active_job=active_job,
    )


@maps_router.post("", response_model=Map, status_code=202)
def create_map(
    graph_service: GraphServiceDependency,
    db: DatabaseSession,
    import_data: ImportMap,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
) -> Map:
    """Create map.

    Synchronously inserts all nodes and zip assignments, then enqueues a
    background task to compute geometry and data aggregations.  Returns 202
    with the new map and an ``active_job`` tracking the pending computation.

    TODO:
        - Return errors for zip codes we don't have data for
        - Validate no duplicate layer names
        - Validate no duplicate parents and raise error if so
    """
    # Lazy import to avoid importing Celery at module load time in API workers
    from src.workers.tasks.maps import import_map_task  # noqa: PLC0415

    data_field_config = [
        {"field": df.name, "type": df.type, "aggregations": df.aggregations}
        for df in import_data.data_fields
        if df.type == "number" and df.aggregations
    ]

    # Create map + permission role
    new_map = graph_service.create_map(name=import_data.name)
    new_map.data_field_config = data_field_config or None
    permission_service.add_map_role(user_id=current_user.id, map_id=new_map.id, role="OWNER")

    # Create layers (order assigned bottom-up: first layer created = order 0)
    layer_and_headers: list[tuple[LayerModel, str]] = []
    for layer_setup in import_data.layers:
        layer = graph_service.create_layer(layer_data=CreateLayer(name=layer_setup.name, map_id=new_map.id))
        layer_and_headers.append((layer, layer_setup.header))

    df_values = pd.DataFrame(import_data.values, columns=list[str](import_data.headers)).astype(object)
    numeric_data_fields = [df for df in import_data.data_fields if df.type == "number" and df.aggregations]

    # Fetch valid zip codes once for the leaf layer filter
    valid_zip_codes: set[str] | None = None
    if any(layer.order == 0 for layer, _ in layer_and_headers):
        valid_zip_codes = set(db.execute(select(ZipCodeGeography.zip_code)).scalars().all())

    previous_header: str | None = None
    previous_nodes: pd.DataFrame | None = None  # DataFrame(id, name) from the layer above

    # Process layers from top (highest order) down to the zip layer (order=0)
    for layer, header in reversed(layer_and_headers):
        df_idx = [header] if not previous_header else [header, previous_header]
        rows_df = df_values[df_idx].drop_duplicates().copy()
        rows_df = rows_df[rows_df[header].notna() & (rows_df[header] != "")]

        if layer.order == 0:
            # --- Zip layer: insert into zip_assignments, not nodes ---
            rows_df[header] = rows_df[header].astype(str).str.zfill(5)
            if valid_zip_codes is not None:
                rows_df = rows_df[rows_df[header].isin(valid_zip_codes)]

            leaf_data = (
                _compute_leaf_data(df_values, header, rows_df, numeric_data_fields)
                if numeric_data_fields
                else {}
            )

            # Fetch geography colors for these zips in one query
            zip_codes_list = rows_df[header].tolist()
            geography_colors: dict[str, str] = dict(
                db.execute(
                    select(ZipCodeGeography.zip_code, ZipCodeGeography.color)
                    .where(ZipCodeGeography.zip_code.in_(zip_codes_list))
                ).all()
            )

            prev_nodes_snap = previous_nodes.copy() if previous_nodes is not None else None
            bulk_insert_zips = rows_df.apply(
                lambda row, lid=layer.id, prev=prev_nodes_snap, ld=leaf_data, colors=geography_colors: (
                    BulkInsertZipAssignment(
                        layer_id=lid,
                        zip_code=str(row[header]),
                        parent_node_id=next(
                            iter(prev.loc[prev["name"] == str(row[previous_header]), "id"]), None
                        )
                        if previous_header is not None and prev is not None
                        else None,
                        color=colors.get(str(row[header]), "#CCCCCC"),
                        data=ld.get(str(row[header])) or None,
                        data_cache_key=hashlib.md5(
                            json.dumps(ld[str(row[header])], sort_keys=True).encode()
                        ).hexdigest()
                        if ld.get(str(row[header]))
                        else "",
                        data_inputs_cache_key="",
                    )
                ),
                axis=1,
            ).to_list()

            db.execute(insert(ZipAssignmentModel).values(bulk_insert_zips))

        else:
            # --- Parent layer (order>=1): insert into nodes ---
            prev_nodes_snap = previous_nodes.copy() if previous_nodes is not None else None
            bulk_insert_nodes = [
                BulkInsertNode(
                    layer_id=layer.id,
                    name=str(row[header]),
                    parent_node_id=next(
                        iter(prev_nodes_snap.loc[prev_nodes_snap["name"] == str(row[previous_header]), "id"]), None
                    )
                    if previous_header is not None and prev_nodes_snap is not None
                    else None,
                    color=_TERRITORY_PALETTE[int(hashlib.md5(str(row[header]).encode()).hexdigest(), 16) % len(_TERRITORY_PALETTE)],
                    data=None,
                    data_cache_key="",
                    data_inputs_cache_key="",
                    geom_cache_key="",
                    geom_inputs_cache_key="",
                )
                for _, row in rows_df.iterrows()
            ]

            result = db.execute(
                insert(NodeModel).values(bulk_insert_nodes).returning(NodeModel.id, NodeModel.name)
            ).tuples()
            previous_nodes = pd.DataFrame(result, columns=["id", "name"]).astype(object)

        previous_header = header

    # Create the job record and commit everything together so the worker
    # always sees the nodes/zips when it starts.
    job_id = str(uuid.uuid4())
    job = MapJobModel(
        id=job_id,
        map_id=new_map.id,
        job_type="import",
        status="pending",
        step=None,
        error=None,
    )
    db.add(job)
    db.commit()

    # Enqueue background computation
    import_map_task.delay(job_id, new_map.id)

    return _map_to_schema(
        new_map,
        MapJob(id=job_id, job_type="import", status="pending"),
    )


@maps_router.get("", response_model=list[Map])
def list_maps(
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
) -> list[Map]:
    """List maps for the current user, each with its latest active job if any."""
    map_roles = permission_service.list_map_roles(user_id=current_user.id)
    map_ids = [mr.map_id for mr in map_roles]

    maps = db.execute(select(MapModel).where(MapModel.id.in_(map_ids))).scalars().all()

    # Fetch the most recent non-complete job per map in a single query.
    # We use a subquery to rank jobs per map and take the latest one.
    active_jobs: dict[int, MapJob] = {}
    if map_ids:
        job_rows = db.execute(
            select(MapJobModel)
            .where(MapJobModel.map_id.in_(map_ids))
            .order_by(MapJobModel.map_id, MapJobModel.created_at.desc())
        ).scalars().all()

        seen: set[int] = set()
        for job in job_rows:
            if job.map_id not in seen:
                seen.add(job.map_id)
                if job.status != "complete":
                    active_jobs[job.map_id] = MapJob(
                        id=job.id,
                        job_type=job.job_type,
                        status=job.status,
                        step=job.step,
                        error=job.error,
                    )

    return [_map_to_schema(m, active_jobs.get(m.id)) for m in maps]


@maps_router.get("/{map_id}", response_model=Map)
def get_map(
    map_id: int,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
) -> Map:
    """Get a single map with its latest active job."""
    map_roles = permission_service.list_map_roles(user_id=current_user.id)
    if not any(mr.map_id == map_id for mr in map_roles):
        raise HTTPException(status_code=404, detail="Map not found")

    map_model = db.get(MapModel, map_id)
    if not map_model:
        raise HTTPException(status_code=404, detail="Map not found")

    return _map_to_schema(map_model, _load_active_job(db, map_id))
