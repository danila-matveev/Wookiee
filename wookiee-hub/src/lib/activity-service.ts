import { supabase } from './supabase'
import type { AgentRun, RunsFilter, ToolRun, ToolRunsFilter } from '../types/activity'

export const AGENT_TO_LABEL: Record<string, string> = {
  'margin-analyst': 'Аналитический отчёт',
  'ad-efficiency': 'Аналитический отчёт',
  'revenue-decomposer': 'Аналитический отчёт',
  'report-compiler': 'Аналитический отчёт',
  'hypothesis-tester': 'Аналитический отчёт',
  'organic-vs-paid': 'Аналитический отчёт',
  'prompt-tuner': 'Аналитический отчёт',
  'funnel-digitizer': 'Воронка продаж',
  'keyword-analyst': 'Обзор рынка',
  'campaign-optimizer': 'Маркетинговый отчёт',
  'kb-searcher': 'Поиск фото',
  'price-strategist': 'Финансовый отчёт',
  'pricing-impact-analyst': 'Финансовый отчёт',
  'test-agent': 'Тест',
}

export const TOOL_SLUG_TO_AGENTS: Record<string, string[]> = {
  '/analytics-report': ['margin-analyst', 'ad-efficiency', 'revenue-decomposer', 'report-compiler', 'hypothesis-tester', 'organic-vs-paid', 'prompt-tuner'],
  '/funnel-report': ['funnel-digitizer'],
  '/market-review': ['keyword-analyst'],
  '/marketing-report': ['campaign-optimizer'],
  '/content-search': ['kb-searcher'],
  '/finance-report': ['price-strategist', 'pricing-impact-analyst'],
}

export function getAgentLabel(agentName: string): string {
  return AGENT_TO_LABEL[agentName] ?? agentName
}

export async function fetchRuns(filter?: RunsFilter, limit = 50): Promise<AgentRun[]> {
  let query = supabase
    .from('agent_runs')
    .select('id, run_id, parent_run_id, agent_name, agent_type, status, started_at, finished_at, duration_ms, error_message, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, output_summary, task_type, trigger')
    .order('started_at', { ascending: false })
    .limit(limit)

  if (filter?.agentNames && filter.agentNames.length > 0) {
    query = query.in('agent_name', filter.agentNames)
  }
  if (filter?.status) {
    query = query.eq('status', filter.status)
  }
  if (filter?.dateFrom) {
    query = query.gte('started_at', filter.dateFrom)
  }
  if (filter?.dateTo) {
    query = query.lte('started_at', filter.dateTo)
  }

  const { data, error } = await query

  if (error) {
    console.error('fetchRuns error:', error)
    return []
  }

  return (data ?? []).map((row) => ({
    id: row.id,
    runId: row.run_id,
    parentRunId: row.parent_run_id,
    agentName: row.agent_name,
    agentType: row.agent_type,
    status: row.status,
    startedAt: row.started_at,
    finishedAt: row.finished_at,
    durationMs: row.duration_ms,
    errorMessage: row.error_message,
    model: row.model,
    promptTokens: row.prompt_tokens,
    completionTokens: row.completion_tokens,
    totalTokens: row.total_tokens,
    costUsd: parseFloat(row.cost_usd),
    outputSummary: row.output_summary,
    taskType: row.task_type,
    trigger: row.trigger,
  }))
}

export async function fetchRunsByToolSlug(toolSlug: string, limit = 5): Promise<AgentRun[]> {
  const agentNames = TOOL_SLUG_TO_AGENTS[toolSlug]
  if (!agentNames || agentNames.length === 0) {
    return []
  }
  return fetchRuns({ agentNames }, limit)
}

// ─── tool_runs ──────────────────────────────────────────────────────────────

export async function fetchToolRuns(filter?: ToolRunsFilter, limit = 50): Promise<ToolRun[]> {
  let query = supabase
    .from('tool_runs')
    .select('id, tool_slug, tool_version, status, trigger_type, triggered_by, environment, period_start, period_end, started_at, finished_at, duration_sec, result_url, items_processed, output_sections, error_stage, error_message, notes, model_used, tokens_input, tokens_output')
    .order('started_at', { ascending: false })
    .limit(limit)

  if (filter?.toolSlugs && filter.toolSlugs.length > 0) {
    query = query.in('tool_slug', filter.toolSlugs)
  }
  if (filter?.status) {
    query = query.eq('status', filter.status)
  }
  if (filter?.dateFrom) {
    query = query.gte('started_at', filter.dateFrom)
  }
  if (filter?.dateTo) {
    query = query.lte('started_at', filter.dateTo)
  }

  const { data, error } = await query

  if (error) {
    console.error('fetchToolRuns error:', error)
    return []
  }

  return (data ?? []).map((row) => ({
    id: row.id,
    toolSlug: row.tool_slug,
    toolVersion: row.tool_version,
    status: row.status,
    triggerType: row.trigger_type,
    triggeredBy: row.triggered_by,
    environment: row.environment,
    periodStart: row.period_start,
    periodEnd: row.period_end,
    startedAt: row.started_at,
    finishedAt: row.finished_at,
    durationSec: row.duration_sec,
    resultUrl: row.result_url,
    itemsProcessed: row.items_processed,
    outputSections: row.output_sections,
    errorStage: row.error_stage,
    errorMessage: row.error_message,
    notes: row.notes,
    modelUsed: row.model_used,
    tokensInput: row.tokens_input,
    tokensOutput: row.tokens_output,
  }))
}

export async function fetchToolRunsBySlug(toolSlug: string, limit = 5): Promise<ToolRun[]> {
  return fetchToolRuns({ toolSlugs: [toolSlug] }, limit)
}
