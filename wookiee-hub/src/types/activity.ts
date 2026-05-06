export type RunStatus = 'success' | 'error' | 'timeout' | 'running'

export interface AgentRun {
  id: string
  runId: string
  parentRunId: string | null
  agentName: string
  agentType: string
  status: RunStatus
  startedAt: string
  finishedAt: string | null
  durationMs: number | null
  errorMessage: string | null
  model: string | null
  promptTokens: number
  completionTokens: number
  totalTokens: number
  costUsd: number
  outputSummary: string | null
  taskType: string | null
  trigger: string | null
}

export interface ToolRun {
  id: string
  toolSlug: string
  toolVersion: string | null
  status: RunStatus
  triggerType: string
  triggeredBy: string | null
  environment: string | null
  periodStart: string | null
  periodEnd: string | null
  startedAt: string
  finishedAt: string | null
  durationSec: number | null
  resultUrl: string | null
  itemsProcessed: number | null
  outputSections: number | null
  errorStage: string | null
  errorMessage: string | null
  notes: string | null
  modelUsed: string | null
  tokensInput: number | null
  tokensOutput: number | null
}

export interface RunsFilter {
  agentNames?: string[]
  status?: RunStatus | null
  dateFrom?: string | null
  dateTo?: string | null
}

export interface ToolRunsFilter {
  toolSlugs?: string[]
  status?: RunStatus | null
  dateFrom?: string | null
  dateTo?: string | null
}
