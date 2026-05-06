import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, type PropsWithChildren } from "react"

import { Spinner } from "@/components/ui/spinner"
import { queries } from "@/queries/queries"

import { ActiveMapContext } from "./context"

export { useActiveMap, useLayers } from "./context"

export const ActiveMapProvider = ({
  mapId,
  children,
}: { mapId: string } & PropsWithChildren) => {
  const mapQuery = useQuery(queries.getMap(mapId))
  const layersQuery = useQuery(queries.listLayers(mapId))
  const queryClient = useQueryClient()

  // Layer data_stats are recomputed against the current node/zip data on every
  // /layers request. When tile_version increments (signal that a recompute
  // job committed new data) refetch layers so dot scaling reflects the new
  // min/max immediately.
  const tileVersion = mapQuery.data?.tile_version
  useEffect(() => {
    if (tileVersion === undefined) return
    void queryClient.invalidateQueries({ queryKey: queries._layers() })
  }, [tileVersion, queryClient])

  if (mapQuery.isLoading || layersQuery.isLoading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background">
        <Spinner className="size-5 text-muted-foreground" />
      </div>
    )
  }

  if (!mapQuery.data || !layersQuery.data) return null

  return (
    <ActiveMapContext.Provider
      value={{ map: mapQuery.data, layers: layersQuery.data }}
    >
      {children}
    </ActiveMapContext.Provider>
  )
}
