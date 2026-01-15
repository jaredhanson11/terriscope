import { Outlet, Route, Routes } from "react-router-dom"

import { AppProviders } from "./providers"
import { AuthProvider } from "./providers/me-provider"
import { AppRoutes } from "./routes"

function App() {
  return (
    <AppProviders>
      <Routes>
        {AppRoutes.getUnproctedRoutes().map((route) => (
          <Route
            key={route.name}
            path={route.route}
            element={route.component}
          />
        ))}
        <Route
          path="/"
          element={
            <AuthProvider>
              <Outlet />
            </AuthProvider>
          }
        >
          {AppRoutes.getProtectedRoutes().map((route) => (
            <Route
              key={route.name}
              path={route.route}
              element={route.component}
            />
          ))}
        </Route>
      </Routes>
    </AppProviders>
  )
}

export default App
