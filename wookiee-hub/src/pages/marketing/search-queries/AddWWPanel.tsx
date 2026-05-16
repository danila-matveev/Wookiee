import { useState } from 'react'
import { Drawer } from '@/components/crm/ui/Drawer'
import { Button } from '@/components/marketing/Button'
import { Input } from '@/components/marketing/Input'
import { SelectMenu } from '@/components/marketing/SelectMenu'
import { useCreateSubstituteArticle } from '@/hooks/marketing/use-search-queries'
import { useModeli, useArtikulyForModel } from '@/hooks/marketing/use-artikuly'

// Назначения (purpose) для WW-подменок — соответствуют Sheets "Аналитика по запросам" col D.
const WW_PURPOSES = [
  'креаторы',
  'соцсети бренда',
  'блогеры',
  'Telega.in',
  'паблики инст и тг',
  'Adblogger',
  'Яндекс',
  'Таргет ВК',
]

const CAMPAIGN_SUGGESTIONS = [
  'WENDY_креаторы',
  'AUDREY_креатор',
  'VUKI_креаторы',
  'MOON_креаторы',
  'RUBY_креаторы',
]

interface AddWWPanelProps {
  onClose: () => void
}

export function AddWWPanel({ onClose }: AddWWPanelProps) {
  const { data: modeli = [] } = useModeli()
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
        sku_label: matchedArtikul.artikul,
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
        <div className="bg-muted rounded-md border border-border px-3 py-2">
          <div className="text-[10px] uppercase text-muted-foreground">Привязан</div>
          <div className="text-sm text-foreground mt-0.5">{matchedArtikul.artikul}</div>
          {matchedArtikul.nm_id != null && (
            <div className="text-[11px] font-mono text-muted-foreground">NM: {matchedArtikul.nm_id}</div>
          )}
        </div>
      )}
      {!matchedArtikul && modelId !== null && color && size && (
        <div className="bg-amber-50 rounded-md border border-amber-200 px-3 py-2 text-[11px] text-amber-700">
          SKU не найден
        </div>
      )}
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-1">
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
        label="Назначение"
        value={channel}
        placeholder="Выбрать назначение…"
        options={WW_PURPOSES.map((p) => ({ value: p, label: p }))}
        onChange={setChannel}
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
    </div>
  )

  const footer = (
    <Button
      disabled={!canSubmit || createMut.isPending}
      onClick={handleSubmit}
      className="w-full"
    >
      {createMut.isPending ? 'Создаю…' : 'Добавить'}
    </Button>
  )

  return (
    <Drawer open={true} onClose={onClose} title="Новый WW-код" footer={footer}>
      {body}
    </Drawer>
  )
}
