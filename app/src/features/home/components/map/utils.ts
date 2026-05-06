import type * as maplibregl from "maplibre-gl"

import config from "@/app/config"

import {
  BASE_MAP_SOURCES,
  type BaseMapName,
  type LayerDataStats,
  type LayerViewOptions,
} from "./config"

const DOT_COLOR_STOPS = [
  "#3b82f6", // 0.0–0.2  blue
  "#10b981", // 0.2–0.4  green
  "#eab308", // 0.4–0.6  yellow
  "#f97316", // 0.6–0.8  orange
  "#ef4444", // 0.8–1.0  red
]

const DOT_CONSTANT_FALLBACK_COLOR = DOT_COLOR_STOPS[2]

/**
 * Norm represents (value - min) / (max - min) clamped to [0, 1] for the chosen
 * data label field on a layer. `kind: "constant"` means min == max so every
 * feature collapses to the same magnitude (used to skip division and apply
 * fixed visual encoding); `kind: "expr"` carries a MapLibre expression
 * computed per feature. Returns null when dots can't render at all.
 */
type DotNorm =
  | { kind: "constant" }
  | { kind: "expr"; expr: maplibregl.ExpressionSpecification }

function buildDotNorm(
  dataLabelField: string | null,
  dataStats: LayerDataStats | null,
): DotNorm | null {
  if (!dataLabelField || !dataStats) return null
  const stats = dataStats[dataLabelField]
  if (!stats) return null
  // Winsorized normalization: clamp values into [p5, p95] so a single outlier
  // doesn't compress the bulk into a tiny visual range. Fall back to min/max
  // when the percentile window collapses (tiny N, all-equal values, etc.).
  const lo = stats.p5 < stats.p95 ? stats.p5 : stats.min
  const hi = stats.p5 < stats.p95 ? stats.p95 : stats.max
  if (hi <= lo) return { kind: "constant" }
  const range = hi - lo
  // Clamp to [0, 1]: anything below p5 caps to 0, anything above p95 caps to 1.
  const expr: maplibregl.ExpressionSpecification = [
    "max",
    0,
    [
      "min",
      1,
      [
        "/",
        ["-", ["to-number", ["get", dataLabelField]], lo],
        range,
      ],
    ],
  ]
  return { kind: "expr", expr }
}

/**
 * Build the circle-radius / circle-color paint properties for the data-dots
 * layer, normalized against the layer's min/max for the chosen data label
 * field. Returns null if dots can't be rendered (no field selected, no stats
 * for that field). When all features have the same value (min == max) we
 * collapse to a constant medium dot rather than dividing by zero.
 */
function buildDotPaint(
  norm: DotNorm | null,
):
  | {
      radius: maplibregl.ExpressionSpecification
      color: maplibregl.ExpressionSpecification | string
    }
  | null {
  if (!norm) return null

  if (norm.kind === "constant") {
    return {
      radius: ["interpolate", ["linear"], ["zoom"], 5, 8, 12, 16],
      color: DOT_CONSTANT_FALLBACK_COLOR,
    }
  }

  return {
    radius: [
      "interpolate",
      ["linear"],
      ["zoom"],
      5,
      ["interpolate", ["linear"], norm.expr, 0, 3, 1, 14],
      12,
      ["interpolate", ["linear"], norm.expr, 0, 6, 1, 28],
    ],
    color: [
      "step",
      norm.expr,
      DOT_COLOR_STOPS[0],
      0.2,
      DOT_COLOR_STOPS[1],
      0.4,
      DOT_COLOR_STOPS[2],
      0.6,
      DOT_COLOR_STOPS[3],
      0.8,
      DOT_COLOR_STOPS[4],
    ],
  }
}

/**
 * text-offset that places the bottom of the label flush with the top edge of
 * the data dot, mirroring the dot's circle-radius expression so the gap
 * tracks dot size. Returns null if dots aren't being rendered for the layer.
 *
 * Math: dot radius (px) varies on zoom and norm; text-size (px) varies on
 * zoom. text-offset units are ems (= 1× text-size), so the y-offset in ems
 * = -(radius_px + GAP) / text_size_px. We pre-divide at the four corners of
 * (zoom × norm) and let MapLibre's nested interpolate fill in between.
 */
const LABEL_DOT_GAP_PX = 2
function buildLabelDotOffsetExpr(
  order: number,
  norm: DotNorm,
): maplibregl.ExpressionSpecification {
  const labelSizeMin = Math.min(10 + order * 2, 16)
  const labelSizeMax = Math.min(13 + order * 4, 24)
  const gap = LABEL_DOT_GAP_PX

  if (norm.kind === "constant") {
    // Constant medium dot from buildDotPaint: radius 8px @ z5, 16px @ z12.
    return [
      "interpolate",
      ["linear"],
      ["zoom"],
      5,
      ["literal", [0, -(8 + gap) / labelSizeMin]],
      12,
      ["literal", [0, -(16 + gap) / labelSizeMax]],
    ]
  }

  // Mirrors buildDotPaint's circle-radius:
  // z=5  → radius 3px @ norm0 → 14px @ norm1
  // z=12 → radius 6px @ norm0 → 28px @ norm1
  return [
    "interpolate",
    ["linear"],
    ["zoom"],
    5,
    [
      "interpolate",
      ["linear"],
      norm.expr,
      0,
      ["literal", [0, -(3 + gap) / labelSizeMin]],
      1,
      ["literal", [0, -(14 + gap) / labelSizeMin]],
    ],
    12,
    [
      "interpolate",
      ["linear"],
      norm.expr,
      0,
      ["literal", [0, -(6 + gap) / labelSizeMax]],
      1,
      ["literal", [0, -(28 + gap) / labelSizeMax]],
    ],
  ]
}

// Two-line format expression: name (dark) + optional data value (blue, smaller)
function buildLabelExpression(
  isZipLayer = false,
  dataLabelField: string | null = null,
): maplibregl.ExpressionSpecification {
  const nameExpr: maplibregl.ExpressionSpecification = isZipLayer
    ? ["get", "zip_code"]
    : ["get", "name"]

  if (!dataLabelField) return nameExpr

  return [
    "format",
    nameExpr,
    {},
    "\n",
    {},
    ["coalesce", ["to-string", ["get", dataLabelField]], "—"],
    { "text-color": "#2563eb", "font-scale": 0.82 },
  ] as unknown as maplibregl.ExpressionSpecification
}

// Returns the MapLibre layer ID of the lowest data layer currently in the map.
// Used to anchor basemap layers beneath all data layers when inserting them.
function findFirstDataLayerId(
  map: maplibregl.Map,
  layers: LayerViewOptions,
): string | undefined {
  for (const layer of layers) {
    const id = layer.id.toString()
    if (map.getLayer(`layer-${id}-fill`)) return `layer-${id}-fill`
    if (map.getLayer(`layer-${id}-selection`)) return `layer-${id}-selection`
  }
  return undefined
}

export function updateSources(
  map: maplibregl.Map,
  layers: LayerViewOptions,
  tileVersion = 0,
) {
  // Basemap sources
  Object.entries(BASE_MAP_SOURCES).forEach(([name, source]) => {
    const sourceId = `base-map-${name}`
    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, source)
    }
  })

  // Data layer sources
  layers.forEach((layerOption) => {
    const { id, order } = layerOption
    const rev = `?rev=${tileVersion.toString()}`
    const sourceId = `layer-${id.toString()}`
    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: "vector",
        tiles: [
          `${config.get("api_base_url")}/tiles/${id.toString()}/{z}/{x}/{y}.pbf${rev}`,
        ],
        minzoom: 0,
        maxzoom: 14,
        // For zip layers, use zip_code as the feature ID so setFeatureState works with string keys
        ...(order === 0 ? { promoteId: { zips: "zip_code" } } : {}),
      })
    }
  })
}

export function updateLayers(
  map: maplibregl.Map,
  baseMap: BaseMapName,
  layers: LayerViewOptions,
) {
  // The lowest data layer currently in the map — basemap layers are inserted
  // before this so they always render beneath the data.
  const firstDataLayerId = findFirstDataLayerId(map, layers)

  // Basemap raster layers: add once (below all data layers), then toggle
  // visibility. Never remove — setLayoutProperty is the only mutation needed.
  Object.keys(BASE_MAP_SOURCES).forEach((name) => {
    const layerId = `base-map-${name}-layer`
    const sourceId = `base-map-${name}`

    if (!map.getLayer(layerId)) {
      // Insert before the lowest data layer so basemap stays at the bottom.
      map.addLayer(
        { id: layerId, type: "raster", source: sourceId },
        firstDataLayerId,
      )
    } else if (firstDataLayerId) {
      // Re-anchor below data layers on every update. Without this, a basemap
      // layer that was added before data layers existed stays below them, but
      // if it ends up above (e.g. first time satellite/terrain tiles fully
      // render), it would cover fills and borders until something re-ordered.
      map.moveLayer(layerId, firstDataLayerId)
    }
    map.setLayoutProperty(
      layerId,
      "visibility",
      baseMap === name ? "visible" : "none",
    )
  })

  // Data layers are painted in four separate passes so that the groups stack
  // correctly regardless of how many layers exist or which toggles are on:
  //
  //   fills (all layers)       ← bottom
  //   selections (all layers)
  //   outlines (all layers)
  //   labels (all layers)      ← top
  //
  // Each pass appends to the top of the current stack (before=undefined), so
  // running the passes in order naturally builds the right grouping. Layers are
  // added exactly once; subsequent calls only call setLayoutProperty.

  // Pass 1 — fills
  layers.forEach(({ id, order, showFill }) => {
    const fillLayerId = `layer-${id.toString()}-fill`
    const sourceId = `layer-${id.toString()}`
    const sourceLayer = order === 0 ? "zips" : "nodes"

    if (!map.getLayer(fillLayerId)) {
      map.addLayer({
        id: fillLayerId,
        type: "fill",
        source: sourceId,
        "source-layer": sourceLayer,
        paint: {
          "fill-color": ["coalesce", ["get", "color"], "#888888"],
          "fill-opacity": 0.7,
        },
      })
    }
    map.setLayoutProperty(
      fillLayerId,
      "visibility",
      showFill ? "visible" : "none",
    )
  })

  // Pass 2 — selection highlights (always visible; opacity expression handles show/hide)
  layers.forEach(({ id, order }) => {
    const selectionLayerId = `layer-${id.toString()}-selection`
    const sourceId = `layer-${id.toString()}`
    const sourceLayer = order === 0 ? "zips" : "nodes"

    if (!map.getLayer(selectionLayerId)) {
      map.addLayer({
        id: selectionLayerId,
        type: "fill",
        source: sourceId,
        "source-layer": sourceLayer,
        paint: {
          "fill-color": "#2563eb",
          "fill-opacity": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            0.5,
            0,
          ],
        },
      })
    }
  })

  // Pass 3 — outlines
  layers.forEach(({ id, order, showOutline }) => {
    const outlineLayerId = `layer-${id.toString()}-outline`
    const sourceId = `layer-${id.toString()}`
    const sourceLayer = order === 0 ? "zips" : "nodes"

    if (!map.getLayer(outlineLayerId)) {
      map.addLayer({
        id: outlineLayerId,
        type: "line",
        source: sourceId,
        "source-layer": sourceLayer,
        paint: {
          "line-color": "#000000",
          "line-width": order === 0 ? 1 : 2,
        },
      })
    }
    map.setLayoutProperty(
      outlineLayerId,
      "visibility",
      showOutline ? "visible" : "none",
    )
  })

  // Pass 4 — labels. When dots are on, render only the node/zip name and pin
  // it just above the dot so its bottom edge sits flush with the dot's top
  // (offset tracks the dot's radius, which scales with norm and zoom).
  // Otherwise render the standard name + optional data line, centered.
  layers.forEach(({ id, order, showLabel, dataLabelField, showDataDots, dataStats }) => {
    const labelLayerId = `layer-${id.toString()}-label`
    const sourceId = `layer-${id.toString()}`
    const norm = buildDotNorm(dataLabelField, dataStats)
    const dotsActive = showDataDots && norm !== null
    const textFieldExpr = buildLabelExpression(
      order === 0,
      dotsActive ? null : dataLabelField,
    )
    const labelSizeMin = Math.min(10 + order * 2, 16)
    const labelSizeMax = Math.min(13 + order * 4, 24)
    const labelFont =
      order >= 2
        ? ["Open Sans Bold", "Arial Unicode MS Regular"]
        : ["Open Sans Regular", "Arial Unicode MS Regular"]
    const labelHaloWidth = order === 0 ? 1.5 : order === 1 ? 2 : 2.5
    const textAnchor = dotsActive ? "bottom" : "center"
    const textOffset: maplibregl.ExpressionSpecification | [number, number] =
      dotsActive ? buildLabelDotOffsetExpr(order, norm) : [0, 0]

    if (!map.getLayer(labelLayerId)) {
      map.addLayer({
        id: labelLayerId,
        type: "symbol",
        source: sourceId,
        "source-layer": order === 0 ? "zip_labels" : "node_labels",
        layout: {
          "text-field": textFieldExpr,
          "text-size": [
            "interpolate",
            ["linear"],
            ["zoom"],
            5,
            labelSizeMin,
            12,
            labelSizeMax,
          ],
          "text-font": labelFont,
          "text-max-width": 20,
          "text-line-height": 1.5,
          "text-justify": "center",
          "text-anchor": textAnchor,
          "text-offset": textOffset,
        },
        paint: {
          "text-color": "#111111",
          "text-halo-color": "rgba(255, 255, 255, 0.85)",
          "text-halo-width": labelHaloWidth,
          "text-halo-blur": 1,
        },
      })
    } else {
      map.setLayoutProperty(labelLayerId, "text-field", textFieldExpr)
      map.setLayoutProperty(labelLayerId, "text-anchor", textAnchor)
      map.setLayoutProperty(labelLayerId, "text-offset", textOffset)
    }
    map.setLayoutProperty(
      labelLayerId,
      "visibility",
      showLabel ? "visible" : "none",
    )
  })

  // Pass 5 — data dots: circle rendered at the label centroid whose size and
  // color encode the magnitude of the layer's chosen data label field,
  // normalized against the layer-wide min/max returned by GET /layers. Hides
  // when no field is selected, no stats exist for the field, or the user
  // hasn't toggled dots on. Paint is rebuilt on every call so changes to
  // the active field/stats are reflected.
  layers.forEach(({ id, order, showLabel, showDataDots, dataLabelField, dataStats }) => {
    const dotsLayerId = `layer-${id.toString()}-dots`
    const sourceId = `layer-${id.toString()}`

    if (!map.getLayer(dotsLayerId)) {
      map.addLayer({
        id: dotsLayerId,
        type: "circle",
        source: sourceId,
        "source-layer": order === 0 ? "zip_labels" : "node_labels",
        paint: {
          "circle-radius": 0,
          "circle-color": DOT_CONSTANT_FALLBACK_COLOR,
          "circle-opacity": 0.85,
          "circle-stroke-color": "rgba(255, 255, 255, 0.95)",
          "circle-stroke-width": 1.5,
        },
      })
    }

    const paint = buildDotPaint(buildDotNorm(dataLabelField, dataStats))
    if (paint) {
      map.setPaintProperty(dotsLayerId, "circle-radius", paint.radius)
      map.setPaintProperty(dotsLayerId, "circle-color", paint.color)
    }
    const visible = showLabel && showDataDots && paint !== null
    map.setLayoutProperty(dotsLayerId, "visibility", visible ? "visible" : "none")
  })
}

/**
 * Forces MapLibre to re-fetch all tile data for every data layer source by
 * updating the tile URLs with a cache-busting revision parameter.  Call this
 * after a recompute job completes so the new geometries are shown immediately.
 */
export function refreshTileSources(
  map: maplibregl.Map,
  layers: LayerViewOptions,
  tileVersion: number,
): void {
  layers.forEach(({ id }) => {
    const tileUrl = `${config.get("api_base_url")}/tiles/${id.toString()}/{z}/{x}/{y}.pbf?rev=${tileVersion.toString()}`
    const source = map.getSource(`layer-${id.toString()}`)
    if (source?.type === "vector")
      (source as maplibregl.VectorTileSource).setTiles([tileUrl])
  })
}

export function updateSelectedNodeStates(
  map: maplibregl.Map,
  layerId: number,
  previousSelection: number[],
  newSelection: number[],
) {
  const sourceId = `layer-${layerId.toString()}`
  const prevSet = new Set(previousSelection)
  const newSet = new Set(newSelection)

  previousSelection.forEach((nodeId) => {
    if (!newSet.has(nodeId)) {
      map.setFeatureState(
        { source: sourceId, sourceLayer: "nodes", id: nodeId },
        { selected: false },
      )
    }
  })

  newSelection.forEach((nodeId) => {
    if (!prevSet.has(nodeId)) {
      map.setFeatureState(
        { source: sourceId, sourceLayer: "nodes", id: nodeId },
        { selected: true },
      )
    }
  })
}

export function updateSelectedZipStates(
  map: maplibregl.Map,
  layerId: number,
  previousSelection: string[],
  newSelection: string[],
) {
  const sourceId = `layer-${layerId.toString()}`
  const prevSet = new Set(previousSelection)
  const newSet = new Set(newSelection)

  previousSelection.forEach((zipCode) => {
    if (!newSet.has(zipCode)) {
      map.setFeatureState(
        { source: sourceId, sourceLayer: "zips", id: zipCode },
        { selected: false },
      )
    }
  })

  newSelection.forEach((zipCode) => {
    if (!prevSet.has(zipCode)) {
      map.setFeatureState(
        { source: sourceId, sourceLayer: "zips", id: zipCode },
        { selected: true },
      )
    }
  })
}
