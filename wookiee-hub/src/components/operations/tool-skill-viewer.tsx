import { useEffect, useState } from 'react'
import { FileText } from 'lucide-react'

interface ToolSkillViewerProps {
  mdPath: string  // e.g. "finance-report.md"
}

export function ToolSkillViewer({ mdPath }: ToolSkillViewerProps) {
  const [content, setContent] = useState<string | null>(null)
  const [status, setStatus] = useState<'loading' | 'ok' | 'not-found'>('loading')

  useEffect(() => {
    setStatus('loading')
    setContent(null)
    fetch(`/skills/${mdPath}`)
      .then((res) => {
        if (!res.ok) { setStatus('not-found'); return null }
        return res.text()
      })
      .then((text) => {
        if (text !== null) { setContent(text); setStatus('ok') }
      })
      .catch(() => setStatus('not-found'))
  }, [mdPath])

  if (status === 'loading') {
    return <div className="text-[12px] text-muted-foreground">Загружаю документацию...</div>
  }

  if (status === 'not-found') return null

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
        <FileText size={11} />
        Инструкция скилла
      </div>
      <pre className="text-[11px] leading-relaxed whitespace-pre-wrap bg-muted/40 border border-border rounded-lg p-3 text-foreground font-mono overflow-auto max-h-64">
        {content}
      </pre>
    </div>
  )
}
