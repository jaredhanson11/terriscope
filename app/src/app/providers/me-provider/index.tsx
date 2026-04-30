import { useQuery } from "@tanstack/react-query"
import { type PropsWithChildren } from "react"
import { useLocation, useNavigate } from "react-router-dom"

import { AppRoutes, PageName } from "@/app/routes"
import { queries } from "@/queries/queries"

import { MeContext } from "./context"
import { AppLoadingScreen } from "./loading-screen"

export const AuthProvider = (props: PropsWithChildren) => {
  const navigate = useNavigate()
  const location = useLocation()
  const userQuery = useQuery(queries.me())
  const mapsQuery = useQuery({
    ...queries.listMaps(),
    enabled: !!userQuery.data,
  })
  const invitesQuery = useQuery({
    ...queries.listMyInvites(),
    enabled: !!userQuery.data,
  })

  if (
    (!userQuery.data && userQuery.isLoading) ||
    (!mapsQuery.data && mapsQuery.isLoading) ||
    (!invitesQuery.data && invitesQuery.isLoading)
  ) {
    return <AppLoadingScreen />
  }

  if (userQuery.isSuccess && mapsQuery.isSuccess && invitesQuery.isSuccess) {
    const isNoMapsFlow =
      !location.pathname.startsWith("/new") &&
      !location.pathname.startsWith("/invites")

    if (mapsQuery.data.length === 0 && isNoMapsFlow) {
      const hasPendingInvites = invitesQuery.data.length > 0
      void navigate(
        hasPendingInvites
          ? AppRoutes.getRoute(PageName.Invites)
          : AppRoutes.getRoute(PageName.Initialize),
      )
    }

    return (
      <MeContext.Provider
        value={{ user: userQuery.data, maps: mapsQuery.data }}
      >
        {props.children}
      </MeContext.Provider>
    )
  }
  void navigate(AppRoutes.getRoute(PageName.Login))
}
