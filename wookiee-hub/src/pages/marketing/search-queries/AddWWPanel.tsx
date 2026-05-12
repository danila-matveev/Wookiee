import { useState } from 'react'
import { X } from 'lucide-react'
import { Drawer } from '@/components/crm/ui/Drawer'
import { Button } from '@/components/marketing/Button'
import { Input } from '@/components/marketing/Input'
import { SelectMenu } from '@/components/marketing/SelectMenu'
import { useCreateSubstituteArticle } from '@/hooks/marketing/use-search-queries'
import { useModeli, useArtikulyForModel } from '@/hooks/marketing/use-artikuly'
import { useChannels } from '@/hooks/marketing/use-channels'

const CAMPAIGN_SUGGESTIONS = [
  'WENDY_креаторы',
  'AUDREY_креатор',
  'VUKI_креаторы',
  'MOON_креаторы',
  'RUBY_креаторы',
  'Яндекс промост',
]

interface AddWWPanelProps {
  onClose: () => void
  /** 'inline' renders bare content for split-pane host; 'drawer' (default) wraps in Drawer. */
  mode?: 'drawer' | 'inline'
}

export function AddWWPanel({ onClose, mode = 'drawer' }: AddWWPanelProps) {
  const { data: modeli = [] } = useModeli()
  const { data: channels = [] } = useChannels()
  const createMut = useCreateSubstituteArticle()

  const [modelId, setModelId] = useState<number | null>(null)
  const [color, setColor] = useState('')
  const [size, setSize] = useState('')
  const [ww, setWw] = useState('')
  const [channel, setChannel] = useState('')
  const [campaign, setCampaign] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: artikuly = [] } = useArtikulyForModel(modelId)

  // Distinct colors derived from artikuly rows for the selected model.
  const availableColors = [...new Set(artikuly.map((a) => a.color).filter((c): c is string => Boolean(c)))]

  // Sizes for the chosen color (distinct, in DB order).
  const availableSizes = [
    ...new Set(
      artikuly
        .filter((a) => a.color === color)
        .map((a) => a.size)
        .filter((s): s is string => Boolean(s)),
    ),
  ]

  const matchedArtikul = artikuly.find((a) => a.color === color && a.size === size)

  const canSubmit = Boolean(matchedArtikul && ww.trim() && channel.trim())

  const handleSubmit = async () => {
    setError(null)
    if (!matchedArtikul) return
    try {
      await createMut.mutateAsync({
        code: ww.trim().toUpperCase(),
        artikul_id: matchedArtikul.id,
        purpose: channel,
        campaign_name: campaign || null,
        nomenklatura_wb: matchedArtikul.nm_id != null ? String(matchedArtikul.nm_id) : null,
      })
      onClose()
    } catch (err) {
      if (err && typeof err === 'object' && 'code' in err && (err as { code?: string }).code === '23505') {
        setError('Такой код уже существует')
      } else if (err instanceof Error && err.message.startsWith('Неизвестный канал')) {
        setError(err.message)
      } else {
        setError(err instanceof Error ? err.message : 'Не удалось создать запись')
      }
    }
  }

  const body = (
    <div className="space-y-3">
      <SelectMenu
        label="Модель"
        value={modelId?.toString() ?? ''}
        placeholder="Выбрать модель…"
        options={modeli.map((m) => ({ value: m.id.toString(), label: m.kod ?? m.nazvanie }))}
        onChange={(v) => {
          setModelId(v ? Number(v) : null)
          setColor('')
          setSize('')
        }}
      />
      {modelId !== null && (
        <SelectMenu
          label="Цвет"
          value={color}
          placeholder="Выбрать цвет…"
          options={availableColors.map((c) => ({ value: c, label: c }))}
          onChange={(v) => {
            setColor(v)
            setSize('')
          }}
        />
      )}
      {color && (
        <SelectMenu
          label="Размер"
          value={size}
          placeholder="Выбрать размер…"
          options={availableSizes.map((s) => ({ value: s, label: s }))}
          onChange={setSize}
        />
      )}
      {matchedArtikul && (
        <div className="bg-stone-50 rounded-md border border-stone-100 px-3 py-2">
          <div className="text-[10px] uppercase text-stone-400">Привязан</div>
          <div className="text-sm text-stone-900 mt-0.5">{matchedArtikul.artikul}</div>
          {matchedArtikul.nm_id != null && (
            <div className="text-[11px] font-mono text-stone-500">NM: {matchedArtikul.nm_id}</div>
          )}
        </div>
      )}
      {!matchedArtikul && modelId !== null && color && size && (
        <div className="bg-amber-50 rounded-md border border-amber-200 px-3 py-2 text-[11px] text-amber-700">
          SKU не найден
        </div>
      )}
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1">
          WW-код
        </label>
        <Input
          className="font-mono uppercase"
          value={ww}
          placeholder="WW..."
          onChange={(e) => setWw(e.target.value)}
        />
      </div>
      <SelectMenu
        label="Канал"
        value={channel}
        placeholder="Выбрать канал…"
        options={channels.map((c) => ({ value: c.slug, label: c.label }))}
        onChange={setChannel}
        allowAdd
      />
      <SelectMenu
        label="Кампания / блогер"
        value={campaign}
        placeholder="Опционально…"
        options={CAMPAIGN_SUGGESTIONS}
        onChange={setCampaign}
        allowAdd
      />
      {error && <p className="text-sm text-danger">{error}</p>}
      <Button
        disabled={!canSubmit || createMut.isPending}
        onClick={handleSubmit}
        className="w-full"
      >
        {createMut.isPending ? 'Создаю…' : 'Добавить'}
      </Button>
    </div>
  )

  if (mode === 'inline') {
    return (
      <div className="flex flex-col h-full">
        <header className="px-5 py-4 border-b border-stone-200 flex items-center justify-between shrink-0">
          <div className="text-sm font-medium text-stone-900">Новый WW-код</div>
          <button
            type="button"
            aria-label="Закрыть"
            onClick={onClose}
            className="p-1.5 rounded-md text-stone-400 hover:bg-stone-100 cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">{body}</div>
      </div>
    )
  }

  return (
    <Drawer open={true} onClose={onClose} title="Новый WW-код">
      {body}
    </Drawer>
  )
}
