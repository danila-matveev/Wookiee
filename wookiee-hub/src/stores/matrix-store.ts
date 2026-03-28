// wookiee-hub/src/stores/matrix-store.ts
import { create } from "zustand"
import type { LookupItem } from "@/lib/matrix-api"

export interface FilterEntry {
  field: string        // e.g. "kategoriya_id"
  label: string        // e.g. "Категория"
  values: number[]     // IDs; OR semantics within field
  valueLabels: string[] // e.g. ["Бельё", "Полотенца"] for chip display
}

export type MatrixEntity =
  | "models"
  | "articles"
  | "products"
  | "colors"
  | "factories"
  | "importers"
  | "cards-wb"
  | "cards-ozon"
  | "certs"

export type ViewTab = "spec" | "stock" | "finance" | "rating" | `saved-${string}`

interface MatrixState {
  activeEntity: MatrixEntity
  activeView: ViewTab
  activeFilters: FilterEntry[]
  expandedRows: Set<number>
  selectedRows: Set<number>
  detailPanelId: number | null
  detailPanelEntityType: MatrixEntity | null
  entityUpdateStamp: Partial<Record<MatrixEntity, number>>
  lookupCache: Record<string, LookupItem[]>
  searchOpen: boolean
  searchQuery: string

  setActiveEntity: (entity: MatrixEntity) => void
  setActiveView: (view: ViewTab) => void
  drillDown: (entity: MatrixEntity, field: string, value: number, valueLabel: string) => void
  addFilter: (entry: FilterEntry) => void
  removeFilter: (field: string) => void
  clearFilters: () => void
  setFilters: (filters: FilterEntry[]) => void
  toggleRowExpanded: (id: number) => void
  toggleRowSelected: (id: number) => void
  selectAllRows: (ids: number[]) => void
  clearSelection: () => void
  openDetailPanel: (id: number, entityType?: MatrixEntity) => void
  closeDetailPanel: () => void
  notifyEntityUpdated: (entity: MatrixEntity) => void
  setLookupCache: (table: string, items: LookupItem[]) => void
  setSearchOpen: (open: boolean) => void
  setSearchQuery: (query: string) => void
}

export const useMatrixStore = create<MatrixState>((set) => ({
  activeEntity: "models",
  activeView: "spec",
  activeFilters: [],
  expandedRows: new Set(),
  selectedRows: new Set(),
  detailPanelId: null,
  detailPanelEntityType: null,
  entityUpdateStamp: {},
  lookupCache: {},
  searchOpen: false,
  searchQuery: "",

  setActiveEntity: (entity) => set({ activeEntity: entity, selectedRows: new Set(), activeFilters: [] }),
  setActiveView: (view) => set({ activeView: view }),
  drillDown: (entity, field, value, valueLabel) =>
    set({
      activeEntity: entity,
      activeFilters: [{
        field,
        label: field === "model_osnova_id" ? "Модель" : field,
        values: [value],
        valueLabels: [valueLabel],
      }],
      selectedRows: new Set(),
    }),
  addFilter: (entry) =>
    set((s) => {
      const existing = s.activeFilters.findIndex((f) => f.field === entry.field)
      if (existing >= 0) {
        const next = [...s.activeFilters]
        next[existing] = entry
        return { activeFilters: next }
      }
      return { activeFilters: [...s.activeFilters, entry] }
    }),
  removeFilter: (field) =>
    set((s) => ({ activeFilters: s.activeFilters.filter((f) => f.field !== field) })),
  clearFilters: () => set({ activeFilters: [] }),
  setFilters: (filters) => set({ activeFilters: filters }),
  toggleRowExpanded: (id) =>
    set((s) => {
      const next = new Set(s.expandedRows)
      next.has(id) ? next.delete(id) : next.add(id)
      return { expandedRows: next }
    }),
  toggleRowSelected: (id) =>
    set((s) => {
      const next = new Set(s.selectedRows)
      next.has(id) ? next.delete(id) : next.add(id)
      return { selectedRows: next }
    }),
  selectAllRows: (ids) => set({ selectedRows: new Set(ids) }),
  clearSelection: () => set({ selectedRows: new Set() }),
  openDetailPanel: (id, entityType) =>
    set({ detailPanelId: id, ...(entityType !== undefined ? { detailPanelEntityType: entityType } : {}) }),
  closeDetailPanel: () => set({ detailPanelId: null, detailPanelEntityType: null }),
  notifyEntityUpdated: (entity) =>
    set((s) => ({
      entityUpdateStamp: {
        ...s.entityUpdateStamp,
        [entity]: (s.entityUpdateStamp[entity] ?? 0) + 1,
      },
    })),
  setLookupCache: (table, items) =>
    set((s) => ({ lookupCache: { ...s.lookupCache, [table]: items } })),
  setSearchOpen: (open) => set({ searchOpen: open }),
  setSearchQuery: (query) => set({ searchQuery: query }),
}))
