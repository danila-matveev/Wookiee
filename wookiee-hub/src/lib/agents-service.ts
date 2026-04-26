import type { Tool, ToolRun } from "@/types/agents"
import { mockTools, mockToolRuns } from "@/data/agents-mock"

/**
 * Service layer for the Агенты module.
 *
 * Phase 1: returns bundled mock data so /agents/skills and /agents/runs render
 * without an authenticated Supabase session.
 *
 * TODO(phase 1.5): replace these stubs with real Supabase queries via
 * `import { supabase } from "@/lib/supabase"`. Example:
 *   const { data, error } = await supabase.from("tools").select("*").order("name")
 * RLS requires `auth.role() = 'authenticated'`, so the Hub must ship a
 * Supabase Auth bootstrap (magic-link or pre-shared session) first.
 */
export const agentsService = {
  async getTools(): Promise<Tool[]> {
    // TODO(phase 1.5): replace mock with supabase.from("tools").select("*")
    return Promise.resolve(mockTools)
  },

  async getRuns(toolId?: string): Promise<ToolRun[]> {
    // TODO(phase 1.5): replace mock with supabase.from("tool_runs").select("*")
    const runs = toolId
      ? mockToolRuns.filter((r) => r.toolId === toolId)
      : mockToolRuns
    // Newest first — mirrors `order("started_at", { ascending: false })`.
    const sorted = [...runs].sort(
      (a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime()
    )
    return Promise.resolve(sorted)
  },
}
