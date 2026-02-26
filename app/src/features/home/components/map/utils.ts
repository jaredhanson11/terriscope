import type * as maplibregl from "maplibre-gl"

import config from "@/app/config"

import {
  BASE_MAP_SOURCES,
  type BaseMapName,
  type LayerViewOptions,
} from "./config"

export function updateSources(map: maplibregl.Map, layers: LayerViewOptions) {
  // Basemap source
  Object.entries(BASE_MAP_SOURCES).forEach(([name, source]) => {
    const sourceId = `base-map-${name}`
    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, source)
    }
  })

  // Basemap layers
  layers.forEach((layerOption) => {
    const { id } = layerOption
    const sourceId = `layer-${id.toString()}`
    const labelSourceId = `layer-${id.toString()}-labels`
    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: "vector",
        tiles: [
          `${config.get("api_base_url")}/tiles/${id.toString()}/{z}/{x}/{y}.pbf`,
        ],
        minzoom: 0,
        maxzoom: 14,
      })
    }
    if (!map.getSource(labelSourceId)) {
      map.addSource(labelSourceId, {
        type: "vector",
        tiles: [
          `${config.get("api_base_url")}/tiles/${id.toString()}/{z}/{x}/{y}/labels.pbf`,
        ],
        minzoom: 0,
        maxzoom: 14,
      })
    }
  })
}

export function updateLayers(
  map: maplibregl.Map,
  baseMap: BaseMapName,
  layers: LayerViewOptions,
) {
  Object.keys(BASE_MAP_SOURCES).forEach((name) => {
    const layerId = `base-map-${name}-layer`
    const sourceId = `base-map-${name}`
    const isActive = baseMap == name
    const isInLayers = map.getLayer(layerId)
    if (isActive && !isInLayers) {
      map.addLayer(
        {
          id: layerId,
          type: "raster",
          source: sourceId,
        },
        undefined,
      )
    } else if (!isActive && isInLayers) {
      map.removeLayer(layerId)
    }
  })

  layers.forEach((layerOption) => {
    const { id, showFill, showOutline, showLabel } = layerOption
    const fillLayerId = `layer-${id.toString()}-fill`
    const selectionLayerId = `layer-${id.toString()}-selection`
    const outlineLayerId = `layer-${id.toString()}-outline`
    const labelLayerId = `layer-${id.toString()}-label`
    const sourceId = `layer-${id.toString()}`
    const labelSourceId = `layer-${id.toString()}-labels`

    // Fill layer — inserted below the selection layer so selection always renders on top
    const fillLayerExists = map.getLayer(fillLayerId)
    if (showFill && !fillLayerExists) {
      map.addLayer(
        {
          id: fillLayerId,
          type: "fill",
          source: sourceId,
          "source-layer": "nodes",
          paint: {
            "fill-color": "#888888",
            "fill-opacity": 0.4,
          },
        },
        map.getLayer(selectionLayerId) ? selectionLayerId : undefined,
      )
    } else if (!showFill && fillLayerExists) {
      map.removeLayer(fillLayerId)
    }

    // Selection highlight — always present, transparent until features are selected.
    // This ensures lasso feedback is visible regardless of which layer has fill enabled.
    if (!map.getLayer(selectionLayerId)) {
      map.addLayer(
        {
          id: selectionLayerId,
          type: "fill",
          source: sourceId,
          "source-layer": "nodes",
          paint: {
            "fill-color": "#2563eb",
            "fill-opacity": [
              "case",
              ["boolean", ["feature-state", "selected"], false],
              0.5,
              0,
            ],
          },
        },
        map.getLayer(outlineLayerId) ? outlineLayerId : undefined,
      )
    }

    // Outline layer — inserted below the label layer
    const outlineLayerExists = map.getLayer(outlineLayerId)
    if (showOutline && !outlineLayerExists) {
      map.addLayer(
        {
          id: outlineLayerId,
          type: "line",
          source: sourceId,
          "source-layer": "nodes",
          paint: {
            "line-color": "#000000",
            "line-width": 2,
          },
        },
        map.getLayer(labelLayerId) ? labelLayerId : undefined,
      )
    } else if (!showOutline && outlineLayerExists) {
      map.removeLayer(outlineLayerId)
    }

    // Label layer — always on top
    const labelLayerExists = map.getLayer(labelLayerId)
    if (showLabel && !labelLayerExists) {
      map.addLayer(
        {
          id: labelLayerId,
          type: "symbol",
          source: labelSourceId,
          "source-layer": "nodes",
          layout: {
            "text-field": ["get", "name"],
            "text-size": ["interpolate", ["linear"], ["zoom"], 4, 10, 10, 13],
            "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
            "text-max-width": 8,
          },
          paint: {
            "text-color": "#1a1a1a",
            "text-halo-color": "rgba(255,255,255,0.85)",
            "text-halo-width": 1.5,
          },
        },
        undefined,
      )
    } else if (!showLabel && labelLayerExists) {
      map.removeLayer(labelLayerId)
    }
  })
}

export function updateSelectedFeatureStates(
  map: maplibregl.Map,
  layerId: number,
  previousSelection: number[],
  newSelection: number[],
) {
  const sourceId = `layer-${layerId.toString()}`
  const prevSet = new Set(previousSelection)
  const newSet = new Set(newSelection)

  // Clear features no longer selected
  previousSelection.forEach((nodeId) => {
    if (!newSet.has(nodeId)) {
      map.setFeatureState(
        { source: sourceId, sourceLayer: "nodes", id: nodeId },
        { selected: false },
      )
    }
  })

  // Add newly selected features
  newSelection.forEach((nodeId) => {
    if (!prevSet.has(nodeId)) {
      map.setFeatureState(
        { source: sourceId, sourceLayer: "nodes", id: nodeId },
        { selected: true },
      )
    }
  })
}
