export type RunStatus = 'success' | 'error' | 'timeout'

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

export interface RunsFilter {
  agentNames?: string[]
  status?: RunStatus | null
  dateFrom?: string | null
  dateTo?: string | null
}
