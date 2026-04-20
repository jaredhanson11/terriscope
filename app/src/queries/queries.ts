import { queryOptions } from "@tanstack/react-query"

import { fetchClient } from "@/fetch-client"
import type { components } from "@/lib/api/v1"

type NodeQuery = components["schemas"]["NodeQuery"]
type ZipQuery = components["schemas"]["ZipQuery"]

const ACTIVE_JOB_STATUSES = new Set(["pending", "processing", "failed"])

function isJobActive(
  data: { active_job?: { status: string } | null } | undefined,
): boolean {
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
  listLayers: (mapId: string) =>
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
  queryNodes: (body: NodeQuery, page = 1, pageSize = 50) =>
    queryOptions({
      queryKey: [...queries._nodes(), "query", { body, page, pageSize }],
      queryFn: async () => {
        const response = await fetchClient.POST("/nodes/query", {
          body,
          params: { query: { page, page_size: pageSize } },
        })
        if (!response.data || response.response.status !== 200) {
          throw new Error("Failed to query nodes")
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
  getMap: (mapId: string) =>
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
      refetchInterval: (query) =>
        isJobActive(query.state.data) ? 2000 : false,
    }),
  searchMap: (mapId: string, q: string) =>
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
  queryZipAssignments: (body: ZipQuery, page = 1, pageSize = 50) =>
    queryOptions({
      queryKey: [...queries._nodes(), "zip-query", { body, page, pageSize }],
      queryFn: async () => {
        const response = await fetchClient.POST("/zip-assignments/query", {
          body,
          params: { query: { page, page_size: pageSize } },
        })
        if (!response.data || response.response.status !== 200) {
          throw new Error("Failed to query zip assignments")
        }
        return response.data
      },
    }),
  getZipAssignment: (layerId: number, zipCode: string) =>
    queryOptions({
      queryKey: [...queries._root(), "zip-assignment", { layerId, zipCode }],
      queryFn: async () => {
        const response = await fetchClient.GET(
          "/zip-assignments/{layer_id}/{zip_code}/geography",
          { params: { path: { layer_id: layerId, zip_code: zipCode } } },
        )
        if (!response.data || response.response.status !== 200) {
          throw new Error("Failed to fetch zip assignment")
        }
        return response.data
      },
    }),
}
