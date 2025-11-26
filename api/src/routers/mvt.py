"""MVT (Mapbox Vector Tile) router for rendering geographic data."""

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import text

from src.app.database import DatabaseSession

mvt_router = APIRouter(prefix="/tiles", tags=["MVT"])


@mvt_router.get("/{layer_id}/{z}/{x}/{y}.pbf")
def get_tile(layer_id: int, z: int, x: int, y: int, db: DatabaseSession):
    """Get a vector tile for a specific layer at the given tile coordinates.

    Args:
        layer_id: The layer ID to render nodes from
        z: Zoom level
        x: Tile X coordinate
        y: Tile Y coordinate
        db: Database session

    Returns:
        Mapbox Vector Tile (MVT) in protobuf format
    """
    # Validate zoom level
    if z < 0 or z > 20:
        raise HTTPException(status_code=400, detail="Invalid zoom level")

    # Query to generate MVT using PostGIS
    # For nodes with geometry: use their geometry directly (leaf nodes)
    # For nodes without geometry: compute ST_Union of all descendant leaf geometries
    query = text("""
        WITH RECURSIVE tile_bounds AS (
            SELECT ST_TileEnvelope(:z, :x, :y) AS geom
        ),
        expanded_bounds AS (
            SELECT ST_Expand(geom, ST_Distance(
                ST_Point(ST_XMin(geom), ST_YMin(geom)),
                ST_Point(ST_XMax(geom), ST_YMax(geom))
            ) * 0.1) AS geom
            FROM tile_bounds
        ),
        descendants AS (
            -- Base case: nodes in the target layer
            SELECT
                id,
                id as root_id,
                name,
                color,
                geom,
                parent_node_id
            FROM nodes
            WHERE layer_id = :layer_id

            UNION ALL

            -- Recursive case: find all descendants
            SELECT
                n.id,
                d.root_id,
                n.name,
                n.color,
                n.geom,
                n.parent_node_id
            FROM nodes n
            INNER JOIN descendants d ON n.parent_node_id = d.id
        ),
        node_geometries AS (
            SELECT
                d.root_id,
                n.name,
                n.color,
                -- If the root node has geometry, use it; otherwise union all leaf descendants
                CASE
                    WHEN n.geom IS NOT NULL
                    THEN n.geom
                    ELSE ST_Union(ST_MakeValid(d.geom))
                END as geom
            FROM descendants d
            INNER JOIN nodes n ON n.id = d.root_id
            WHERE d.geom IS NOT NULL  -- Only include descendants with actual geometry
            GROUP BY d.root_id, n.name, n.color, n.geom
        ),
        tile_data AS (
            SELECT
                ng.root_id as id,
                ng.name,
                ng.color,
                ST_AsMVTGeom(
                    ST_Transform(ng.geom, 3857),
                    (SELECT geom FROM tile_bounds),
                    4096,
                    256,
                    true
                ) AS geom
            FROM node_geometries ng, expanded_bounds
            WHERE ng.geom IS NOT NULL
                AND ST_Intersects(
                    ST_Transform(ng.geom, 3857),
                    expanded_bounds.geom
                )
        )
        SELECT ST_AsMVT(tile_data, 'nodes', 4096, 'geom')
        FROM tile_data
        WHERE tile_data.geom IS NOT NULL;
    """)

    result = db.execute(query, {"layer_id": layer_id, "z": z, "x": x, "y": y}).scalar()

    # Return empty tile if no data found
    if result is None:
        result = b""

    return Response(
        content=bytes(result),
        media_type="application/x-protobuf",
        headers={
            "Content-Type": "application/x-protobuf",
            "Cache-Control": "public, max-age=3600",
        },
    )


@mvt_router.get("/debug/colors/{layer_id}")
def debug_layer_colors(layer_id: int, db: DatabaseSession):
    """Debug endpoint to check if color values exist in the database."""
    query = text("""
        SELECT
            id,
            name,
            color,
            CASE WHEN color IS NULL THEN 'NULL'
                 WHEN color = '' THEN 'EMPTY'
                 ELSE 'HAS_VALUE'
            END as color_status
        FROM nodes
        WHERE layer_id = :layer_id
        LIMIT 10
    """)

    result = db.execute(query, {"layer_id": layer_id}).mappings().all()

    return {"layer_id": layer_id, "sample_nodes": [dict(row) for row in result]}


@mvt_router.get("/debug/tile/{layer_id}/{z}/{x}/{y}")
def debug_tile_data(layer_id: int, z: int, x: int, y: int, db: DatabaseSession):
    """Debug endpoint to see what data would be in a tile (as JSON instead of MVT)."""
    query = text("""
        WITH tile_bounds AS (
            SELECT ST_TileEnvelope(:z, :x, :y) AS geom
        ),
        expanded_bounds AS (
            SELECT ST_Expand(geom, ST_Distance(
                ST_Point(ST_XMin(geom), ST_YMin(geom)),
                ST_Point(ST_XMax(geom), ST_YMax(geom))
            ) * 0.1) AS geom
            FROM tile_bounds
        )
        SELECT
            nodes.id,
            nodes.name,
            nodes.color,
            ST_AsGeoJSON(nodes.geom) as geom_json
        FROM nodes, expanded_bounds
        WHERE nodes.layer_id = :layer_id
            AND nodes.geom IS NOT NULL
            AND ST_Intersects(
                ST_Transform(nodes.geom, 3857),
                expanded_bounds.geom
            )
        LIMIT 5
    """)

    result = db.execute(query, {"layer_id": layer_id, "z": z, "x": x, "y": y}).mappings().all()

    return {
        "layer_id": layer_id,
        "tile": f"{z}/{x}/{y}",
        "features_in_tile": len(result),
        "sample_features": [
            {"id": row["id"], "name": row["name"], "color": row["color"], "has_geom": row["geom_json"] is not None}
            for row in result
        ],
    }


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
            "tile_url": f"/tiles/{row["id"]}/{{z}}/{{x}}/{{y}}.pbf",
        }
        for row in result
    ]


@mvt_router.get("/diagnostics/geometry-stats")
def get_geometry_stats(db: DatabaseSession, layer_id: int | None = None):
    """Get detailed statistics about polygon complexity to diagnose performance issues.

    This endpoint helps identify problematic geometries that might be causing
    database crashes or slow queries.
    """
    if layer_id:
        layer_filter = "WHERE layer_id = :layer_id"
        params = {"layer_id": layer_id}
    else:
        layer_filter = ""
        params = {}

    query = text(
        """
        SELECT
            layer_id,
            COUNT(*) as total_nodes,
            COUNT(CASE WHEN geom IS NOT NULL THEN 1 END) as nodes_with_geom,
            -- Polygon complexity metrics
            MIN(ST_NPoints(geom)) as min_points,
            MAX(ST_NPoints(geom)) as max_points,
            AVG(ST_NPoints(geom))::int as avg_points,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ST_NPoints(geom))::int as median_points,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY ST_NPoints(geom))::int as p95_points,
            -- Find extremely complex geometries
            COUNT(CASE WHEN ST_NPoints(geom) > 10000 THEN 1 END) as nodes_over_10k_points,
            COUNT(CASE WHEN ST_NPoints(geom) > 50000 THEN 1 END) as nodes_over_50k_points,
            COUNT(CASE WHEN ST_NPoints(geom) > 100000 THEN 1 END) as nodes_over_100k_points,
            -- Size metrics
            MIN(ST_MemSize(geom)) as min_size_bytes,
            MAX(ST_MemSize(geom)) as max_size_bytes,
            AVG(ST_MemSize(geom))::bigint as avg_size_bytes,
            SUM(ST_MemSize(geom))::bigint as total_size_bytes,
            -- Validity checks
            COUNT(CASE WHEN NOT ST_IsValid(geom) THEN 1 END) as invalid_geometries,
            -- Number of rings (exterior + holes)
            MAX(ST_NumGeometries(geom)) as max_polygons_in_multipolygon,
            AVG(ST_NumGeometries(geom))::numeric(10,2) as avg_polygons_in_multipolygon
        FROM nodes
        """
        + f" {layer_filter}"
        + """
        GROUP BY layer_id
        ORDER BY layer_id
    """
    )

    result = db.execute(query, params).mappings().all()

    return [
        {
            "layer_id": row["layer_id"],
            "total_nodes": row["total_nodes"],
            "nodes_with_geom": row["nodes_with_geom"],
            "complexity": {
                "min_points": row["min_points"],
                "max_points": row["max_points"],
                "avg_points": row["avg_points"],
                "median_points": row["median_points"],
                "p95_points": row["p95_points"],
            },
            "problematic_geometries": {
                "over_10k_points": row["nodes_over_10k_points"],
                "over_50k_points": row["nodes_over_50k_points"],
                "over_100k_points": row["nodes_over_100k_points"],
                "invalid": row["invalid_geometries"],
            },
            "size": {
                "min_bytes": row["min_size_bytes"],
                "max_bytes": row["max_size_bytes"],
                "avg_bytes": row["avg_size_bytes"],
                "total_bytes": row["total_size_bytes"],
                "total_mb": round(row["total_size_bytes"] / 1024 / 1024, 2) if row["total_size_bytes"] else 0,
            },
            "multipolygon_stats": {
                "max_polygons": row["max_polygons_in_multipolygon"],
                "avg_polygons": float(row["avg_polygons_in_multipolygon"])
                if row["avg_polygons_in_multipolygon"]
                else 0,
            },
        }
        for row in result
    ]


@mvt_router.get("/diagnostics/problematic-nodes")
def get_problematic_nodes(db: DatabaseSession, layer_id: int | None = None, min_points: int = 10000):
    """List nodes with overly complex geometries that might cause performance issues.

    Args:
        db: Database session
        layer_id: Optional layer to filter by
        min_points: Minimum number of points to be considered problematic (default: 10000)
    """
    params = {"min_points": min_points}
    if layer_id:
        layer_filter = "AND layer_id = :layer_id"
        params["layer_id"] = layer_id
    else:
        layer_filter = ""

    query = text(
        """
        SELECT
            id,
            name,
            layer_id,
            ST_NPoints(geom) as num_points,
            ST_MemSize(geom) as size_bytes,
            ST_NumGeometries(geom) as num_polygons,
            ST_IsValid(geom) as is_valid,
            CASE
                WHEN NOT ST_IsValid(geom) THEN ST_IsValidReason(geom)
                ELSE NULL
            END as invalid_reason
        FROM nodes
        WHERE geom IS NOT NULL
            AND ST_NPoints(geom) >= :min_points
        """
        + f" {layer_filter}"
        + """
        ORDER BY ST_NPoints(geom) DESC
        LIMIT 100
    """
    )

    result = db.execute(query, params).mappings().all()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "layer_id": row["layer_id"],
            "num_points": row["num_points"],
            "size_bytes": row["size_bytes"],
            "size_mb": round(row["size_bytes"] / 1024 / 1024, 2),
            "num_polygons": row["num_polygons"],
            "is_valid": row["is_valid"],
            "invalid_reason": row["invalid_reason"],
        }
        for row in result
    ]


@mvt_router.get("/diagnostics/node-stats/{node_id}")
def get_node_stats(node_id: int, db: DatabaseSession):
    """Get detailed statistics about a specific node's geometry.

    Args:
        node_id: The node ID to analyze
        db: Database session

    Returns:
        Dictionary with detailed geometry statistics including:
        - size_bytes: Raw geometry size in bytes
        - size_kb: Geometry size in kilobytes
        - num_vertices: Total number of vertices across all polygons
        - num_polygons: Number of polygons in the multipolygon
        - num_rings: Total number of rings (exterior + interior/holes)
        - avg_vertices_per_polygon: Average vertices per polygon
        - min_distance: Minimum distance between consecutive points (meters)
        - max_distance: Maximum distance between consecutive points (meters)
        - avg_distance: Average distance between consecutive points (meters)
        - median_distance: Median distance between consecutive points (meters)
        - coordinate_precision: Estimated decimal places in coordinates
        - is_valid: Whether geometry is topologically valid
        - invalid_reason: Reason if geometry is invalid
    """
    query = text(
        """
        WITH node_geom AS (
            SELECT
                id,
                name,
                layer_id,
                geom,
                -- Basic size metrics
                LENGTH(geom::bytea) as size_bytes,
                ST_NPoints(geom) as num_vertices,
                ST_NumGeometries(geom) as num_polygons,
                -- Validity
                ST_IsValid(geom) as is_valid,
                ST_IsValidReason(geom) as invalid_reason
            FROM nodes
            WHERE id = :node_id
        ),
        ring_stats AS (
            SELECT
                n.id,
                -- Count all rings (exterior + interior)
                SUM(ST_NumInteriorRings(geom_dump.geom) + 1) as num_rings
            FROM nodes n,
                LATERAL ST_Dump(n.geom) as geom_dump
            WHERE n.id = :node_id
            GROUP BY n.id
        ),
        point_distances AS (
            SELECT
                n.id,
                -- Calculate distances between consecutive points in meters
                -- Using ST_Distance with geography to get meters
                ST_Distance(
                    ST_Transform(point1, 4326)::geography,
                    ST_Transform(point2, 4326)::geography
                ) as distance_meters
            FROM nodes n,
                LATERAL ST_DumpPoints(n.geom) AS dp1,
                LATERAL (
                    SELECT ST_PointN(dp1.geom, generate_series(1, ST_NPoints(dp1.geom) - 1)) as point1
                ) pts1,
                LATERAL (
                    SELECT ST_PointN(dp1.geom, generate_series(2, ST_NPoints(dp1.geom))) as point2
                ) pts2
            WHERE n.id = :node_id
              AND point1 IS NOT NULL
              AND point2 IS NOT NULL
        ),
        distance_stats AS (
            SELECT
                id,
                MIN(distance_meters) as min_distance,
                MAX(distance_meters) as max_distance,
                AVG(distance_meters) as avg_distance,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY distance_meters) as median_distance
            FROM point_distances
            GROUP BY id
        ),
        coord_precision AS (
            SELECT
                n.id,
                -- Estimate coordinate precision by checking smallest coordinate differences
                -- Extract coordinates and find minimum non-zero decimal places
                MAX(
                    CASE
                        WHEN ABS(coord_diff) > 0 AND ABS(coord_diff) < 1
                        THEN CEIL(-LOG10(ABS(coord_diff)))
                        ELSE 0
                    END
                ) as estimated_precision
            FROM nodes n,
                LATERAL ST_DumpPoints(n.geom) AS dp,
                LATERAL (
                    SELECT
                        ST_X(dp.geom) - LAG(ST_X(dp.geom)) OVER (ORDER BY dp.path) as coord_diff
                    FROM (SELECT dp.geom, dp.path) sub
                    LIMIT 1000  -- Sample first 1000 points for performance
                ) diffs
            WHERE n.id = :node_id
              AND coord_diff IS NOT NULL
              AND ABS(coord_diff) > 0
            GROUP BY n.id
        )
        SELECT
            ng.id,
            ng.name,
            ng.layer_id,
            ng.size_bytes,
            ROUND(ng.size_bytes / 1024.0, 2) as size_kb,
            ng.num_vertices,
            ng.num_polygons,
            COALESCE(rs.num_rings, 0) as num_rings,
            CASE
                WHEN ng.num_polygons > 0
                THEN ROUND(ng.num_vertices::numeric / ng.num_polygons, 2)
                ELSE 0
            END as avg_vertices_per_polygon,
            COALESCE(ROUND(ds.min_distance::numeric, 4), 0) as min_distance_meters,
            COALESCE(ROUND(ds.max_distance::numeric, 4), 0) as max_distance_meters,
            COALESCE(ROUND(ds.avg_distance::numeric, 4), 0) as avg_distance_meters,
            COALESCE(ROUND(ds.median_distance::numeric, 4), 0) as median_distance_meters,
            COALESCE(cp.estimated_precision, 0) as estimated_coordinate_precision,
            ng.is_valid,
            ng.invalid_reason
        FROM node_geom ng
        LEFT JOIN ring_stats rs ON ng.id = rs.id
        LEFT JOIN distance_stats ds ON ng.id = ds.id
        LEFT JOIN coord_precision cp ON ng.id = cp.id
    """
    )

    result = db.execute(query, {"node_id": node_id}).mappings().first()

    if not result:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    return dict(result)
