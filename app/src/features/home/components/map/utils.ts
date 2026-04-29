import type * as maplibregl from "maplibre-gl"

import config from "@/app/config"

import {
  BASE_MAP_SOURCES,
  type BaseMapName,
  type LayerViewOptions,
} from "./config"

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

  // Pass 4 — labels (update text-field in place when dataLabelField changes)
  layers.forEach(({ id, order, showLabel, dataLabelField }) => {
    const labelLayerId = `layer-${id.toString()}-label`
    const sourceId = `layer-${id.toString()}`
    const textFieldExpr = buildLabelExpression(order === 0, dataLabelField)
    const labelSizeMin = Math.min(10 + order * 2, 16)
    const labelSizeMax = Math.min(13 + order * 4, 24)
    const labelFont =
      order >= 2
        ? ["Open Sans Bold", "Arial Unicode MS Regular"]
        : ["Open Sans Regular", "Arial Unicode MS Regular"]
    const labelHaloWidth = order === 0 ? 1.5 : order === 1 ? 2 : 2.5

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
    }
    map.setLayoutProperty(
      labelLayerId,
      "visibility",
      showLabel ? "visible" : "none",
    )
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
