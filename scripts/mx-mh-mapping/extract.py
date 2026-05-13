"""Extract MX/MH zip filler polygons + neighboring real zips into per-zip GeoJSON files.

Each filler zip (zip_code ending in 'MX' or 'MH') gets its own GeoJSON file in
`output/<zip>.geojson`. The file is a FeatureCollection mixing two feature kinds:

  - kind="target"   one filler polygon to be reassigned. id = "<zip>:<poly_index>".
  - kind="neighbor" one real zip shown for context. id = "<zip>".

A `manifest.json` lists every zip processed (with target/neighbor counts) so the
UI can iterate through them.

Usage:
  python extract.py                  # process all MX/MH zips
  python extract.py --zip 890MX      # process one zip (good for smoke-testing)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


DEFAULT_DSN = "postgresql://terramaps:terramaps@localhost:15433/app"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "output"
DEFAULT_TOLERANCE_DEG = 0.0005  # ~50m at mid-latitudes; covers floating-point gaps


LIST_FILLER_ZIPS_SQL = """
SELECT zip_code
FROM geography_zip_codes
WHERE zip_code LIKE '%%MX' OR zip_code LIKE '%%MH'
ORDER BY zip_code;
"""


TARGETS_FOR_ZIP_SQL = """
WITH exploded AS (
    SELECT
        COALESCE((d).path[1], 1) - 1 AS poly_index,
        (d).geom AS poly_geom
    FROM geography_zip_codes f,
    LATERAL ST_Dump(f.geom) AS d
    WHERE f.zip_code = %(zip)s
)
SELECT
    e.poly_index,
    ST_AsGeoJSON(e.poly_geom)::json AS geometry,
    ST_X(ST_Centroid(e.poly_geom)) AS centroid_lon,
    ST_Y(ST_Centroid(e.poly_geom)) AS centroid_lat,
    ST_Area(e.poly_geom::geography) AS area_m2,
    COALESCE(
        (
            SELECT array_agg(z.zip_code ORDER BY z.zip_code)
            FROM geography_zip_codes z
            WHERE z.zip_code != %(zip)s
              AND z.zip_code NOT LIKE '%%MX'
              AND z.zip_code NOT LIKE '%%MH'
              AND ST_DWithin(z.geom, e.poly_geom, %(tol)s)
        ),
        ARRAY[]::text[]
    ) AS neighbor_zips
FROM exploded e
ORDER BY e.poly_index;
"""


NEIGHBORS_SQL = """
SELECT
    z.zip_code,
    ST_AsGeoJSON(z.geom)::json AS geometry
FROM geography_zip_codes z
WHERE z.zip_code = ANY(%(zips)s);
"""


def process_zip(cur, zip_code: str, tolerance: float) -> dict:
    """Build a FeatureCollection for one filler zip. Returns the dict (caller writes it)."""
    cur.execute(TARGETS_FOR_ZIP_SQL, {"zip": zip_code, "tol": tolerance})
    target_rows = cur.fetchall()

    unique_neighbor_zips = sorted({
        z for r in target_rows for z in (r["neighbor_zips"] or [])
    })

    cur.execute(NEIGHBORS_SQL, {"zips": unique_neighbor_zips})
    neighbor_rows = cur.fetchall()

    features: list[dict] = []
    for r in target_rows:
        features.append({
            "type": "Feature",
            "id": f"{zip_code}:{r['poly_index']}",
            "geometry": r["geometry"],
            "properties": {
                "kind": "target",
                "zip_code": zip_code,
                "poly_index": r["poly_index"],
                "centroid": [r["centroid_lon"], r["centroid_lat"]],
                "area_m2": r["area_m2"],
                "neighbor_zips": r["neighbor_zips"] or [],
            },
        })
    for r in neighbor_rows:
        features.append({
            "type": "Feature",
            "id": r["zip_code"],
            "geometry": r["geometry"],
            "properties": {
                "kind": "neighbor",
                "zip_code": r["zip_code"],
            },
        })

    return {
        "type": "FeatureCollection",
        "filler_zip": zip_code,
        "target_count": len(target_rows),
        "neighbor_count": len(neighbor_rows),
        "features": features,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_URL", DEFAULT_DSN),
        help="Postgres DSN. Default: %(default)s (or $DATABASE_URL).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory. Default: %(default)s.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE_DEG,
        help="Neighbor search tolerance in degrees (default ~50m).",
    )
    parser.add_argument(
        "--zip",
        action="append",
        dest="zips",
        help="Filler zip code(s) to process. May be repeated. Default: all MX/MH zips.",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to {args.dsn}", file=sys.stderr)
    with psycopg.connect(args.dsn, row_factory=dict_row) as conn, conn.cursor() as cur:
        if args.zips:
            zips = args.zips
        else:
            cur.execute(LIST_FILLER_ZIPS_SQL)
            zips = [r["zip_code"] for r in cur.fetchall()]
        print(f"Processing {len(zips)} filler zip(s)", file=sys.stderr)

        manifest: list[dict] = []
        for i, zip_code in enumerate(zips, start=1):
            t0 = time.monotonic()
            collection = process_zip(cur, zip_code, args.tolerance)
            out_path = args.out_dir / f"{zip_code}.geojson"
            with out_path.open("w") as f:
                json.dump(collection, f)
            size_kb = out_path.stat().st_size / 1024
            elapsed = time.monotonic() - t0
            print(
                f"  [{i}/{len(zips)}] {zip_code}: "
                f"{collection['target_count']} polys, "
                f"{collection['neighbor_count']} neighbors, "
                f"{size_kb:.0f} KB ({elapsed:.1f}s)",
                file=sys.stderr,
            )
            manifest.append({
                "zip_code": zip_code,
                "target_count": collection["target_count"],
                "neighbor_count": collection["neighbor_count"],
                "file": f"{zip_code}.geojson",
            })

    manifest_path = args.out_dir / "manifest.json"
    with manifest_path.open("w") as f:
        json.dump({"zips": manifest}, f, indent=2)
    print(f"Wrote manifest with {len(manifest)} zips → {manifest_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
