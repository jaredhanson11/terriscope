import { queryOptions } from "@tanstack/react-query"

import { fetchClient } from "@/fetch-client"

export const queries = {
  _root: () => [],
  _layers: () => ["layers"],
  listLayers: () =>
    queryOptions({
      queryKey: [...queries._layers(), "list"],
      queryFn: async () => {
        const response = await fetchClient.GET("/layers")
        if (!response.data || response.response.status !== 200) {
          throw new Error("Failed to fetch layers")
        }
        return response.data
      },
    }),
}
