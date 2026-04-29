import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { PropsWithChildren } from "react"
import { BrowserRouter } from "react-router-dom"

import { SidebarProvider } from "@/components/ui/sidebar"

const queryClient = new QueryClient()
export const AppProviders = ({ children }: PropsWithChildren<object>) => {
  return (
    <BrowserRouter>
      <SidebarProvider>
        <QueryClientProvider client={queryClient}>
          {/* <ReactQueryDevtools
            initialIsOpen={false}
            buttonPosition="top-right"
          /> */}
          {children}
        </QueryClientProvider>
      </SidebarProvider>
    </BrowserRouter>
  )
}
