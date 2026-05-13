import { useState } from 'react'
import { X } from 'lucide-react'
import { Drawer } from '@/components/crm/ui/Drawer'
import { Button } from '@/components/crm/ui/Button'
import { Input } from '@/components/crm/ui/Input'
import { SelectMenu } from '@/components/marketing/SelectMenu'
import { useCreatePromoCode } from '@/hooks/marketing/use-promo-codes'
import { useChannels } from '@/hooks/marketing/use-channels'

interface AddPromoPanelProps {
  onClose: () => void
  /** 'inline' renders bare content for split-pane host; 'drawer' (default) wraps in Drawer. */
  mode?: 'drawer' | 'inline'
}

export function AddPromoPanel({ onClose, mode = 'drawer' }: AddPromoPanelProps) {
  const create = useCreatePromoCode()
  const { data: channels = [] } = useChannels()

  const [code, setCode] = useState('')
  const [channel, setChannel] = useState('')
  const [discountPct, setDiscountPct] = useState('')
  const [validFrom, setValidFrom] = useState('')
  const [validUntil, setValidUntil] = useState('')
  const [error, setError] = useState<string | null>(null)

  const channelOptions = channels.map((c) => ({ value: c.slug, label: c.label }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!code.trim()) {
      setError('Код промокода обязателен')
      return
    }

    try {
      await create.mutateAsync({
        code,
        channel: channel || undefined,
        discount_pct: discountPct ? Number(discountPct) : undefined,
        valid_from: validFrom || undefined,
        valid_until: validUntil || undefined,
      })
      onClose()
    } catch (err) {
      if (err && typeof err === 'object' && 'code' in err && (err as { code?: string }).code === '23505') {
        setError('Промокод с таким кодом уже существует')
      } else {
        setError(err instanceof Error ? err.message : 'Не удалось создать промокод')
      }
    }
  }

  const formBody = (
    <form id="add-promo-form" onSubmit={handleSubmit} className="flex flex-col gap-5">
      <div className="flex flex-col gap-1.5">
        <label htmlFor="promo-code" className="text-sm font-medium text-fg">
          Код <span className="text-danger">*</span>
        </label>
        <Input
          id="promo-code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="SUMMER20"
          autoFocus
          autoComplete="off"
          style={{ textTransform: 'uppercase' }}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-fg">Канал</label>
        <SelectMenu
          value={channel}
          options={channelOptions}
          onChange={setChannel}
          allowAdd={true}
          placeholder="Выбрать канал…"
          newValueLabel="Добавить канал"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="promo-discount" className="text-sm font-medium text-fg">
          Скидка (%)
        </label>
        <Input
          id="promo-discount"
          type="number"
          min={0}
          max={100}
          step={0.01}
          value={discountPct}
          onChange={(e) => setDiscountPct(e.target.value)}
          placeholder="20"
        />
      </div>

      <div className="flex gap-3">
        <div className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="promo-valid-from" className="text-sm font-medium text-fg">
            Действует с
          </label>
          <Input
            id="promo-valid-from"
            type="date"
            value={validFrom}
            onChange={(e) => setValidFrom(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="promo-valid-until" className="text-sm font-medium text-fg">
            Действует по
          </label>
          <Input
            id="promo-valid-until"
            type="date"
            value={validUntil}
            onChange={(e) => setValidUntil(e.target.value)}
            min={validFrom || undefined}
          />
        </div>
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
        form="add-promo-form"
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
          <h2 className="font-semibold text-lg text-fg">Новый промокод</h2>
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
      title="Новый промокод"
      footer={footer}
    >
      {formBody}
    </Drawer>
  )
}
