import { useState } from 'react'
import { Drawer } from '@/components/crm/ui/Drawer'
import { Button } from '@/components/crm/ui/Button'
import { Input } from '@/components/crm/ui/Input'
import { useCreateBrandQuery } from '@/hooks/marketing/use-search-queries'

interface AddBrandQueryPanelProps {
  onClose: () => void
}

export function AddBrandQueryPanel({ onClose }: AddBrandQueryPanelProps) {
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

    // Default canonical brand to the query itself (lowercased) if user left it blank.
    // Most запросы где запрос === бренд (например "wooki" → "wooki"). Для алиасов
    // юзер может явно прописать каноническое имя ("шарлот" → "charlotte").
    const canonical = canonicalBrand.trim() || query.trim().toLowerCase()

    try {
      await create.mutateAsync({
        query,
        canonical_brand: canonical,
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

      <details className="group rounded-md border border-border bg-card/50 px-3 py-2">
        <summary className="cursor-pointer text-sm font-medium text-fg list-none flex items-center justify-between select-none">
          <span>Алиас бренда (опционально)</span>
          <span className="text-xs text-muted-foreground group-open:hidden">показать</span>
          <span className="text-xs text-muted-foreground hidden group-open:inline">скрыть</span>
        </summary>
        <div className="flex flex-col gap-1.5 mt-3">
          <label htmlFor="bq-canonical" className="text-xs text-muted-foreground">
            Канонический бренд
          </label>
          <Input
            id="bq-canonical"
            value={canonicalBrand}
            onChange={(e) => setCanonicalBrand(e.target.value)}
            placeholder={query.trim() ? query.trim().toLowerCase() : 'оставь пустым — возьмём запрос'}
            autoComplete="off"
          />
          <p className="text-xs text-muted-foreground">
            Если «вуки» — это другое написание «wookiee», укажи canonical = <span className="font-mono">wookiee</span>.
            Тогда «вуки» сгруппируется с другими формами этого же бренда. Если запрос уже на латинице — оставь пустым.
          </p>
        </div>
      </details>

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
