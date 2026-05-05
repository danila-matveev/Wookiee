import { X, Terminal, ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { OperationsTool } from '@/types/tool'
import { ToolSkillViewer } from './tool-skill-viewer'

const STATUS_LABEL: Record<string, string> = {
  active:     'Активен',
  deprecated: 'Устарел',
  draft:      'Черновик',
  archived:   'Архив',
}
const STATUS_CLASS: Record<string, string> = {
  active:     'bg-green-100 text-green-700',
  deprecated: 'bg-amber-100 text-amber-700',
  draft:      'bg-gray-100 text-gray-600',
  archived:   'bg-red-100 text-red-700',
}
const CATEGORY_LABEL: Record<string, string> = {
  analytics:  'Аналитика',
  infra:      'Инфраструктура',
  content:    'Контент',
  publishing: 'Публикация',
  team:       'Команда',
  planning:   'Планирование',
}

function formatLastRunPanel(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 1) return 'только что'
  if (h < 24) return `${h}ч назад`
  return `${Math.floor(h / 24)}д назад`
}

interface SectionProps { label: string; children: React.ReactNode }
function Section({ label, children }: SectionProps) {
  return (
    <div className="space-y-2">
      {label && <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{label}</p>}
      {children}
      <div className="border-t border-border/50 mt-4 pt-0" />
    </div>
  )
}

interface ToolDetailPanelProps {
  tool: OperationsTool
  onClose: () => void
}

export function ToolDetailPanel({ tool, onClose }: ToolDetailPanelProps) {
  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40" onClick={onClose} />

      {/* Panel */}
      <aside className="fixed right-0 top-0 bottom-0 z-50 w-[480px] max-w-full bg-card border-l border-border shadow-xl overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-card border-b border-border px-5 py-4 flex items-start justify-between">
          <div>
            <p className="font-mono text-[15px] font-bold text-foreground">{tool.name}</p>
            {tool.nameRu && (
              <p className="text-[13px] text-muted-foreground mt-0.5">{tool.nameRu}</p>
            )}
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded', STATUS_CLASS[tool.status])}>
                {STATUS_LABEL[tool.status] ?? tool.status}
              </span>
              <span className="text-[10px] bg-muted text-muted-foreground px-2 py-0.5 rounded">
                {CATEGORY_LABEL[tool.category] ?? tool.category}
              </span>
              {tool.version && (
                <span className="text-[10px] text-muted-foreground font-mono">{tool.version}</span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-5 space-y-5">

          {/* Description */}
          {tool.description && (
            <Section label="Что делает">
              <p className="text-[13px] text-foreground leading-relaxed">{tool.description}</p>
            </Section>
          )}

          {/* How it works */}
          {tool.howItWorks && (
            <Section label="Как работает">
              <pre className="text-[12px] text-foreground leading-relaxed whitespace-pre-wrap font-sans">
                {tool.howItWorks}
              </pre>
            </Section>
          )}

          {/* Skill .md doc viewer (only for skills with mdPath) */}
          {tool.type === 'skill' && tool.skillMdPath && (
            <Section label="">
              <ToolSkillViewer mdPath={tool.skillMdPath} />
            </Section>
          )}

          {/* Run command */}
          {tool.runCommand && (
            <Section label="Команда запуска">
              <div className="flex items-center gap-2 bg-muted/50 border border-border rounded-lg px-3 py-2">
                <Terminal size={13} className="text-muted-foreground shrink-0" />
                <code className="text-[12px] font-mono text-foreground flex-1">{tool.runCommand}</code>
              </div>
            </Section>
          )}

          {/* Health check (services) */}
          {tool.healthCheck && (
            <Section label="Как проверить">
              <div className="bg-muted/50 border border-border rounded-lg px-3 py-2">
                <code className="text-[12px] font-mono text-foreground">{tool.healthCheck}</code>
              </div>
            </Section>
          )}

          {/* Dependencies */}
          {(tool.dependsOn.length > 0 || tool.dataSources.length > 0) && (
            <Section label="Зависимости">
              <div className="flex flex-wrap gap-2">
                {[...tool.dataSources, ...tool.dependsOn].map((dep) => (
                  <span key={dep} className="text-[11px] bg-muted border border-border rounded px-2 py-0.5 text-muted-foreground">
                    {dep}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {/* Output */}
          {(tool.outputTargets.length > 0 || tool.outputDescription) && (
            <Section label="Результат">
              {tool.outputDescription && (
                <p className="text-[12px] text-foreground mb-2">{tool.outputDescription}</p>
              )}
              {tool.outputTargets.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  <ArrowRight size={12} className="text-muted-foreground" />
                  {tool.outputTargets.map((t) => (
                    <span key={t} className="text-[11px] bg-green-50 border border-green-200 text-green-700 rounded px-2 py-0.5">
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </Section>
          )}

          {/* Required env vars (skills only) */}
          {tool.type === 'skill' && tool.requiredEnvVars.length > 0 && (
            <Section label="Переменные окружения">
              <div className="flex flex-wrap gap-2">
                {tool.requiredEnvVars.map((v) => (
                  <code key={v} className="text-[11px] bg-amber-50 border border-amber-200 text-amber-700 rounded px-2 py-0.5 font-mono">
                    {v}
                  </code>
                ))}
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">Задать в .env файле проекта</p>
            </Section>
          )}

          {/* Run stats — from tools table, available Phase 1 */}
          <Section label="Статистика запусков">
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-muted/40 border border-border rounded-lg p-3">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">Всего</p>
                <p className="text-xl font-bold text-foreground">{tool.totalRuns}</p>
              </div>
              <div className="bg-muted/40 border border-border rounded-lg p-3">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">Последний</p>
                <p className="text-[12px] text-foreground">{tool.lastRunAt ? formatLastRunPanel(tool.lastRunAt) : '—'}</p>
              </div>
              <div className={cn(
                'border rounded-lg p-3',
                tool.lastStatus === 'error' ? 'bg-red-50 border-red-200' : 'bg-muted/40 border-border'
              )}>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">Статус</p>
                <p className={cn(
                  'text-[12px] font-medium',
                  tool.lastStatus === 'error'   ? 'text-red-600' :
                  tool.lastStatus === 'success' ? 'text-green-600' : 'text-muted-foreground'
                )}>
                  {tool.lastStatus ?? '—'}
                </p>
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground mt-2">Детальная история запусков — Phase 2</p>
          </Section>

        </div>
      </aside>
    </>
  )
}
