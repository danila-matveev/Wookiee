import { useState } from 'react'
import { X } from 'lucide-react'
import { Drawer } from '@/components/crm/ui/Drawer'
import { Button } from '@/components/crm/ui/Button'
import { Input } from '@/components/crm/ui/Input'
import { useCreateBrandQuery } from '@/hooks/marketing/use-search-queries'

interface AddBrandQueryPanelProps {
  onClose: () => void
  /** 'inline' renders bare content for split-pane host; 'drawer' (default) wraps in Drawer. */
  mode?: 'drawer' | 'inline'
}

export function AddBrandQueryPanel({ onClose, mode = 'drawer' }: AddBrandQueryPanelProps) {
  const create = useCreateBrandQuery()

  const [query, setQuery] = useState('')
  const [canonicalBrand, setCanonicalBrand] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!query.trim()) {
      setError('Поисковый запрос обязателен')
      return
    }
    if (!canonicalBrand.trim()) {
      setError('Каноническое название бренда обязательно')
      return
    }

    try {
      await create.mutateAsync({
        query,
        canonical_brand: canonicalBrand,
        notes: notes.trim() || undefined,
      })
      onClose()
    } catch (err) {
      if (err && typeof err === 'object' && 'code' in err && (err as { code?: string }).code === '23505') {
        setError('Такой запрос уже существует')
      } else {
        setError(err instanceof Error ? err.message : 'Не удалось создать запрос')
      }
    }
  }

  const formBody = (
    <form id="add-brand-query-form" onSubmit={handleSubmit} className="flex flex-col gap-5">
      <div className="flex flex-col gap-1.5">
        <label htmlFor="bq-query" className="text-sm font-medium text-fg">
          Поисковый запрос <span className="text-danger">*</span>
        </label>
        <Input
          id="bq-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="wookee, wooky, wuki…"
          autoFocus
          autoComplete="off"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="bq-canonical" className="text-sm font-medium text-fg">
          Канонический бренд <span className="text-danger">*</span>
        </label>
        <Input
          id="bq-canonical"
          value={canonicalBrand}
          onChange={(e) => setCanonicalBrand(e.target.value)}
          placeholder="wookiee"
          autoComplete="off"
        />
        <p className="text-xs text-muted-foreground">Каноническое название бренда (lowercase, для группировки)</p>
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="bq-notes" className="text-sm font-medium text-fg">
          Заметки
        </label>
        <textarea
          id="bq-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Опционально"
          rows={3}
          className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:border-primary-muted focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-muted-fg resize-none"
        />
      </div>

      {error && (
        <p className="text-sm text-danger">{error}</p>
      )}
    </form>
  )

  const footer = (
    <>
      <Button variant="ghost" type="button" onClick={onClose} disabled={create.isPending}>
        Отмена
      </Button>
      <Button
        variant="primary"
        type="submit"
        form="add-brand-query-form"
        loading={create.isPending}
        disabled={create.isPending}
      >
        Создать
      </Button>
    </>
  )

  if (mode === 'inline') {
    return (
      <div className="flex flex-col h-full">
        <header className="px-6 py-4 border-b border-border flex items-center justify-between shrink-0">
          <h2 className="font-semibold text-lg text-fg">Новый брендированный запрос</h2>
          <button
            type="button"
            aria-label="Закрыть"
            className="p-2 rounded-md hover:bg-primary-light cursor-pointer"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-4">{formBody}</div>
        <footer className="px-6 py-4 border-t border-border flex justify-end gap-2 shrink-0">
          {footer}
        </footer>
      </div>
    )
  }

  return (
    <Drawer
      open={true}
      onClose={onClose}
      title="Новый брендированный запрос"
      footer={footer}
    >
      {formBody}
    </Drawer>
  )
}
