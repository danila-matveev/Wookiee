import { create } from 'zustand'
import type { OperationsTool, ToolCategoryFilter } from '@/types/tool'

interface OperationsState {
  tools: OperationsTool[]
  loading: boolean
  categoryFilter: ToolCategoryFilter
  searchQuery: string
  selectedTool: OperationsTool | null
  setTools: (tools: OperationsTool[]) => void
  setLoading: (loading: boolean) => void
  setCategoryFilter: (category: ToolCategoryFilter) => void
  setSearchQuery: (query: string) => void
  setSelectedTool: (tool: OperationsTool | null) => void
}

export const useOperationsStore = create<OperationsState>((set) => ({
  tools: [],
  loading: false,
  categoryFilter: 'all',
  searchQuery: '',
  selectedTool: null,
  setTools: (tools) => set({ tools }),
  setLoading: (loading) => set({ loading }),
  setCategoryFilter: (categoryFilter) => set({ categoryFilter }),
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setSelectedTool: (selectedTool) => set({ selectedTool }),
}))

export function filterTools(
  tools: OperationsTool[],
  category: ToolCategoryFilter,
  query: string
): OperationsTool[] {
  const q = query.toLowerCase().trim()
  return tools.filter((tool) => {
    const matchesCategory = category === 'all' || tool.category === category
    const matchesQuery =
      q === '' ||
      tool.name.toLowerCase().includes(q) ||
      (tool.nameRu ?? '').toLowerCase().includes(q) ||
      (tool.description ?? '').toLowerCase().includes(q)
    return matchesCategory && matchesQuery
  })
}
