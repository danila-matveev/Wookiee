/**
 * Types for the Агенты module — mirrors Supabase `tools` and `tool_runs` schema.
 * In Phase 1 the Hub uses mock data (see src/data/agents-mock.ts);
 * Phase 1.5 will replace mock loaders with real Supabase queries (RLS-gated).
 */

export type ToolStatus = "active" | "paused" | "deprecated"

export type RunStatus = "success" | "error" | "pending"

export interface Tool {
  id: string
  name: string
  category: string
  version: string
  status: ToolStatus
  description?: string
  lastRunAt?: string
  lastStatus?: RunStatus
}

export interface ToolRun {
  id: string
  toolId: string
  toolName: string
  status: RunStatus
  startedAt: string
  /** Duration in seconds (computed from started_at / finished_at on the backend). */
  durationSec?: number
  costUsd?: number
  triggerSource?: string
  errorMessage?: string
}
