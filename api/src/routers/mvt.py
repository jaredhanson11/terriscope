"""MVT (Mapbox Vector Tile) router for rendering geographic data."""

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from src.app.database import DatabaseSession
from src.models.graph import LayerModel, MapModel
from src.services import mvt_cache

mvt_router = APIRouter(prefix="/tiles", tags=["MVT"])

_SAFE_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SAFE_AGG_RE = re.compile(r"^(sum|avg|min|max)$")

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


def _extract_data_fields(
    config: list[dict[str, Any]] | None,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return validated (field_name, aggregations) pairs from data_field_config."""
    if not config:
        return ()
    result: list[tuple[str, tuple[str, ...]]] = []
    for f in config:
        fname = str(f.get("field", ""))
        raw_aggs: list[Any] = list(f.get("aggregations") or [])
        aggs: tuple[str, ...] = tuple(str(a) for a in raw_aggs if _SAFE_AGG_RE.match(str(a)))
        if _SAFE_FIELD_RE.match(fname) and aggs:
            result.append((fname, aggs))
    return tuple(result)


def _data_columns(fields: tuple[tuple[str, tuple[str, ...]], ...], alias: str) -> str:
    """Build extra SELECT column expressions for data fields, or empty string if none."""
    if not fields:
        return ""
    parts: list[str] = []
    for fname, aggs in fields:
        for agg in aggs:
            parts.append(f"({alias}.data->'{fname}'->>'{agg}')::numeric AS {fname}_{agg}")
    return ",\n                " + ",\n                ".join(parts)


def _node_query(col: str, data_fields: tuple[tuple[str, tuple[str, ...]], ...]) -> TextClause:
    extra = _data_columns(data_fields, "n")
    return text(f"""
        WITH tile_bounds AS (
            SELECT ST_TileEnvelope(:z, :x, :y) AS geom
        ),
        {_FILTER_BOUNDS_CTE},
        tile_data AS (
            SELECT
                n.id,
                n.name,
                n.color{extra},
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
    """)  # noqa: S608


def _zip_query(col: str, data_fields: tuple[tuple[str, tuple[str, ...]], ...]) -> TextClause:
    extra = _data_columns(data_fields, "za")
    return text(f"""
        WITH tile_bounds AS (
            SELECT ST_TileEnvelope(:z, :x, :y) AS geom
        ),
        {_FILTER_BOUNDS_CTE},
        tile_data AS (
            SELECT
                gz.zip_code,
                COALESCE(za.color, '#FFFFFF') AS color,
                za.parent_node_id{extra},
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
    """)  # noqa: S608


def _pick_zoom_col(z: int) -> str:
    if z <= 3:
        return "geom_z3"
    if z <= 7:
        return "geom_z7"
    return "geom_z11"


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
    Data fields from data_field_config are included as flat numeric properties.
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

    map_model = db.get(MapModel, layer.map_id)
    data_fields = _extract_data_fields(map_model.data_field_config if map_model else None)

    col = _pick_zoom_col(z)
    query = _zip_query(col, data_fields) if layer.order == 0 else _node_query(col, data_fields)
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
