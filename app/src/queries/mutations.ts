import { useMutation } from "@tanstack/react-query"
import type { FetchResponse } from "openapi-fetch"

import { fetchClient } from "@/fetch-client"
import type { paths } from "@/lib/api/v1"

export const useImportMapMutation = (options?: {
  onSuccess?: (
    response: FetchResponse<paths["/maps"]["post"], "json", "application/json">,
  ) => void
}) => {
  return useMutation({
    mutationFn: async (variables: {
      import_data: paths["/maps"]["post"]["requestBody"]["content"]["application/json"]
    }) => {
      return await fetchClient.POST("/maps", {
        body: variables.import_data,
      })
    },
    onSuccess: options?.onSuccess,
  })
}
