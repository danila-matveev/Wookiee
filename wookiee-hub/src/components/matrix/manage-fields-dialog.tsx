import { useEffect, useState } from "react"
import { Plus, GripVertical, Trash2 } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { matrixApi, type FieldDefinition } from "@/lib/matrix-api"
import { getBackendType } from "@/lib/entity-registry"
import type { MatrixEntity } from "@/stores/matrix-store"

const FIELD_TYPE_LABELS: Record<string, string> = {
  text: "Текст",
  number: "Число",
  select: "Выбор",
  multi_select: "Мульти-выбор",
  checkbox: "Чекбокс",
  date: "Дата",
  url: "URL",
  file: "Файл",
}

interface ManageFieldsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  entity: string
}

export function ManageFieldsDialog({
  open,
  onOpenChange,
  entity,
}: ManageFieldsDialogProps) {
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [loading, setLoading] = useState(false)
  const [newName, setNewName] = useState("")
  const [newDisplayName, setNewDisplayName] = useState("")
  const [newType, setNewType] = useState("text")

  const entityType = getBackendType(entity as MatrixEntity)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    matrixApi
      .listFields(entityType)
      .then(setFields)
      .catch(() => setFields([]))
      .finally(() => setLoading(false))
  }, [open, entityType])

  async function handleAddField() {
    const fieldName = newName.trim().toLowerCase().replace(/\s+/g, "_")
    const displayName = newDisplayName.trim() || newName.trim()
    if (!fieldName) return

    try {
      const created = await matrixApi.createField(entityType, {
        entity_type: entityType,
        field_name: fieldName,
        display_name: displayName,
        field_type: newType,
      })
      setFields((prev) => [...prev, created])
      setNewName("")
      setNewDisplayName("")
      setNewType("text")
    } catch {
      // TODO: toast error
    }
  }

  async function handleDeleteField(fieldId: number) {
    try {
      await matrixApi.deleteField(entityType, fieldId)
      setFields((prev) => prev.filter((f) => f.id !== fieldId))
    } catch {
      // TODO: toast error
    }
  }

  const customFields = fields.filter((f) => !f.is_system)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Настроить поля</DialogTitle>
        </DialogHeader>

        <div className="space-y-3">
          {loading ? (
            <p className="text-sm text-muted-foreground">Загрузка...</p>
          ) : customFields.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Нет кастомных полей
            </p>
          ) : (
            <div className="space-y-1.5">
              {customFields.map((field) => (
                <div
                  key={field.id}
                  className="flex items-center gap-2 rounded-md border border-border px-2 py-1.5"
                >
                  <GripVertical className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="flex-1 text-sm">{field.display_name}</span>
                  <Badge variant="secondary">
                    {FIELD_TYPE_LABELS[field.field_type] ?? field.field_type}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => handleDeleteField(field.id)}
                    className="h-6 w-6 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          <div className="border-t border-border pt-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Добавить поле
            </p>
            <div className="flex flex-col gap-2">
              <Input
                placeholder="Имя поля (латиница)"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="h-8 text-sm"
              />
              <Input
                placeholder="Отображаемое имя"
                value={newDisplayName}
                onChange={(e) => setNewDisplayName(e.target.value)}
                className="h-8 text-sm"
              />
              <div className="flex items-center gap-2">
                <Select value={newType} onValueChange={setNewType}>
                  <SelectTrigger className="h-8 flex-1 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(FIELD_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  size="sm"
                  onClick={handleAddField}
                  disabled={!newName.trim()}
                  className="gap-1"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Добавить
                </Button>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
