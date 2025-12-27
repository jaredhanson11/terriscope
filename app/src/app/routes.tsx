import type { ReactNode } from "react"

import { ComponentExample } from "@/components/component-example"
import HomePage from "@/features/home/page"
import InitializePage from "@/features/initialize/page"

import { VersionsPage } from "./common/versions.page"

const PageName = {
  Versions: "VersionsPage",
  Initialize: "InitializePage",
  Example: "ExamplePage",
  Home: "HomePage",
} as const

type PageName = (typeof PageName)[keyof typeof PageName]

type Route = {
  route: string
  component: ReactNode
}

/* Here we can Define parameter types for each route in the format of
   { [PageName]: { path: { [paramName]: any }, query: { [paramName]: any} } }
*/
export type RouteParamsType = {
  [PageName.Versions]: {
    query: {
      hello?: "world"
    }
  }
}

export type ExtractPathParams<T extends PageName & keyof RouteParamsType> =
  // @ts-expect-error we need to review and fix this eventually
  RouteParamsType[T]["path"] extends Record<string, string>
    ? // @ts-expect-error we need to review and fix this eventually
      RouteParamsType[T]["path"]
    : undefined

export type ExtractQueryParams<T extends PageName & keyof RouteParamsType> =
  RouteParamsType[T]["query"] extends Record<string, string | number>
    ? RouteParamsType[T]["query"]
    : undefined

const Routes: Record<PageName, Route> = {
  [PageName.Home]: {
    route: "/",
    component: <HomePage />,
  },
  [PageName.Initialize]: {
    route: "/new",
    component: <InitializePage />,
  },
  [PageName.Example]: {
    route: "/example",
    component: <ComponentExample />,
  },
  [PageName.Versions]: {
    route: "/versions",
    component: <VersionsPage />,
  },
}

class RouteClass<T extends PageName> {
  private routesObj: Record<T, Route>

  constructor(routesObj: Record<T, Route>) {
    this.routesObj = routesObj
  }

  getRoute<K extends T>(
    route: K,
    pathParams?: ExtractPathParams<K>,
    queryParams?: ExtractQueryParams<K>,
  ): string {
    let path = this.routesObj[route].route
    if (!path) {
      throw new Error(`Route '${route}' not found.`)
    }

    if (pathParams) {
      for (const key in pathParams) {
        path = path.replace(`:${key}`, pathParams[key])
      }
    }

    if (queryParams) {
      const queryString = Object.entries(
        queryParams as {
          [key: string]: string | number | undefined
        },
      )
        .filter(([_, value]) => value !== undefined)
        .map(
          ([key, value]) =>
            `${encodeURIComponent(key)}=${encodeURIComponent(
              (value as string | number).toString(),
            )}`,
        )
        .join("&")

      if (queryString) {
        path += `?${queryString}`
      }
    }
    return path
  }

  getAllRoutes(): ({
    name: string
  } & Route)[] {
    return Object.entries(
      this.routesObj as {
        [key: string]: Route
      },
    ).map(([name, { route, component }]) => ({
      name,
      route,
      component,
    }))
  }
}

const AppRoutes = new RouteClass(Routes)

export { AppRoutes, PageName }
