"""Maps router."""

import hashlib
import json
from typing import Any, TypedDict

import pandas as pd
from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.app.database import DatabaseSession
from src.models.geography import ZipCodeGeography
from src.models.graph import LayerModel, MapModel, NodeModel, ZipAssignmentModel
from src.schemas.dtos.graph import CreateLayer
from src.schemas.dtos.maps import DataFieldSetup, ImportMap
from src.schemas.graph import Map
from src.services.auth import CurrentUserDependency
from src.services.computation import ComputationServiceDependency
from src.services.graph import GraphServiceDependency
from src.services.permissions import PermissionsServiceDependency

maps_router = APIRouter(prefix="/maps", tags=["Maps"])


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


@maps_router.post("", response_model=Map)
def create_map(
    graph_service: GraphServiceDependency,
    db: DatabaseSession,
    import_data: ImportMap,
    computation_service: ComputationServiceDependency,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Create map.

    TODO:
        - Return errors for zip codes we don't have data for
        - Validate no duplicate layer names
        - Validate no duplicate parents and raise error if so
    """
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
            # Zip is always the leaf — no need to update previous_nodes

        else:
            # --- Parent layer (order>=1): insert into nodes ---
            prev_nodes_snap = previous_nodes.copy() if previous_nodes is not None else None
            bulk_insert_nodes = rows_df.apply(
                lambda row, lid=layer.id, prev=prev_nodes_snap: (
                    BulkInsertNode(
                        layer_id=lid,
                        name=str(row[header]),
                        parent_node_id=next(
                            iter(prev.loc[prev["name"] == str(row[previous_header]), "id"]), None
                        )
                        if previous_header is not None and prev is not None
                        else None,
                        color="#CCCCCC",
                        data=None,
                        data_cache_key="",
                        data_inputs_cache_key="",
                        geom_cache_key="",
                        geom_inputs_cache_key="",
                    )
                ),
                axis=1,
            ).to_list()

            result = db.execute(
                insert(NodeModel).values(bulk_insert_nodes).returning(NodeModel.id, NodeModel.name)
            ).tuples()
            previous_nodes = pd.DataFrame(result, columns=["id", "name"]).astype(object)

        previous_header = header

    # Recompute geometry for all parent layers bottom-to-top (order=1 first)
    for layer, _ in layer_and_headers[1:]:
        result = computation_service.bulk_recompute_layer(layer_id=layer.id, force=True)
        print(f"Geometry layer {layer.name} (id={layer.id}): {result}")

    # Recompute aggregated data for all parent layers bottom-to-top
    if numeric_data_fields and data_field_config:
        for layer, _ in layer_and_headers[1:]:
            result = computation_service.bulk_recompute_data_layer(
                layer_id=layer.id,
                data_field_config=data_field_config,
                force=True,
            )
            print(f"Data layer {layer.name} (id={layer.id}): {result}")

    db.commit()
    return Map(id=new_map.id, name=new_map.name, data_field_config=new_map.data_field_config)


@maps_router.get("", response_model=list[Map])
def list_maps(
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """List maps."""
    map_roles = permission_service.list_map_roles(user_id=current_user.id)
    return [
        Map(id=_map.id, name=_map.name, data_field_config=_map.data_field_config)
        for _map in db.execute(
            select(MapModel).where(MapModel.id.in_([mr.map_id for mr in map_roles]))
        )
        .scalars()
        .all()
    ]
