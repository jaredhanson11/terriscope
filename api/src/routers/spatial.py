"""Router for spatial operations."""

from fastapi import APIRouter
from sqlalchemy import func, select

from src.app.database import DatabaseSession
from src.models.graph import NodeModel
from src.schemas.dtos.spatial import SpatialSelectRequest, SpatialSelectResponse

spatial_router = APIRouter(prefix="/spatial", tags=["Spatial"])


@spatial_router.post("/select", response_model=SpatialSelectResponse)
def select_features_in_lasso(selection: SpatialSelectRequest, db: DatabaseSession):
    """Select all features from a layer that intersect with a lasso polygon."""
    count, ids = (
        db.execute(
            select(
                func.count(NodeModel.id).label("count"),
                func.array_agg(NodeModel.id).label("ids"),
            ).where(
                NodeModel.layer_id == selection.layer_id,
                NodeModel.geom.isnot(None),
                func.ST_Intersects(
                    NodeModel.geom,
                    func.ST_GeomFromGeoJSON(
                        selection.polygon.model_dump_json(),
                    ),
                ),
            )
        )
        .tuples()
        .one()
    )
    return SpatialSelectResponse(count=count, nodes=list[int](ids))
