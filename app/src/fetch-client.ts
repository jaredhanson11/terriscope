import createClient, { InitParam, MaybeOptionalInit } from "openapi-fetch"
import { PathsWithMethod } from "openapi-typescript-helpers"

import config from "./app/config"
import { paths } from "./lib/api/v1"

export const vanillaFetchClient = createClient<paths>({
  baseUrl: config.get("api_base_url"),
  credentials: "include",
})

let refreshPromise: Promise<void> | null = null

async function refreshToken(): Promise<boolean> {
  try {
    const response = await vanillaFetchClient.POST(
      "/v1.0/auth/refresh-token",
      {},
    )
    if ("error" in response) {
      // If the response has an `error` property, treat as failed
      throw new Error("Refresh token request returned an error.")
    }
    return true
  } catch (err) {
    console.error("refreshToken error:", err)
    return false
  }
}

function isUnauthorized(response: unknown): boolean {
  return (
    typeof response === "object" &&
    response !== null &&
    "response" in response &&
    typeof response.response === "object" &&
    response.response !== null &&
    "status" in response.response &&
    response.response.status === 401
  )
}

function throwIfError(response: unknown): void {
  if (
    typeof response === "object" &&
    response !== null &&
    "error" in response
  ) {
    if (
      typeof response.error === "object" &&
      response.error !== null &&
      "message" in response.error &&
      typeof response.error.message === "string"
    ) {
      throw new Error(response.error.message)
    }

    throw new Error("Request failed")
  }
}

async function handleRequestWithRefresh<T>(fn: () => Promise<T>): Promise<T> {
  let response: T
  response = await fn()

  // Check for 401
  if (isUnauthorized(response)) {
    // If there's no refresh in progress, start one
    if (!refreshPromise) {
      refreshPromise = (async () => {
        const success = await refreshToken()
        // Clear the stored promise either way
        refreshPromise = null
        if (!success) {
          // Force logout or throw if refresh fails
          throw new Error("Token refresh failed; user must re-authenticate.")
        }
      })()
    }

    // Wait on the in-flight refresh attempt
    await refreshPromise

    // After refresh is successful, retry the original request
    response = await fn()
  }

  // Throw if the response has an error payload
  throwIfError(response)
  return response
}

export const fetchClient = {
  GET<
    Path extends PathsWithMethod<paths, "get">,
    Init extends MaybeOptionalInit<paths[Path], "get">,
  >(url: Path, ...init: InitParam<Init>) {
    return handleRequestWithRefresh(() =>
      vanillaFetchClient.GET(
        url,
        ...(init as InitParam<MaybeOptionalInit<paths[Path], "get">>),
      ),
    )
  },
  POST<
    Path extends PathsWithMethod<paths, "post">,
    Init extends MaybeOptionalInit<paths[Path], "post">,
  >(url: Path, ...init: InitParam<Init>) {
    return handleRequestWithRefresh(() =>
      vanillaFetchClient.POST(
        url,
        ...(init as InitParam<MaybeOptionalInit<paths[Path], "post">>),
      ),
    )
  },
  DELETE<
    Path extends PathsWithMethod<paths, "delete">,
    Init extends MaybeOptionalInit<paths[Path], "delete">,
  >(url: Path, ...init: InitParam<Init>) {
    return handleRequestWithRefresh(() =>
      vanillaFetchClient.DELETE(
        url,
        ...(init as InitParam<MaybeOptionalInit<paths[Path], "delete">>),
      ),
    )
  },
  PUT<
    Path extends PathsWithMethod<paths, "put">,
    Init extends MaybeOptionalInit<paths[Path], "put">,
  >(url: Path, ...init: InitParam<Init>) {
    return handleRequestWithRefresh(() =>
      vanillaFetchClient.PUT(
        url,
        ...(init as InitParam<MaybeOptionalInit<paths[Path], "put">>),
      ),
    )
  },
}
