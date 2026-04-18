import { queryOptions } from "@tanstack/react-query"

import { fetchClient } from "@/fetch-client"

const ACTIVE_JOB_STATUSES = new Set(["pending", "processing", "failed"])

function isJobActive(data: { active_job?: { status: string } | null } | undefined): boolean {
  return !!data?.active_job && ACTIVE_JOB_STATUSES.has(data.active_job.status)
}

export const queries = {
  _root: () => [],
  _layers: () => ["layers"],
  _nodes: () => ["nodes"],
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
  listNodes: (layerId: number, page = 1, pageSize = 100) =>
    queryOptions({
      queryKey: [...queries._nodes(), "list", { layerId, page, pageSize }],
      queryFn: async () => {
        const response = await fetchClient.GET("/nodes", {
          params: { query: { layer_id: layerId, page, page_size: pageSize } },
        })
        if (!response.data || response.response.status !== 200) {
          throw new Error("Failed to fetch nodes")
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
  getMap: (mapId: number) =>
    queryOptions({
      queryKey: [...queries._maps(), "detail", mapId],
      queryFn: async () => {
        const response = await fetchClient.GET("/maps/{map_id}", {
          params: { path: { map_id: mapId } },
        })
        if (!response.data || response.response.status !== 200) {
          throw new Error("Failed to fetch map")
        }
        return response.data
      },
      // Poll every 2s while a job is active; stop when idle or complete
      refetchInterval: (query) => (isJobActive(query.state.data) ? 2000 : false),
    }),
  searchMap: (mapId: number, q: string) =>
    queryOptions({
      queryKey: [...queries._root(), "search", { mapId, q }],
      queryFn: async () => {
        const response = await fetchClient.GET("/search", {
          params: { query: { map_id: mapId, q } },
        })
        if (!response.data || response.response.status !== 200) {
          throw new Error("Failed to search map")
        }
        return response.data
      },
      enabled: q.trim().length > 0,
    }),
  getNode: (nodeId: number) =>
    queryOptions({
      queryKey: [...queries._nodes(), "detail", nodeId],
      queryFn: async () => {
        const response = await fetchClient.GET("/nodes/{node_id}", {
          params: { path: { node_id: nodeId } },
        })
        if (!response.data || response.response.status !== 200) {
          throw new Error("Failed to fetch node")
        }
        return response.data
      },
    }),
}
