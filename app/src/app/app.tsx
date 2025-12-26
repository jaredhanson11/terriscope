import { Route, Routes } from "react-router-dom"

import { AppProviders } from "./providers"
import { AppRoutes } from "./routes"

function App() {
  return (
    <AppProviders>
      <Routes>
        {AppRoutes.getAllRoutes().map((route) => (
          <Route
            key={route.name}
            path={route.route}
            element={route.component}
          />
        ))}
      </Routes>
    </AppProviders>
  )
}

export default App
