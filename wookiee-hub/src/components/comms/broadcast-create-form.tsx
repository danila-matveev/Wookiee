import { useState, useRef } from "react"
import { ImagePlus, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { DateRangePicker } from "@/components/shared/date-range-picker"
import { useIntegrationsStore } from "@/stores/integrations"
import { getServiceDef } from "@/config/service-registry"
import type { Broadcast } from "@/types/comms-broadcasts"
import type { DateRange } from "react-day-picker"

const MAX_MESSAGE_LENGTH = 1000

interface BroadcastCreateFormProps {
  onSave: (broadcast: Broadcast) => void
  onCancel: () => void
}

export function BroadcastCreateForm({
  onSave,
  onCancel,
}: BroadcastCreateFormProps) {
  const activeConnections = useIntegrationsStore((s) => s.getActiveConnections())
  const getConnectionById = useIntegrationsStore((s) => s.getConnectionById)

  const [name, setName] = useState("")
  const [connectionId, setConnectionId] = useState(
    activeConnections[0]?.id ?? ""
  )
  const [dateRange, setDateRange] = useState<DateRange | undefined>()
  const [recipientCount, setRecipientCount] = useState("")
  const [message, setMessage] = useState("")
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const isValid = name.trim().length > 0 && connectionId && message.trim().length > 0

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const url = URL.createObjectURL(file)
    setPhotoPreview(url)
  }

  function handleRemovePhoto() {
    setPhotoPreview(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  function handleSubmit() {
    if (!isValid) return

    const connection = getConnectionById(connectionId)
    if (!connection) return

    const svc = getServiceDef(connection.serviceType)

    const broadcast: Broadcast = {
      id: `bc-${Date.now()}`,
      name: name.trim(),
      connectionId,
      serviceType: connection.serviceType,
      storeName: `${svc.label} — ${connection.name}`,
      recipientCount: parseInt(recipientCount, 10) || 0,
      message: message.trim(),
      photoUrl: photoPreview ?? undefined,
      status: "draft",
      createdAt: new Date().toISOString(),
    }

    onSave(broadcast)
  }

  return (
    <div className="bg-card border border-border rounded-[10px] p-5 space-y-4">
      <h2 className="text-[15px] font-semibold">Новая рассылка</h2>

      {/* Name */}
      <div className="space-y-1.5">
        <label className="text-[13px] font-medium text-foreground">
          Название рассылки
        </label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Введите название"
        />
      </div>

      {/* Store select */}
      <div className="space-y-1.5">
        <label className="text-[13px] font-medium text-foreground">
          Выберите магазин
        </label>
        {activeConnections.length === 0 ? (
          <p className="text-[12px] text-muted-foreground">
            Нет активных подключений. Добавьте подключение в разделе Интеграции.
          </p>
        ) : (
          <select
            value={connectionId}
            onChange={(e) => setConnectionId(e.target.value)}
            className="h-8 w-full px-3 rounded-lg border border-border bg-card text-sm focus:outline-none focus:ring-1 focus:ring-accent"
          >
            {activeConnections.map((c) => {
              const def = getServiceDef(c.serviceType)
              return (
                <option key={c.id} value={c.id}>
                  {def.label} — {c.name}
                </option>
              )
            })}
          </select>
        )}
      </div>

      {/* Date range */}
      <div className="space-y-1.5">
        <label className="text-[13px] font-medium text-foreground">
          Диапазон дат
        </label>
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>

      {/* Recipient count */}
      <div className="space-y-1.5">
        <label className="text-[13px] font-medium text-foreground">
          Количество получателей
        </label>
        <Input
          type="number"
          value={recipientCount}
          onChange={(e) => setRecipientCount(e.target.value)}
          placeholder="Максимум 199"
          min={0}
          max={199}
        />
      </div>

      {/* Message */}
      <div className="space-y-1.5">
        <label className="text-[13px] font-medium text-foreground">
          Текст рассылки
        </label>
        <Textarea
          value={message}
          onChange={(e) => {
            if (e.target.value.length <= MAX_MESSAGE_LENGTH) {
              setMessage(e.target.value)
            }
          }}
          placeholder="Введите текст рассылки..."
          rows={4}
        />
        <p className="text-[11px] text-muted-foreground text-right">
          {message.length} / {MAX_MESSAGE_LENGTH}
        </p>
      </div>

      {/* Photo upload */}
      <div className="space-y-1.5">
        <label className="text-[13px] font-medium text-foreground">
          Добавьте фото
        </label>
        {photoPreview ? (
          <div className="relative inline-block">
            <img
              src={photoPreview}
              alt="preview"
              className="w-32 h-32 object-cover rounded-lg border border-border"
            />
            <button
              type="button"
              onClick={handleRemovePhoto}
              className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-destructive text-white flex items-center justify-center"
            >
              <X className="size-3" />
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-2 px-4 py-3 rounded-lg border-2 border-dashed border-border text-[13px] text-muted-foreground hover:border-accent hover:text-foreground transition-colors"
          >
            <ImagePlus className="size-4" />
            PNG или JPG (необязательно)
          </button>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2">
        <Button onClick={handleSubmit} disabled={!isValid}>
          Сохранить
        </Button>
        <Button variant="outline" onClick={onCancel}>
          Отмена
        </Button>
      </div>
    </div>
  )
}
