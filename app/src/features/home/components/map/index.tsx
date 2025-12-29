import "maplibre-gl/dist/maplibre-gl.css"
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react"
import MapGL, { type MapRef } from "react-map-gl/maplibre"

import type { LayerViewOptions } from "./config"
import type { BaseMapName } from "./config"
import { updateLayers, updateSources } from "./utils"

const EMPTY_STYLE = {
  version: 8 as const,
  sources: {},
  layers: [],
}

const INITIAL_VIEW_STATE = {
  longitude: -98.5795,
  latitude: 39.8283,
  zoom: 4,
}

export const Map = forwardRef<
  MapRef | null,
  {
    baseMap: BaseMapName
    layers: LayerViewOptions
  }
>(({ baseMap, layers }, forwardRef) => {
  const ref = useRef<MapRef | null>(null)
  useImperativeHandle(forwardRef, () => ref.current as MapRef, [])

  useEffect(() => {
    const map = ref.current?.getMap()
    if (map && map.isStyleLoaded()) {
      updateSources(map, layers)
      updateLayers(map, baseMap, layers)
      console.log(map.getStyle())
      console.log(layers)
    }
  }, [baseMap, layers])

  return (
    <div className={`relative h-full w-full`}>
      <MapGL
        initialViewState={INITIAL_VIEW_STATE}
        mapStyle={EMPTY_STYLE}
        ref={ref}
        onLoad={(evt) => {
          const map = evt.target
          updateSources(map, layers)
          updateLayers(map, baseMap, layers)
        }}
        style={{ width: "100%", height: "100%" }}
        attributionControl={false}
      />
    </div>
  )
})
