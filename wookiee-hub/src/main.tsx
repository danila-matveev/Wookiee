import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { RouterProvider } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "sonner"
import { router } from "./router"
import { useThemeStore } from "./stores/theme"
import "./index.css"

const queryClient = new QueryClient()

// Initial sync: outside React render so it runs before first paint.
document.documentElement.classList.toggle(
  "dark",
  useThemeStore.getState().theme === "dark",
)

// Subscribe to theme changes globally — works for all routes including /login (outside AppShell).
useThemeStore.subscribe((s) => {
  document.documentElement.classList.toggle("dark", s.theme === "dark")
})

function App() {
  const theme = useThemeStore((s) => s.theme)
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      {/* W9.18 — единый Toaster для toast-уведомлений (replaces window.alert) */}
      <Toaster richColors position="top-right" closeButton theme={theme} />
    </QueryClientProvider>
  )
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
