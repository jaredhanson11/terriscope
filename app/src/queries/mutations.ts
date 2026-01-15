import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { FetchResponse } from "openapi-fetch"
import { useNavigate } from "react-router-dom"

import { AppRoutes, PageName } from "@/app/routes"
import { fetchClient } from "@/fetch-client"
import type { paths } from "@/lib/api/v1"

import { queries } from "./queries"

export const useImportMapMutation = () => {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: async (variables: {
      import_data: paths["/maps"]["post"]["requestBody"]["content"]["application/json"]
    }) => {
      return await fetchClient.POST("/maps", {
        body: variables.import_data,
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queries._maps() })
      void navigate(AppRoutes.getRoute(PageName.Home))
    },
  })
}

export const useLoginMutation = (options?: {
  onSuccess?: (
    response: FetchResponse<
      paths["/auth/login"]["post"],
      "json",
      "application/json"
    >["data"],
  ) => void
  onError?: (error: Error) => void
}) => {
  return useMutation({
    mutationFn: async (variables: {
      email: string
      password: string
      remember_me?: boolean
    }) => {
      const response = await fetchClient.POST("/auth/login", {
        body: {
          email: variables.email,
          password: variables.password,
          remember_me: variables.remember_me ?? false,
        },
      })
      if (response.response.status !== 200 || response.data == null) {
        throw new Error("Invalid email or password")
      }
      return response.data
    },
    onSuccess: options?.onSuccess,
    onError: options?.onError,
  })
}

export const useRegisterMutation = (options?: {
  onSuccess?: (
    response: FetchResponse<
      paths["/auth/register"]["post"],
      "json",
      "application/json"
    >["data"],
  ) => void
  onError?: (error: Error) => void
}) => {
  return useMutation({
    mutationFn: async (variables: { email: string; password: string }) => {
      const response = await fetchClient.POST("/auth/register", {
        body: {
          email: variables.email,
          password: variables.password,
        },
      })
      if (response.response.status !== 201 || response.data == null) {
        throw new Error("Registration failed")
      }
      return response.data
    },
    onSuccess: options?.onSuccess,
    onError: options?.onError,
  })
}

export const useLogoutMutation = () => {
  const queryClient = useQueryClient()
  return useMutation({
    retry: 3,
    mutationFn: async () => {
      const response = await fetchClient.POST("/auth/logout")
      if (response.response.status !== 200) {
        throw new Error("Logout failed")
      }
    },
    onSuccess: () => {
      void queryClient.resetQueries()
    },
  })
}
