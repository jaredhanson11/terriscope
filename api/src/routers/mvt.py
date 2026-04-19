"""MVT (Mapbox Vector Tile) router for rendering geographic data."""

import threading
from collections import OrderedDict

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select, text

from src.app.database import DatabaseSession
from src.models.graph import LayerModel, MapModel

mvt_router = APIRouter(prefix="/tiles", tags=["MVT"])

# ---------------------------------------------------------------------------
# In-process LRU tile cache
# Keys: (layer_id, endpoint, z, x, y, rev)
# Values: raw protobuf bytes
# Invalidated naturally because the frontend cache-busts with ?rev={tile_version}.
# ---------------------------------------------------------------------------
_TILE_CACHE_MAX = 2048
_tile_cache: OrderedDict[tuple, bytes] = OrderedDict()
_tile_cache_lock = threading.Lock()


def _cache_get(key: tuple) -> bytes | None:
    with _tile_cache_lock:
        value = _tile_cache.get(key)
        if value is not None:
            _tile_cache.move_to_end(key)
        return value


def _cache_set(key: tuple, value: bytes) -> None:
    with _tile_cache_lock:
        _tile_cache[key] = value
        _tile_cache.move_to_end(key)
        while len(_tile_cache) > _TILE_CACHE_MAX:
            _tile_cache.popitem(last=False)


@mvt_router.get("/{layer_id}/{z}/{x}/{y}.pbf")
def get_tile(
    layer_id: int,
    z: int,
    x: int,
    y: int,
    db: DatabaseSession,
    rev: int = Query(default=0),
):
    """Get a vector tile for a specific layer at the given tile coordinates.

    For order=0 (zip) layers: queries geography_zip_codes LEFT JOIN zip_assignments.
    For order>=1 layers: queries pre-computed node geometries.
    """
    if z < 0 or z > 20:
        raise HTTPException(status_code=400, detail="Invalid zoom level")

    cache_key = (layer_id, "fill", z, x, y, rev)
    cached = _cache_get(cache_key)
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

    if layer.order == 0:
        query = text("""
            WITH tile_bounds AS (
                SELECT ST_TileEnvelope(:z, :x, :y) AS geom
            ),
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
            ),
            tile_data AS (
                SELECT
                    gz.zip_code,
                    COALESCE(za.color, '#FFFFFF') AS color,
                    za.parent_node_id,
                    ST_AsMVTGeom(
                        ST_Transform(
                            CASE
                                WHEN :z <= 3  THEN CASE WHEN gz.geom_z3  IS NOT NULL AND NOT ST_IsEmpty(gz.geom_z3)  THEN gz.geom_z3  ELSE gz.geom END
                                WHEN :z <= 7  THEN CASE WHEN gz.geom_z7  IS NOT NULL AND NOT ST_IsEmpty(gz.geom_z7)  THEN gz.geom_z7  ELSE gz.geom END
                                WHEN :z <= 11 THEN CASE WHEN gz.geom_z11 IS NOT NULL AND NOT ST_IsEmpty(gz.geom_z11) THEN gz.geom_z11 ELSE gz.geom END
                                WHEN :z <= 15 THEN CASE WHEN gz.geom_z15 IS NOT NULL AND NOT ST_IsEmpty(gz.geom_z15) THEN gz.geom_z15 ELSE gz.geom END
                                ELSE gz.geom
                            END,
                            3857
                        ),
                        (SELECT geom FROM tile_bounds),
                        4096,
                        256,
                        true
                    ) AS geom
                FROM geography_zip_codes gz
                LEFT JOIN zip_assignments za
                    ON za.zip_code = gz.zip_code
                    AND za.layer_id = :layer_id
                WHERE gz.geom IS NOT NULL
                  AND ST_Intersects(gz.geom, (SELECT geom FROM filter_bounds))
            )
            SELECT ST_AsMVT(tile_data, 'zips', 4096, 'geom')
            FROM tile_data
            WHERE tile_data.geom IS NOT NULL;
        """)
    else:
        query = text("""
            WITH tile_bounds AS (
                SELECT ST_TileEnvelope(:z, :x, :y) AS geom
            ),
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
            ),
            tile_data AS (
                SELECT
                    n.id,
                    n.name,
                    n.color,
                    ST_AsMVTGeom(
                        ST_Transform(
                            CASE
                                WHEN :z <= 3  THEN CASE WHEN n.geom_z3  IS NOT NULL AND NOT ST_IsEmpty(n.geom_z3)  THEN n.geom_z3  ELSE n.geom END
                                WHEN :z <= 7  THEN CASE WHEN n.geom_z7  IS NOT NULL AND NOT ST_IsEmpty(n.geom_z7)  THEN n.geom_z7  ELSE n.geom END
                                WHEN :z <= 11 THEN CASE WHEN n.geom_z11 IS NOT NULL AND NOT ST_IsEmpty(n.geom_z11) THEN n.geom_z11 ELSE n.geom END
                                WHEN :z <= 15 THEN CASE WHEN n.geom_z15 IS NOT NULL AND NOT ST_IsEmpty(n.geom_z15) THEN n.geom_z15 ELSE n.geom END
                                ELSE n.geom
                            END,
                            3857
                        ),
                        (SELECT geom FROM tile_bounds),
                        4096,
                        256,
                        true
                    ) AS geom
                FROM nodes n
                WHERE n.layer_id = :layer_id
                  AND n.geom IS NOT NULL
                  AND ST_Intersects(n.geom, (SELECT geom FROM filter_bounds))
            )
            SELECT ST_AsMVT(tile_data, 'nodes', 4096, 'geom', 'id')
            FROM tile_data
            WHERE tile_data.geom IS NOT NULL;
        """)

    result = db.execute(query, {"layer_id": layer_id, "z": z, "x": x, "y": y}).scalar()
    tile_bytes = bytes(result) if result else b""

    _cache_set(cache_key, tile_bytes)

    return Response(
        content=tile_bytes,
        media_type="application/x-protobuf",
        headers={
            "Content-Type": "application/x-protobuf",
            "Cache-Control": "public, max-age=86400",
        },
    )


@mvt_router.get("/{layer_id}/{z}/{x}/{y}/labels.pbf")
def get_label_tile(
    layer_id: int,
    z: int,
    x: int,
    y: int,
    db: DatabaseSession,
    rev: int = Query(default=0),
):
    """Get a label tile for a specific layer using point-on-surface geometries.

    For order=0 (zip) layers: one point per zip code, label is the zip_code string.
    For order>=1 layers: one point per node with all configured data field values.
    """
    if z < 0 or z > 20:
        raise HTTPException(status_code=400, detail="Invalid zoom level")

    cache_key = (layer_id, "label", z, x, y, rev)
    cached = _cache_get(cache_key)
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

    if layer.order == 0:
        query = text("""
            WITH tile_bounds AS (
                SELECT ST_TileEnvelope(:z, :x, :y) AS geom
            ),
            filter_bounds AS (
                SELECT ST_Transform((SELECT geom FROM tile_bounds), 4326) AS geom
            ),
            label_points AS (
                SELECT
                    gz.zip_code AS name,
                    ST_Transform(ST_PointOnSurface(gz.geom), 3857) AS pt
                FROM geography_zip_codes gz
                WHERE gz.geom IS NOT NULL
                  AND ST_Intersects(gz.geom, (SELECT geom FROM filter_bounds))
            ),
            tile_data AS (
                SELECT
                    lp.name,
                    ST_AsMVTGeom(lp.pt, (SELECT geom FROM tile_bounds), 4096, 0, false) AS geom
                FROM label_points lp
                WHERE ST_Intersects(lp.pt, (SELECT geom FROM tile_bounds))
            )
            SELECT ST_AsMVT(tile_data, 'zips', 4096, 'geom')
            FROM tile_data
            WHERE tile_data.geom IS NOT NULL;
        """)

        result = db.execute(query, {"layer_id": layer_id, "z": z, "x": x, "y": y}).scalar()
    else:
        data_field_config = db.execute(
            select(MapModel.data_field_config)
            .join(LayerModel, LayerModel.map_id == MapModel.id)
            .where(LayerModel.id == layer_id)
        ).scalar()

        extra_label_selects = ""
        extra_tile_selects = ""
        if data_field_config:
            for field_config in data_field_config:
                for agg in field_config.get("aggregations", []):
                    key = f"{field_config['field']}_{agg}"
                    extra_label_selects += f',\n                n.data->>{key!r} AS "{key}"'
                    extra_tile_selects += f',\n                lp."{key}"'

        query = text(f"""
            WITH tile_bounds AS (
                SELECT ST_TileEnvelope(:z, :x, :y) AS geom
            ),
            filter_bounds AS (
                SELECT ST_Transform((SELECT geom FROM tile_bounds), 4326) AS geom
            ),
            label_points AS (
                SELECT
                    n.id,
                    n.name{extra_label_selects},
                    ST_Transform(ST_PointOnSurface(n.geom), 3857) AS pt
                FROM nodes n
                WHERE n.layer_id = :layer_id
                  AND n.geom IS NOT NULL
                  AND ST_Intersects(n.geom, (SELECT geom FROM filter_bounds))
            ),
            tile_data AS (
                SELECT
                    lp.id,
                    lp.name{extra_tile_selects},
                    ST_AsMVTGeom(lp.pt, (SELECT geom FROM tile_bounds), 4096, 0, false) AS geom
                FROM label_points lp
                WHERE ST_Intersects(lp.pt, (SELECT geom FROM tile_bounds))
            )
            SELECT ST_AsMVT(tile_data, 'nodes', 4096, 'geom', 'id')
            FROM tile_data
            WHERE tile_data.geom IS NOT NULL;
        """)

        result = db.execute(query, {"layer_id": layer_id, "z": z, "x": x, "y": y}).scalar()

    tile_bytes = bytes(result) if result else b""
    _cache_set(cache_key, tile_bytes)

    return Response(
        content=tile_bytes,
        media_type="application/x-protobuf",
        headers={
            "Content-Type": "application/x-protobuf",
            "Cache-Control": "public, max-age=86400",
        },
    )


@mvt_router.get("/layers")
def list_tile_layers(db: DatabaseSession):
    """List all available layers that can be rendered as tiles.

    Returns a list of layers with their IDs and names, which can be used
    to construct tile URLs.
    """
    query = text("""
        SELECT
            l.id,
            l.name,
            l.order,
            COUNT(n.id) as node_count
        FROM layers l
        LEFT JOIN nodes n ON n.layer_id = l.id AND n.geom IS NOT NULL
        GROUP BY l.id, l.name, l.order
        ORDER BY l.order
    """)

    result = db.execute(query).mappings().all()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "order": row["order"],
            "node_count": row["node_count"],
            "tile_url": f"/tiles/{row['id']}/{{z}}/{{x}}/{{y}}.pbf",
        }
        for row in result
    ]
