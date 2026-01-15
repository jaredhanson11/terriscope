import { queryOptions } from "@tanstack/react-query"

import { fetchClient } from "@/fetch-client"

export const queries = {
  _root: () => [],
  _layers: () => ["layers"],
  _me: () => [...queries._root(), "me"],
  _maps: () => [...queries._root(), "maps"],
  me: () =>
    queryOptions({
      queryKey: [...queries._me()],
      queryFn: async () => {
        const response = await fetchClient.GET("/me")
        if (!response.data || response.response.status !== 200) {
          throw new Error("Failed to fetch user data")
        }
        return response.data
      },
    }),
  listLayers: (mapId: number) =>
    queryOptions({
      queryKey: [...queries._layers(), "list", { mapId }],
      queryFn: async () => {
        const response = await fetchClient.GET("/layers", {
          params: { query: { map_id: mapId } },
        })
        if (!response.data || response.response.status !== 200) {
          throw new Error("Failed to fetch layers")
        }
        return response.data
      },
    }),
  listMaps: () =>
    queryOptions({
      queryKey: [...queries._maps(), "list"],
      queryFn: async () => {
        const response = await fetchClient.GET("/maps")
        if (!response.data || response.response.status !== 200) {
          throw new Error("Failed to fetch maps")
        }
        return response.data
      },
    }),
}
