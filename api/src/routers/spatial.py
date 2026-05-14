"""Router for spatial operations."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select, text

from src.app.database import DatabaseSession
from src.models.graph import LayerModel, MapModel, NodeModel
from src.schemas.dtos.spatial import (
    SpatialSelectRequest,
    SpatialSelectResponse,
    SpatialSummaryRequest,
    SpatialSummaryResponse,
)
from src.services.auth import CurrentUserDependency
from src.services.computation import ComputationServiceDependency
from src.services.permissions import PermissionsServiceDependency

spatial_router = APIRouter(prefix="/spatial", tags=["Spatial"])


@spatial_router.post("/select", response_model=SpatialSelectResponse)
def select_features_in_lasso(
    selection: SpatialSelectRequest,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
):
    """Select all features from a layer that intersect with a lasso polygon.

    For order=0 (zip) layers: returns zip_codes (strings) from geography_zip_codes.
    For order>=1 layers: returns node IDs (integers) from nodes.
    """
    layer = db.get(LayerModel, selection.layer_id)
    if layer is None:
        raise HTTPException(status_code=404, detail="Layer not found")
    if not permission_service.check_for_map_access(
        user_id=current_user.id, map_id=layer.map_id, map_roles=["OWNER", "MEMBER"]
    ):
        raise HTTPException(status_code=403)

    polygon_geojson = selection.polygon.model_dump_json()

    if layer.order == 0:
        # Zip layer: intersect against geography_zip_codes geometries.
        # The lasso polygon arrives as 4326 GeoJSON; project it once into the
        # storage CRS (3857) so the intersect runs against the indexed column.
        result = db.execute(
            text("""
                SELECT
                    COUNT(*) AS count,
                    ARRAY_AGG(gz.zip_code ORDER BY gz.zip_code) AS zip_codes
                FROM geography_zip_codes gz
                WHERE gz.geom_z11_merc IS NOT NULL
                  AND ST_Intersects(gz.geom_z11_merc, ST_Transform(ST_GeomFromGeoJSON(:polygon), 3857))
            """),
            {"polygon": polygon_geojson},
        ).one()
        count = result.count or 0
        zip_codes = list(result.zip_codes) if result.zip_codes else []
        return SpatialSelectResponse(count=count, nodes=[], zip_codes=zip_codes)

    # Node layer: intersect against node geometries
    count, ids = (
        db.execute(
            select(
                func.count(NodeModel.id).label("count"),
                func.array_agg(NodeModel.id).label("ids"),
            ).where(
                NodeModel.layer_id == selection.layer_id,
                NodeModel.geom_z11_merc.isnot(None),
                func.ST_Intersects(
                    NodeModel.geom_z11_merc,
                    func.ST_Transform(func.ST_GeomFromGeoJSON(polygon_geojson), 3857),
                ),
            )
        )
        .tuples()
        .one()
    )
    return SpatialSelectResponse(count=count or 0, nodes=list[int](ids or []))


@spatial_router.post("/summary", response_model=SpatialSummaryResponse)
def summarize_selection(
    selection: SpatialSummaryRequest,
    db: DatabaseSession,
    current_user: CurrentUserDependency,
    permission_service: PermissionsServiceDependency,
    computation_service: ComputationServiceDependency,
):
    """Roll up `data` across a selection of zips (order=0) or nodes (order>=1).

    Mirrors the rollup math used by the recompute task: sum-of-sums, naive
    avg-of-avgs, min-of-mins, max-of-maxes — so a selection of children shows
    the same numbers their shared parent would.
    """
    layer = db.get(LayerModel, selection.layer_id)
    if layer is None:
        raise HTTPException(status_code=404, detail="Layer not found")
    if not permission_service.check_for_map_access(
        user_id=current_user.id, map_id=layer.map_id, map_roles=["OWNER", "MEMBER"]
    ):
        raise HTTPException(status_code=403)

    if layer.order == 0:
        if not selection.zip_codes:
            return SpatialSummaryResponse(count=0, data={})
        count = len(selection.zip_codes)
    else:
        if not selection.node_ids:
            return SpatialSummaryResponse(count=0, data={})
        count = len(selection.node_ids)

    map_model = db.get(MapModel, layer.map_id)
    fields = [
        f for f in (map_model.data_field_config or [])
        if f.get("type") == "number" and f.get("aggregations")
    ] if map_model else []

    data = computation_service.compute_summary_for_selection(
        layer=layer,
        fields=fields,
        node_ids=selection.node_ids if layer.order > 0 else None,
        zip_codes=selection.zip_codes if layer.order == 0 else None,
    )
    return SpatialSummaryResponse(count=count, data=data)
