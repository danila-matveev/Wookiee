// wookiee-hub/src/stores/views-store.ts
// Client-side only — saved views stored in localStorage via Zustand persist.
// No backend API calls for view storage (per CONTEXT.md locked decision).
import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { FilterEntry } from "./matrix-store"

export interface SavedViewConfig {
  columns: string[]
  filters: FilterEntry[]
  sort: { field: string; order: "asc" | "desc" } | null
}

export interface SavedView {
  id: string        // crypto.randomUUID()
  entity: string    // e.g. "models", "articles"
  name: string
  config: SavedViewConfig
  createdAt: string // ISO date string
}

interface ViewsState {
  savedViews: SavedView[]
  /** Set when user loads a view — consumed by the page via useEffect */
  loadedViewConfig: SavedViewConfig | null

  addView: (entity: string, name: string, config: SavedViewConfig) => void
  deleteView: (id: string) => void
  loadView: (view: SavedView) => void
  clearLoadedView: () => void
}

export const useViewsStore = create<ViewsState>()(
  persist(
    (set) => ({
      savedViews: [],
      loadedViewConfig: null,

      addView: (entity, name, config) =>
        set((state) => ({
          savedViews: [
            ...state.savedViews,
            {
              id: crypto.randomUUID(),
              entity,
              name,
              config,
              createdAt: new Date().toISOString(),
            },
          ],
        })),

      deleteView: (id) =>
        set((state) => ({
          savedViews: state.savedViews.filter((v) => v.id !== id),
        })),

      loadView: (view) => set({ loadedViewConfig: view.config }),

      clearLoadedView: () => set({ loadedViewConfig: null }),
    }),
    {
      name: "matrix-views-storage", // localStorage key
      // Don't persist loadedViewConfig — it's ephemeral UI state
      partialize: (state) => ({ savedViews: state.savedViews }),
    },
  ),
)
