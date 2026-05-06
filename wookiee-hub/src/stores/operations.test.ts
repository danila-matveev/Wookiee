import { describe, it, expect, beforeEach } from 'vitest'
import { useOperationsStore, filterTools } from '@/stores/operations'
import type { OperationsTool } from '@/types/tool'

const makeTool = (overrides: Partial<OperationsTool>): OperationsTool => ({
  slug: 'test-tool',
  name: 'test-tool',
  nameRu: 'Тестовый тулз',
  type: 'skill',
  category: 'analytics',
  status: 'active',
  version: 'v1',
  description: 'Описание',
  howItWorks: null,
  runCommand: null,
  dataSources: [],
  dependsOn: [],
  outputTargets: [],
  outputDescription: null,
  healthCheck: null,
  skillMdPath: null,
  requiredEnvVars: [],
  totalRuns: 0,
  lastRunAt: null,
  lastStatus: null,
  usageExamples: null,
  docUrl: null,
  ...overrides,
})

const tools = [
  makeTool({ slug: 'finance', category: 'analytics', name: 'finance-report' }),
  makeTool({ slug: 'sheets', category: 'infra', name: 'sheets-sync' }),
  makeTool({ slug: 'hygiene', category: 'infra', name: 'hygiene', status: 'active' }),
]

describe('filterTools', () => {
  it('returns all tools when category is "all" and query empty', () => {
    expect(filterTools(tools, 'all', '')).toHaveLength(3)
  })

  it('filters by category', () => {
    const result = filterTools(tools, 'infra', '')
    expect(result).toHaveLength(2)
    expect(result.every(t => t.category === 'infra')).toBe(true)
  })

  it('filters by search query on name', () => {
    const result = filterTools(tools, 'all', 'finance')
    expect(result).toHaveLength(1)
    expect(result[0].slug).toBe('finance')
  })

  it('search is case-insensitive', () => {
    const result = filterTools(tools, 'all', 'HYGIENE')
    expect(result).toHaveLength(1)
  })
})
