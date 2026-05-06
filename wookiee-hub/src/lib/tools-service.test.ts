import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: {
    from: vi.fn(),
  },
}))

import { fetchTools } from '@/lib/tools-service'
import { supabase } from '@/lib/supabase'

const mockRow = {
  slug: 'finance-report',
  display_name: 'finance-report',
  name_ru: 'Финансовый отчёт P&L',
  type: 'skill',
  category: 'analytics',
  status: 'active',
  version: 'v4',
  description: 'Недельный P&L отчёт',
  how_it_works: 'Шаг 1. Загрузка данных',
  run_command: '/finance-report',
  data_sources: ['supabase'],
  depends_on: ['notion'],
  output_targets: ['notion', 'telegram'],
  output_description: 'Notion страница',
  health_check: null,
  skill_md_path: 'finance-report.md',
  required_env_vars: ['OPENROUTER_API_KEY', 'SUPABASE_URL'],
  total_runs: 42,
  last_run_at: '2026-05-04T09:15:00Z',
  last_status: 'success',
}

describe('fetchTools', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('maps display_name to name', async () => {
    vi.mocked(supabase.from).mockReturnValue({
      select: vi.fn().mockReturnValue({
        neq: vi.fn().mockReturnValue({
          eq: vi.fn().mockResolvedValue({ data: [mockRow], error: null }),
        }),
      }),
    } as any)

    const tools = await fetchTools()
    expect(tools[0].name).toBe('finance-report')
    expect(tools[0].nameRu).toBe('Финансовый отчёт P&L')
  })

  it('returns empty array on null data', async () => {
    vi.mocked(supabase.from).mockReturnValue({
      select: vi.fn().mockReturnValue({
        neq: vi.fn().mockReturnValue({
          eq: vi.fn().mockResolvedValue({ data: null, error: { message: 'fail' } }),
        }),
      }),
    } as any)

    const tools = await fetchTools()
    expect(tools).toEqual([])
  })

  it('maps null arrays to empty arrays', async () => {
    const rowWithNulls = { ...mockRow, data_sources: null, depends_on: null, output_targets: null }
    vi.mocked(supabase.from).mockReturnValue({
      select: vi.fn().mockReturnValue({
        neq: vi.fn().mockReturnValue({
          eq: vi.fn().mockResolvedValue({ data: [rowWithNulls], error: null }),
        }),
      }),
    } as any)

    const tools = await fetchTools()
    expect(tools[0].dataSources).toEqual([])
    expect(tools[0].dependsOn).toEqual([])
  })
})
