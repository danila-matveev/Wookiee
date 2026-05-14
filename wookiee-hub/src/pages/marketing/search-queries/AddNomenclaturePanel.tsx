import { useState } from 'react'
import { Drawer } from '@/components/crm/ui/Drawer'
import { Button } from '@/components/marketing/Button'
import { Input } from '@/components/marketing/Input'
import { SelectMenu } from '@/components/marketing/SelectMenu'
import { useCreateSubstituteArticle } from '@/hooks/marketing/use-search-queries'
import { useModeli, useArtikulyForModel } from '@/hooks/marketing/use-artikuly'

// "Артикулы внешний лид" — цифровая номенклатура WB. Назначения из Sheets:
const NM_PURPOSES = ['Яндекс', 'Таргет ВК', 'Adblogger']

interface AddNomenclaturePanelProps {
  onClose: () => void
}

export function AddNomenclaturePanel({ onClose }: AddNomenclaturePanelProps) {
  const { data: modeli = [] } = useModeli()
  const createMut = useCreateSubstituteArticle()

  const [modelId, setModelId] = useState<number | null>(null)
  const [color, setColor] = useState('')
  const [size, setSize] = useState('')
  const [purpose, setPurpose] = useState('')
  const [campaign, setCampaign] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: artikuly = [] } = useArtikulyForModel(modelId)
  const availableColors = [...new Set(artikuly.map((a) => a.color).filter((c): c is string => Boolean(c)))]
  const availableSizes = [
    ...new Set(
      artikuly
        .filter((a) => a.color === color)
        .map((a) => a.size)
        .filter((s): s is string => Boolean(s)),
    ),
  ]
  const matchedArtikul = artikuly.find((a) => a.color === color && a.size === size)

  const canSubmit = Boolean(matchedArtikul?.nm_id && purpose.trim())

  const handleSubmit = async () => {
    setError(null)
    if (!matchedArtikul || !matchedArtikul.nm_id) {
      setError('У выбранного артикула нет WB nm_id')
      return
    }
    const nmStr = String(matchedArtikul.nm_id)
    try {
      await createMut.mutateAsync({
        code: nmStr,
        artikul_id: matchedArtikul.id,
        purpose,
        campaign_name: campaign || null,
        nomenklatura_wb: nmStr,
        sku_label: matchedArtikul.artikul,
      })
      onClose()
    } catch (err) {
      if (err && typeof err === 'object' && 'code' in err && (err as { code?: string }).code === '23505') {
        setError('Такой nm_id уже добавлен')
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
          <div className="text-[10px] uppercase text-stone-400">Артикул</div>
          <div className="text-sm text-stone-900 mt-0.5">{matchedArtikul.artikul}</div>
          {matchedArtikul.nm_id != null && (
            <div className="text-[11px] font-mono text-stone-500">NM: {matchedArtikul.nm_id}</div>
          )}
          {matchedArtikul.nm_id == null && (
            <div className="text-[11px] text-amber-600">⚠ NM не привязан в каталоге</div>
          )}
        </div>
      )}
      <SelectMenu
        label="Назначение"
        value={purpose}
        placeholder="Выбрать назначение…"
        options={NM_PURPOSES.map((p) => ({ value: p, label: p }))}
        onChange={setPurpose}
      />
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1">
          Кампания
        </label>
        <Input
          value={campaign}
          placeholder="Опционально"
          onChange={(e) => setCampaign(e.target.value)}
        />
      </div>
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
    <Drawer open={true} onClose={onClose} title="Новый артикул WB (номенклатура)" footer={footer}>
      {body}
    </Drawer>
  )
}
