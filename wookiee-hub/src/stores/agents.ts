import { create } from "zustand"
import type { Tool, ToolRun } from "@/types/agents"
import { agentsService } from "@/lib/agents-service"

interface AgentsState {
  tools: Tool[]
  runs: ToolRun[]
  loading: boolean
  error: string | null
  loadTools: () => Promise<void>
  loadRuns: (toolId?: string) => Promise<void>
}

/**
 * Zustand store for the Агенты module.
 *
 * Phase 1: backed by `agentsService` which returns mock data.
 *
 * TODO(phase 1.5): once Supabase Auth is wired in, agentsService will issue
 * real queries — this store does not need to change.
 */
export const useAgentsStore = create<AgentsState>((set) => ({
  tools: [],
  runs: [],
  loading: false,
  error: null,

  loadTools: async () => {
    set({ loading: true, error: null })
    try {
      const tools = await agentsService.getTools()
      set({ tools, loading: false })
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : "Не удалось загрузить скиллы",
        loading: false,
      })
    }
  },

  loadRuns: async (toolId) => {
    set({ loading: true, error: null })
    try {
      const runs = await agentsService.getRuns(toolId)
      set({ runs, loading: false })
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : "Не удалось загрузить запуски",
        loading: false,
      })
    }
  },
}))
