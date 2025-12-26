import "maplibre-gl/dist/maplibre-gl.css"
import { useState } from "react"
import MapGL from "react-map-gl/maplibre"

export interface BaseMapConfig {
  type: "osm" | "satellite" | "terrain" | "dark" | "none"
}

export interface LayerConfig {
  id: string
  name: string
  visible: boolean
  mvtUrl?: string
  fillColor?: string
  outlineColor?: string
  showLabels?: boolean
}

export interface MapProps {
  baseMap: BaseMapConfig
  layers: LayerConfig[]
  center?: [number, number]
  zoom?: number
  className?: string
}

// MapLibre style definitions for different base maps
const getMapStyle = (
  type: BaseMapConfig["type"],
): maplibregl.StyleSpecification => {
  const baseStyle: maplibregl.StyleSpecification = {
    version: 8,
    sources: {},
    layers: [],
  }

  if (type === "none") {
    return baseStyle
  }

  // Add raster tile source and layer for the base map
  const sourceId = `${type}-tiles`
  baseStyle.sources[sourceId] = {
    type: "raster",
    tiles:
      type === "osm"
        ? [
            "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
          ]
        : type === "satellite"
          ? [
              "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            ]
          : type === "terrain"
            ? [
                "https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
                "https://b.tile.opentopomap.org/{z}/{x}/{y}.png",
                "https://c.tile.opentopomap.org/{z}/{x}/{y}.png",
              ]
            : type === "dark"
              ? [
                  "https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png",
                ]
              : [],
    tileSize: 256,
    attribution:
      type === "osm"
        ? "© OpenStreetMap contributors"
        : type === "terrain"
          ? "© OpenTopoMap"
          : "",
  }

  baseStyle.layers.push({
    id: `${type}-layer`,
    type: "raster",
    source: sourceId,
    minzoom: 0,
    maxzoom: 22,
  })

  return baseStyle
}

export function Map({
  baseMap,
  layers,
  center = [-98.5795, 39.8283], // Center of USA
  zoom = 4,
  className = "",
}: MapProps) {
  const [viewState, setViewState] = useState({
    longitude: center[0],
    latitude: center[1],
    zoom: zoom,
  })

  const mapStyle = getMapStyle(baseMap.type)

  return (
    <div className={`relative h-full w-full ${className}`}>
      <MapGL
        {...viewState}
        onMove={(evt) => {
          setViewState(evt.viewState)
        }}
        mapStyle={mapStyle}
        style={{ width: "100%", height: "100%" }}
        attributionControl={true}
      />
    </div>
  )
}
