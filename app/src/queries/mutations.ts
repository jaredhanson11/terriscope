import { useMutation, useQueryClient } from "@tanstack/react-query"

import { fetchClient } from "@/fetch-client"
import type { paths } from "@/lib/api/v1"

export const useImportMap = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (variables: {
      import_data: paths["/maps"]["post"]["requestBody"]["content"]["application/json"]
    }) => {
      return await fetchClient.POST("/maps", {
        requestBody: variables.import_data,
      })
    },
    onSuccess: async () => {},
  })
}
