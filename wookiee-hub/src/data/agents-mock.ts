import type { Tool, ToolRun } from "@/types/agents"

/**
 * Mock data for the Агенты module — Phase 1.
 *
 * These entries mirror the shape of real Supabase rows (`tools`, `tool_runs`)
 * but are bundled with the SPA so `/agents/skills` and `/agents/runs` render
 * meaningfully without a Hub auth bootstrap. Phase 1.5 replaces this module
 * with real Supabase queries (RLS-gated by `auth.role() = 'authenticated'`).
 */

export const mockTools: Tool[] = [
  {
    id: "tool-finance-report",
    name: "finance-report",
    category: "analytics",
    version: "v4",
    status: "active",
    description: "Глубокий финансовый отчёт по бренду Wookiee (P&L, юнит-экономика).",
    lastRunAt: "2026-04-24T09:00:00Z",
    lastStatus: "success",
  },
  {
    id: "tool-marketing-report",
    name: "marketing-report",
    category: "analytics",
    version: "v2",
    status: "active",
    description: "Маркетинговая аналитика — воронка, реклама, блогеры, VK, SMM.",
    lastRunAt: "2026-04-23T08:30:00Z",
    lastStatus: "success",
  },
  {
    id: "tool-funnel-report",
    name: "funnel-report",
    category: "analytics",
    version: "v1",
    status: "active",
    description: "Воронка модели: переходы → корзина → заказы → выкупы.",
    lastRunAt: "2026-04-22T07:45:00Z",
    lastStatus: "success",
  },
  {
    id: "tool-daily-brief",
    name: "daily-brief",
    category: "analytics",
    version: "v3",
    status: "active",
    description: "Ежедневный отчёт — финансы, воронка, маркетинг, модели.",
    lastRunAt: "2026-04-25T05:00:00Z",
    lastStatus: "success",
  },
  {
    id: "tool-abc-audit",
    name: "abc-audit",
    category: "analytics",
    version: "v2",
    status: "active",
    description: "ABC-аудит товарной матрицы (WB+OZON) — ABC × ROI.",
    lastRunAt: "2026-04-22T11:20:00Z",
    lastStatus: "error",
  },
  {
    id: "tool-logistics-report",
    name: "logistics-report",
    category: "operations",
    version: "v2.1",
    status: "active",
    description: "Анализ логистики WB+OZON — расходы, локализация, оборачиваемость.",
    lastRunAt: "2026-04-21T14:00:00Z",
    lastStatus: "success",
  },
  {
    id: "tool-finolog-dds",
    name: "finolog-dds-report",
    category: "finance",
    version: "v1",
    status: "active",
    description: "ДДС из Финолога — остатки, прогноз кассового разрыва.",
    lastRunAt: "2026-04-24T16:10:00Z",
    lastStatus: "success",
  },
  {
    id: "tool-reviews-audit",
    name: "reviews-audit",
    category: "community",
    version: "v1",
    status: "active",
    description: "Глубокий аудит отзывов и вопросов — кластеры, gap-analysis.",
    lastRunAt: "2026-04-19T09:30:00Z",
    lastStatus: "success",
  },
  {
    id: "tool-market-review",
    name: "market-review",
    category: "research",
    version: "v1",
    status: "active",
    description: "Ежемесячный обзор рынка и конкурентов через MPStats.",
    lastRunAt: "2026-04-18T12:00:00Z",
    lastStatus: "pending",
  },
  {
    id: "tool-monthly-plan",
    name: "monthly-plan",
    category: "planning",
    version: "v1",
    status: "paused",
    description: "Месячный бизнес-план — multi-wave агенты, цели по марже.",
    lastRunAt: "2026-04-01T10:00:00Z",
    lastStatus: "success",
  },
]

export const mockToolRuns: ToolRun[] = [
  // finance-report
  { id: "run-001", toolId: "tool-finance-report", toolName: "finance-report", status: "success", startedAt: "2026-04-24T09:00:00Z", durationSec: 187, costUsd: 0.42, triggerSource: "cron" },
  { id: "run-002", toolId: "tool-finance-report", toolName: "finance-report", status: "success", startedAt: "2026-04-23T09:00:00Z", durationSec: 192, costUsd: 0.41, triggerSource: "cron" },
  { id: "run-003", toolId: "tool-finance-report", toolName: "finance-report", status: "success", startedAt: "2026-04-22T09:00:00Z", durationSec: 179, costUsd: 0.39, triggerSource: "cron" },
  // marketing-report
  { id: "run-004", toolId: "tool-marketing-report", toolName: "marketing-report", status: "success", startedAt: "2026-04-23T08:30:00Z", durationSec: 305, costUsd: 0.78, triggerSource: "cron" },
  { id: "run-005", toolId: "tool-marketing-report", toolName: "marketing-report", status: "success", startedAt: "2026-04-22T08:30:00Z", durationSec: 298, costUsd: 0.74, triggerSource: "cron" },
  { id: "run-006", toolId: "tool-marketing-report", toolName: "marketing-report", status: "error", startedAt: "2026-04-21T08:30:00Z", durationSec: 42, triggerSource: "cron", errorMessage: "Sheets API timeout (30s)" },
  // funnel-report
  { id: "run-007", toolId: "tool-funnel-report", toolName: "funnel-report", status: "success", startedAt: "2026-04-22T07:45:00Z", durationSec: 224, costUsd: 0.31, triggerSource: "manual" },
  { id: "run-008", toolId: "tool-funnel-report", toolName: "funnel-report", status: "success", startedAt: "2026-04-21T07:45:00Z", durationSec: 218, costUsd: 0.29, triggerSource: "cron" },
  // daily-brief
  { id: "run-009", toolId: "tool-daily-brief", toolName: "daily-brief", status: "success", startedAt: "2026-04-25T05:00:00Z", durationSec: 412, costUsd: 0.56, triggerSource: "cron" },
  { id: "run-010", toolId: "tool-daily-brief", toolName: "daily-brief", status: "success", startedAt: "2026-04-24T05:00:00Z", durationSec: 398, costUsd: 0.54, triggerSource: "cron" },
  { id: "run-011", toolId: "tool-daily-brief", toolName: "daily-brief", status: "success", startedAt: "2026-04-23T05:00:00Z", durationSec: 405, costUsd: 0.55, triggerSource: "cron" },
  { id: "run-012", toolId: "tool-daily-brief", toolName: "daily-brief", status: "success", startedAt: "2026-04-22T05:00:00Z", durationSec: 389, costUsd: 0.53, triggerSource: "cron" },
  // abc-audit
  { id: "run-013", toolId: "tool-abc-audit", toolName: "abc-audit", status: "error", startedAt: "2026-04-22T11:20:00Z", durationSec: 67, triggerSource: "manual", errorMessage: "Supabase RLS denied — service role required" },
  { id: "run-014", toolId: "tool-abc-audit", toolName: "abc-audit", status: "success", startedAt: "2026-04-15T11:20:00Z", durationSec: 521, costUsd: 1.12, triggerSource: "manual" },
  // logistics-report
  { id: "run-015", toolId: "tool-logistics-report", toolName: "logistics-report", status: "success", startedAt: "2026-04-21T14:00:00Z", durationSec: 263, costUsd: 0.48, triggerSource: "cron" },
  { id: "run-016", toolId: "tool-logistics-report", toolName: "logistics-report", status: "success", startedAt: "2026-04-14T14:00:00Z", durationSec: 271, costUsd: 0.51, triggerSource: "cron" },
  // finolog-dds
  { id: "run-017", toolId: "tool-finolog-dds", toolName: "finolog-dds-report", status: "success", startedAt: "2026-04-24T16:10:00Z", durationSec: 142, costUsd: 0.22, triggerSource: "cron" },
  { id: "run-018", toolId: "tool-finolog-dds", toolName: "finolog-dds-report", status: "success", startedAt: "2026-04-17T16:10:00Z", durationSec: 138, costUsd: 0.21, triggerSource: "cron" },
  // reviews-audit
  { id: "run-019", toolId: "tool-reviews-audit", toolName: "reviews-audit", status: "success", startedAt: "2026-04-19T09:30:00Z", durationSec: 612, costUsd: 1.85, triggerSource: "manual" },
  { id: "run-020", toolId: "tool-reviews-audit", toolName: "reviews-audit", status: "error", startedAt: "2026-04-12T09:30:00Z", durationSec: 89, triggerSource: "manual", errorMessage: "OpenRouter rate limit (429)" },
  // market-review
  { id: "run-021", toolId: "tool-market-review", toolName: "market-review", status: "pending", startedAt: "2026-04-18T12:00:00Z", triggerSource: "manual" },
  { id: "run-022", toolId: "tool-market-review", toolName: "market-review", status: "success", startedAt: "2026-03-18T12:00:00Z", durationSec: 845, costUsd: 2.41, triggerSource: "manual" },
  // monthly-plan
  { id: "run-023", toolId: "tool-monthly-plan", toolName: "monthly-plan", status: "success", startedAt: "2026-04-01T10:00:00Z", durationSec: 1240, costUsd: 3.18, triggerSource: "manual" },
  { id: "run-024", toolId: "tool-monthly-plan", toolName: "monthly-plan", status: "success", startedAt: "2026-03-01T10:00:00Z", durationSec: 1180, costUsd: 3.02, triggerSource: "manual" },
  // recent successes
  { id: "run-025", toolId: "tool-finance-report", toolName: "finance-report", status: "success", startedAt: "2026-04-21T09:00:00Z", durationSec: 175, costUsd: 0.38, triggerSource: "cron" },
  { id: "run-026", toolId: "tool-finance-report", toolName: "finance-report", status: "success", startedAt: "2026-04-20T09:00:00Z", durationSec: 181, costUsd: 0.40, triggerSource: "cron" },
  { id: "run-027", toolId: "tool-marketing-report", toolName: "marketing-report", status: "success", startedAt: "2026-04-20T08:30:00Z", durationSec: 312, costUsd: 0.76, triggerSource: "cron" },
  { id: "run-028", toolId: "tool-funnel-report", toolName: "funnel-report", status: "success", startedAt: "2026-04-20T07:45:00Z", durationSec: 220, costUsd: 0.30, triggerSource: "cron" },
  { id: "run-029", toolId: "tool-daily-brief", toolName: "daily-brief", status: "success", startedAt: "2026-04-21T05:00:00Z", durationSec: 401, costUsd: 0.55, triggerSource: "cron" },
  { id: "run-030", toolId: "tool-daily-brief", toolName: "daily-brief", status: "error", startedAt: "2026-04-20T05:00:00Z", durationSec: 23, triggerSource: "cron", errorMessage: "Supabase connection refused" },
]
