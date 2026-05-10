import { useState } from 'react'
import { Drawer } from '@/components/crm/ui/Drawer'
import { Button } from '@/components/crm/ui/Button'
import { Input } from '@/components/crm/ui/Input'
import { SelectMenu } from '@/components/marketing/SelectMenu'
import { useCreateSubstituteArticle } from '@/hooks/marketing/use-search-queries'
import { useModeli, useArtikulyForModel } from '@/hooks/marketing/use-artikuly'
import { useChannels } from '@/hooks/marketing/use-channels'

interface AddWWPanelProps {
  onClose: () => void
}

export function AddWWPanel({ onClose }: AddWWPanelProps) {
  const create = useCreateSubstituteArticle()

  const [modelId, setModelId] = useState<string>('')
  const [artikulId, setArtikulId] = useState<string>('')
  const [code, setCode] = useState('')
  const [purpose, setPurpose] = useState('')
  const [campaignName, setCampaignName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const modeliQ = useModeli()
  const selectedModelId = modelId ? Number(modelId) : null
  const artikulyQ = useArtikulyForModel(selectedModelId)
  const channelsQ = useChannels()

  const modelOptions = (modeliQ.data ?? []).map((m) => ({
    value: String(m.id),
    label: m.nazvanie + (m.kod ? ` (${m.kod})` : ''),
  }))

  const artikulOptions = (artikulyQ.data ?? []).map((a) => ({
    value: String(a.id),
    label: `${a.artikul} • ${a.color_label ?? '—'} • WB ${a.nomenklatura_wb ?? '—'}`,
  }))

  const channelOptions = (channelsQ.data ?? []).map((c) => ({
    value: c.slug,
    label: c.label,
  }))

  const handleModelChange = (v: string) => {
    setModelId(v)
    setArtikulId('') // reset artikul when model changes
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!modelId) {
      setError('Выберите модель')
      return
    }
    if (!artikulId) {
      setError('Выберите артикул')
      return
    }
    if (!code.trim()) {
      setError('Код обязателен')
      return
    }
    if (!purpose) {
      setError('Выберите канал')
      return
    }

    // Find nomenklatura_wb from selected artikul
    const artikulRow = artikulyQ.data?.find((a) => String(a.id) === artikulId)
    const nomenklatura_wb = artikulRow?.nomenklatura_wb != null
      ? String(artikulRow.nomenklatura_wb)
      : null

    try {
      await create.mutateAsync({
        code: code.trim(),
        artikul_id: Number(artikulId),
        purpose,
        nomenklatura_wb,
        campaign_name: campaignName.trim() || null,
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
    <Drawer
      open={true}
      onClose={onClose}
      title="Новый WW-код"
      footer={
        <>
          <Button variant="ghost" type="button" onClick={onClose} disabled={create.isPending}>
            Отмена
          </Button>
          <Button
            variant="primary"
            type="submit"
            form="add-ww-form"
            loading={create.isPending}
            disabled={create.isPending}
          >
            Создать
          </Button>
        </>
      }
    >
      <form id="add-ww-form" onSubmit={handleSubmit} className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-fg">
            Модель <span className="text-danger">*</span>
          </label>
          <SelectMenu
            value={modelId}
            options={modelOptions}
            onChange={handleModelChange}
            placeholder={modeliQ.isLoading ? 'Загрузка…' : 'Выбрать модель…'}
            disabled={modeliQ.isLoading}
            emptyHint="Модели не найдены"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-fg">
            Артикул <span className="text-danger">*</span>
          </label>
          <SelectMenu
            value={artikulId}
            options={artikulOptions}
            onChange={setArtikulId}
            placeholder={
              !modelId
                ? 'Сначала выберите модель'
                : artikulyQ.isLoading
                ? 'Загрузка…'
                : 'Выбрать артикул…'
            }
            disabled={!modelId || artikulyQ.isLoading}
            emptyHint="Артикулы не найдены (нет nomenklatura_wb)"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="ww-code" className="text-sm font-medium text-fg">
            Код <span className="text-danger">*</span>
          </label>
          <Input
            id="ww-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="WW123456 или 246928570"
            autoFocus
            autoComplete="off"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-fg">
            Канал <span className="text-danger">*</span>
          </label>
          <SelectMenu
            value={purpose}
            options={channelOptions}
            onChange={setPurpose}
            placeholder={channelsQ.isLoading ? 'Загрузка…' : 'Выбрать канал…'}
            disabled={channelsQ.isLoading}
            emptyHint="Каналы не найдены"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="ww-campaign" className="text-sm font-medium text-fg">
            Кампания / название
          </label>
          <Input
            id="ww-campaign"
            value={campaignName}
            onChange={(e) => setCampaignName(e.target.value)}
            placeholder="Название кампании (опционально)"
            autoComplete="off"
          />
          <p className="text-xs text-muted-foreground">
            Для именного креатора: <code className="font-mono bg-muted px-1 rounded">креатор_&lt;Имя&gt;</code> (creator_ref заполнится автоматически)
          </p>
        </div>

        {error && (
          <p className="text-sm text-danger">{error}</p>
        )}
      </form>
    </Drawer>
  )
}
