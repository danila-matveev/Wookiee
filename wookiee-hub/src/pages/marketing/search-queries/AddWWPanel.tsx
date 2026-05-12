import { useMemo, useState } from 'react'
import { Drawer } from '@/components/crm/ui/Drawer'
import { SelectMenu } from '@/components/marketing/SelectMenu'
import {
  useCreateSubstituteArticle,
  useExistingCampaigns,
} from '@/hooks/marketing/use-search-queries'
import { useChannels } from '@/hooks/marketing/use-channels'
import { useSkuCascade } from '@/hooks/marketing/use-sku-browser'

interface AddWWPanelProps {
  onClose: () => void
}

export function AddWWPanel({ onClose }: AddWWPanelProps) {
  const create = useCreateSubstituteArticle()
  const cascade = useSkuCascade()
  const channelsQ = useChannels()
  const campaignsQ = useExistingCampaigns()

  const [modelId, setModelId] = useState<number | null>(null)
  const [colorId, setColorId] = useState<number | null>(null)
  const [razmerId, setRazmerId] = useState<number | null>(null)
  const [ww, setWw] = useState('')
  const [channel, setChannel] = useState('')
  const [campaign, setCampaign] = useState('')
  const [error, setError] = useState<string | null>(null)

  const colorOpts = colorsForSelect(cascade.colorsForModel(modelId))
  const sizeOpts  = sizesForSelect(cascade.sizesForModelColor(modelId, colorId))
  const matched   = cascade.matchedSku(modelId, colorId, razmerId)

  const modelOptions = useMemo(
    () => cascade.models.map((m) => ({ value: String(m.id), label: m.label })),
    [cascade.models],
  )

  const channelOptions = useMemo(
    () => (channelsQ.data ?? []).map((c) => ({ value: c.slug, label: c.label })),
    [channelsQ.data],
  )

  const campaignOptions = useMemo(
    () => (campaignsQ.data ?? []).map((c) => ({ value: c, label: c })),
    [campaignsQ.data],
  )

  const handleModelChange = (v: string) => {
    setModelId(v ? Number(v) : null)
    setColorId(null)
    setRazmerId(null)
  }

  const handleColorChange = (v: string) => {
    setColorId(v ? Number(v) : null)
    setRazmerId(null)
  }

  const handleSizeChange = (v: string) => {
    setRazmerId(v ? Number(v) : null)
  }

  const canSubmit = Boolean(matched && ww.trim() && channel) && !create.isPending

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!matched) {
      setError('Выберите модель, цвет и размер')
      return
    }
    if (!ww.trim()) {
      setError('WW-код обязателен')
      return
    }
    if (!channel) {
      setError('Выберите канал')
      return
    }

    try {
      await create.mutateAsync({
        code: ww.trim(),
        artikul_id: matched.artikul_id,
        purpose: channel,
        nomenklatura_wb: matched.nomenklatura_wb != null ? String(matched.nomenklatura_wb) : null,
        campaign_name: campaign.trim() || null,
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

  return (
    <Drawer open={true} onClose={onClose} title="Новый WW-код">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <SelectMenu
          label="Модель"
          value={modelId != null ? String(modelId) : ''}
          options={modelOptions}
          onChange={handleModelChange}
          placeholder={cascade.isLoading ? 'Загрузка…' : 'Выбрать модель…'}
          disabled={cascade.isLoading}
          emptyHint="Модели не найдены"
        />

        {modelId != null && (
          <SelectMenu
            label="Цвет"
            value={colorId != null ? String(colorId) : ''}
            options={colorOpts}
            onChange={handleColorChange}
            placeholder="Выбрать цвет…"
            emptyHint="Цвета не найдены"
          />
        )}

        {colorId != null && (
          <SelectMenu
            label="Размер"
            value={razmerId != null ? String(razmerId) : ''}
            options={sizeOpts}
            onChange={handleSizeChange}
            placeholder="Выбрать размер…"
            emptyHint="Размеры не найдены"
          />
        )}

        {matched && (
          <div className="bg-muted/30 rounded-md border border-border px-3 py-2">
            <div className="text-[10px] uppercase text-muted-foreground">Привязан</div>
            <div className="text-sm text-foreground mt-0.5">
              {matched.model_label}/{matched.color_label}_{matched.razmer_label}
            </div>
            <div className="text-[11px] font-mono text-muted-foreground">NM: {matched.nomenklatura_wb}</div>
          </div>
        )}

        {!matched && modelId != null && colorId != null && razmerId != null && (
          <div className="bg-amber-50 dark:bg-amber-950/30 rounded-md border border-amber-200 dark:border-amber-800 px-3 py-2 text-[11px] text-amber-700 dark:text-amber-300">
            SKU не найден
          </div>
        )}

        <div>
          <div className="block text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-1">WW-код</div>
          <input
            value={ww}
            onChange={(e) => setWw(e.target.value)}
            placeholder="WW..."
            autoComplete="off"
            className="w-full rounded-md border border-border bg-card px-2.5 py-1.5 text-sm font-mono uppercase focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
        </div>

        <SelectMenu
          label="Канал"
          value={channel}
          options={channelOptions}
          onChange={setChannel}
          allowAdd
          placeholder={channelsQ.isLoading ? 'Загрузка…' : 'Выбрать канал…'}
          disabled={channelsQ.isLoading}
          emptyHint="Каналы не найдены"
        />

        <SelectMenu
          label="Кампания / блогер"
          value={campaign}
          options={campaignOptions}
          onChange={setCampaign}
          allowAdd
          placeholder="Опционально…"
          emptyHint="Кампаний пока нет"
        />

        <button
          type="submit"
          disabled={!canSubmit}
          className="w-full py-1.5 rounded-md bg-stone-900 text-white text-sm font-medium hover:bg-stone-800 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Добавить
        </button>

        {error && <p className="text-sm text-danger">{error}</p>}
      </form>
    </Drawer>
  )
}

function colorsForSelect(items: { id: number; label: string }[]): { value: string; label: string }[] {
  return items.map((c) => ({ value: String(c.id), label: c.label }))
}

function sizesForSelect(items: { id: number; label: string; order: number }[]): { value: string; label: string }[] {
  return items.map((s) => ({ value: String(s.id), label: s.label }))
}
