"""Build a blank assignment CSV listing every (filler_zip, poly_index) from the manifest.

Reads `output/manifest.json` + each per-zip geojson, emits a CSV row per target
polygon with centroid/area filled in and `assigned_to_zip` left blank. Ordered
by filler_zip, poly_index. Matches the column layout the UI exports.
"""

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUTPUT_DIR = HERE / "output"
DEFAULT_OUT = HERE / "mx-mappings" / "all-polygons.csv"

HEADER = [
    "filler_zip",
    "poly_index",
    "assigned_to_zip",
    "centroid_lon",
    "centroid_lat",
    "area_m2",
]


def main() -> int:
    manifest = json.loads((OUTPUT_DIR / "manifest.json").read_text())

    rows: list[list[str]] = []
    for entry in manifest["zips"]:
        zip_code = entry["zip_code"]
        data = json.loads((OUTPUT_DIR / entry["file"]).read_text())
        for f in data["features"]:
            if f["properties"].get("kind") != "target":
                continue
            p = f["properties"]
            lon, lat = p["centroid"]
            rows.append([
                zip_code,
                str(p["poly_index"]),
                "",
                f"{lon:.7f}",
                f"{lat:.7f}",
                f"{p['area_m2']:.2f}",
            ])

    rows.sort(key=lambda r: (r[0], int(r[1])))

    DEFAULT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with DEFAULT_OUT.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows → {DEFAULT_OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
