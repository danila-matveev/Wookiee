import { create } from "zustand"
import { persist } from "zustand/middleware"

interface ThemeState {
  theme: "dark" | "light"
  setTheme: (theme: "dark" | "light") => void
  toggleTheme: () => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: "light",
      setTheme: (theme) => set({ theme }),
      toggleTheme: () =>
        set((s) => ({ theme: s.theme === "dark" ? "light" : "dark" })),
    }),
    { name: "wookiee-theme" }
  )
)
