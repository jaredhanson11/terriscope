import type * as maplibregl from "maplibre-gl"
import "maplibre-gl/dist/maplibre-gl.css"

export type LayerDataStats = {
  /** MVT property name → {min, max, p5, p95} across this layer. p5/p95 drive
   *  winsorized dot normalization; min/max kept for tooltips and reference. */
  [propertyName: string]: {
    min: number
    max: number
    p5: number
    p95: number
  }
}

export type LayerViewOption = {
  id: number
  /** Layer order from the API (0 = zip/leaf layer, 1+ = territory/region layers). */
  order: number
  showFill: boolean
  showOutline: boolean
  showLabel: boolean
  /** MVT property name (e.g. "customers_sum") to render as a second styled line below the name label. Null disables the data line. */
  dataLabelField: string | null
  /** Render a sized/colored circle at the label centroid instead of the text label. Visualizes the data field magnitude. */
  showDataDots: boolean
  /** Per-layer min/max for every numeric MVT property, from GET /layers. Drives dot normalization. */
  dataStats: LayerDataStats | null
}

export type LayerViewOptions = LayerViewOption[]

export type BaseMapName = "osm" | "satellite" | "terrain" | "dark" | "none"

/** Sources that require a raster tile entry. "none" has no source — the background is transparent. */
export const BASE_MAP_SOURCES: Partial<
  Record<BaseMapName, maplibregl.SourceSpecification>
> = {
  osm: {
    type: "raster",
    tileSize: 256,
    tiles: [
      "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
      "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
      "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
    ],
  },
  satellite: {
    type: "raster",
    tileSize: 256,
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ],
  },
  terrain: {
    type: "raster",
    tileSize: 256,
    tiles: [
      "https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
      "https://b.tile.opentopomap.org/{z}/{x}/{y}.png",
      "https://c.tile.opentopomap.org/{z}/{x}/{y}.png",
    ],
  },
  dark: {
    type: "raster",
    tileSize: 256,
    tiles: [
      "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    ],
  },
  // "none" intentionally omitted — no source needed
}
