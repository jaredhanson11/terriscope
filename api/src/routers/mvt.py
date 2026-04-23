"""MVT (Mapbox Vector Tile) router for rendering geographic data."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from src.app.database import DatabaseSession
from src.models.graph import LayerModel
from src.services import mvt_cache

mvt_router = APIRouter(prefix="/tiles", tags=["MVT"])

_FILTER_BOUNDS_CTE = """
    filter_bounds AS (
        SELECT ST_Transform(
            ST_Expand(
                (SELECT geom FROM tile_bounds),
                ST_Distance(
                    ST_Point(ST_XMin((SELECT geom FROM tile_bounds)), ST_YMin((SELECT geom FROM tile_bounds))),
                    ST_Point(ST_XMax((SELECT geom FROM tile_bounds)), ST_YMax((SELECT geom FROM tile_bounds)))
                ) * 0.1
            ),
            4326
        ) AS geom
    )"""


def _make_node_query(col: Literal["geom_z3", "geom_z7", "geom_z11"]) -> TextClause:
    return text(f"""
        WITH tile_bounds AS (
            SELECT ST_TileEnvelope(:z, :x, :y) AS geom
        ),
        {_FILTER_BOUNDS_CTE},
        tile_data AS (
            SELECT
                n.id,
                n.name,
                n.color,
                ST_AsMVTGeom(
                    ST_Transform(n.{col}, 3857),
                    (SELECT geom FROM tile_bounds),
                    4096, 256, true
                ) AS geom
            FROM nodes n
            WHERE n.layer_id = :layer_id
              AND n.{col} IS NOT NULL
              AND ST_Intersects(n.{col}, (SELECT geom FROM filter_bounds))
        )
        SELECT ST_AsMVT(tile_data, 'nodes', 4096, 'geom', 'id')
        FROM tile_data
        WHERE tile_data.geom IS NOT NULL;
    """)  # noqa: S608, literal not user allowed string


def _make_zip_query(col: Literal["geom_z3", "geom_z7", "geom_z11"]) -> TextClause:
    return text(f"""
        WITH tile_bounds AS (
            SELECT ST_TileEnvelope(:z, :x, :y) AS geom
        ),
        {_FILTER_BOUNDS_CTE},
        tile_data AS (
            SELECT
                gz.zip_code,
                COALESCE(za.color, '#FFFFFF') AS color,
                za.parent_node_id,
                ST_AsMVTGeom(
                    ST_Transform(gz.{col}, 3857),
                    (SELECT geom FROM tile_bounds),
                    4096, 256, true
                ) AS geom
            FROM geography_zip_codes gz
            LEFT JOIN zip_assignments za
                ON za.zip_code = gz.zip_code
                AND za.layer_id = :layer_id
            WHERE gz.{col} IS NOT NULL
              AND ST_Intersects(gz.{col}, (SELECT geom FROM filter_bounds))
        )
        SELECT ST_AsMVT(tile_data, 'zips', 4096, 'geom')
        FROM tile_data
        WHERE tile_data.geom IS NOT NULL;
    """)  # noqa: S608, literal not user allowed string


_NODE_TILE_QUERY_Z3 = _make_node_query("geom_z3")
_NODE_TILE_QUERY_Z7 = _make_node_query("geom_z7")
_NODE_TILE_QUERY_Z11 = _make_node_query("geom_z11")

_ZIP_TILE_QUERY_Z3 = _make_zip_query("geom_z3")
_ZIP_TILE_QUERY_Z7 = _make_zip_query("geom_z7")
_ZIP_TILE_QUERY_Z11 = _make_zip_query("geom_z11")


def _pick_node_tile_query(z: int) -> TextClause:
    if z <= 3:
        return _NODE_TILE_QUERY_Z3
    if z <= 7:
        return _NODE_TILE_QUERY_Z7
    return _NODE_TILE_QUERY_Z11


def _pick_zip_tile_query(z: int) -> TextClause:
    if z <= 3:
        return _ZIP_TILE_QUERY_Z3
    if z <= 7:
        return _ZIP_TILE_QUERY_Z7
    return _ZIP_TILE_QUERY_Z11


@mvt_router.get("/{layer_id}/{z}/{x}/{y}.pbf")
def get_tile(
    layer_id: int,
    z: int,
    x: int,
    y: int,
    db: DatabaseSession,
):
    """Get a vector tile for a specific layer at the given tile coordinates.

    For order=0 (zip) layers: queries geography_zip_codes LEFT JOIN zip_assignments.
    For order>=1 layers: queries pre-computed node geometries.
    """
    if z < 3 or z > 11:
        raise HTTPException(status_code=400, detail="Invalid zoom level")

    cached = mvt_cache.get_tile(db, layer_id, "fill", z, x, y)
    if cached is not None:
        return Response(
            content=cached,
            media_type="application/x-protobuf",
            headers={
                "Content-Type": "application/x-protobuf",
                "Cache-Control": "public, max-age=86400",
            },
        )

    layer = db.get(LayerModel, layer_id)
    if layer is None:
        raise HTTPException(status_code=404, detail="Layer not found")

    query = _pick_zip_tile_query(z) if layer.order == 0 else _pick_node_tile_query(z)
    result = db.execute(query, {"layer_id": layer_id, "z": z, "x": x, "y": y}).scalar()
    tile_bytes = bytes(result) if result else b""

    mvt_cache.save_tile(db, layer_id, "fill", z, x, y, tile_bytes)

    return Response(
        content=tile_bytes,
        media_type="application/x-protobuf",
        headers={
            "Content-Type": "application/x-protobuf",
            "Cache-Control": "public, max-age=86400",
        },
    )
