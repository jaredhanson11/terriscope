import { createContext, useContext } from "react"

import type { components } from "@/lib/api/v1"

export const MeContext = createContext<{
  user: components["schemas"]["User"] | null
  maps: components["schemas"]["Map"][] | null
}>({
  user: null,
  maps: null,
})

export const useMe = () => {
  const authContext = useContext(MeContext)
  if (authContext.user != null) {
    return authContext.user
  } else {
    throw new Error("useMe must be used within an MeProvider.")
  }
}

export const useMaps = () => {
  const authContext = useContext(MeContext)
  if (authContext.maps != null) {
    return authContext.maps
  } else {
    throw new Error("useMaps must be used within a MeProvider.")
  }
}
