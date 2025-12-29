import type * as maplibregl from "maplibre-gl"

import config from "@/app/config"

import {
  BASE_MAP_SOURCES,
  type BaseMapName,
  type LayerViewOptions,
} from "./config"

export function updateSources(map: maplibregl.Map, layers: LayerViewOptions) {
  Object.entries(BASE_MAP_SOURCES).forEach(([name, source]) => {
    const sourceId = `base-map-${name}`
    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, source)
    }
  })

  layers.forEach((layerOption) => {
    const { id } = layerOption
    const sourceId = `layer-${id.toString()}`
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
    const outlineLayerId = `layer-${id.toString()}-outline`
    const labelLayerId = `layer-${id.toString()}-label`
    const sourceId = `layer-${id.toString()}`

    // Fill layer - create once, then toggle visibility
    if (!map.getLayer(fillLayerId)) {
      map.addLayer({
        id: fillLayerId,
        type: "fill",
        source: sourceId,
        "source-layer": "nodes",
        paint: {
          "fill-color": "#888888",
          "fill-opacity": 0.5,
        },
        layout: {
          visibility: showFill ? "visible" : "none",
        },
      })
    } else {
      map.setLayoutProperty(fillLayerId, "visibility", showFill ? "visible" : "none")
    }

    // Outline layer - create once, then toggle visibility
    if (!map.getLayer(outlineLayerId)) {
      map.addLayer({
        id: outlineLayerId,
        type: "line",
        source: sourceId,
        "source-layer": "nodes",
        paint: {
          "line-color": "#000000",
          "line-width": 2,
        },
        layout: {
          visibility: showOutline ? "visible" : "none",
        },
      })
    } else {
      map.setLayoutProperty(outlineLayerId, "visibility", showOutline ? "visible" : "none")
    }

    // Label layer - create once, then toggle visibility
    if (!map.getLayer(labelLayerId)) {
      map.addLayer({
        id: labelLayerId,
        type: "symbol",
        source: sourceId,
        "source-layer": "nodes",
        layout: {
          "text-field": ["get", "name"],
          "text-size": 12,
          visibility: showLabel ? "visible" : "none",
        },
        paint: {
          "text-color": "#202020",
        },
      })
    } else {
      map.setLayoutProperty(labelLayerId, "visibility", showLabel ? "visible" : "none")
    }
  })
}
