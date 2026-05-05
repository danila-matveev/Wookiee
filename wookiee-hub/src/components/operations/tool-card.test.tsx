import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ToolCard } from '@/components/operations/tool-card'
import type { OperationsTool } from '@/types/tool'

const tool: OperationsTool = {
  slug: 'finance-report',
  name: 'finance-report',
  nameRu: 'Финансовый отчёт',
  type: 'skill',
  category: 'analytics',
  status: 'active',
  version: 'v4',
  description: 'Формирует P&L отчёт',
  howItWorks: null,
  runCommand: '/finance-report',
  dataSources: [],
  dependsOn: [],
  outputTargets: [],
  outputDescription: null,
  healthCheck: null,
  skillMdPath: 'finance-report.md',
  requiredEnvVars: ['OPENROUTER_API_KEY'],
  totalRuns: 5,
  lastRunAt: '2026-05-04T09:00:00Z',
  lastStatus: 'success',
}

describe('ToolCard', () => {
  it('renders tool name', () => {
    render(<ToolCard tool={tool} onSelect={vi.fn()} />)
    expect(screen.getByText('finance-report')).toBeInTheDocument()
  })

  it('renders Russian name when present', () => {
    render(<ToolCard tool={tool} onSelect={vi.fn()} />)
    expect(screen.getByText('Финансовый отчёт')).toBeInTheDocument()
  })

  it('does not render Russian name when null', () => {
    render(<ToolCard tool={{ ...tool, nameRu: null }} onSelect={vi.fn()} />)
    expect(screen.queryByText('Финансовый отчёт')).not.toBeInTheDocument()
  })

  it('calls onSelect with tool when clicked', () => {
    const onSelect = vi.fn()
    render(<ToolCard tool={tool} onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('article'))
    expect(onSelect).toHaveBeenCalledWith(tool)
  })

  it('shows green dot for active tool with success last status', () => {
    render(<ToolCard tool={tool} onSelect={vi.fn()} />)
    const indicator = document.querySelector('[data-status="active"]')
    expect(indicator).toBeInTheDocument()
    expect(indicator).toHaveClass('bg-green-500')
  })

  it('shows red dot and error border when lastStatus is error', () => {
    render(<ToolCard tool={{ ...tool, lastStatus: 'error' }} onSelect={vi.fn()} />)
    const indicator = document.querySelector('[data-last-status="error"]')
    expect(indicator).toBeInTheDocument()
    expect(indicator).toHaveClass('bg-red-500')
    expect(screen.getByRole('article')).toHaveClass('border-red-300')
  })
})
