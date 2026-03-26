import { useState, type FormEvent } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
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
import { matrixApi } from "@/lib/matrix-api"
import type { FieldDefinition, LookupItem } from "@/lib/matrix-api"
import { LOOKUP_TABLE_MAP } from "@/components/matrix/panel/types"

interface CreateRecordDialogProps {
  entityType: string
  fieldDefs: FieldDefinition[]
  lookupCache: Record<string, LookupItem[]>
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (id: number) => void
}

/**
 * Map from entity type to the matrixApi create method.
 */
const CREATE_FN: Record<
  string,
  (data: Record<string, unknown>) => Promise<{ id: number }>
> = {
  models: matrixApi.createModel as (data: Record<string, unknown>) => Promise<{ id: number }>,
  articles: matrixApi.createArticle as (data: Record<string, unknown>) => Promise<{ id: number }>,
  products: matrixApi.createProduct as (data: Record<string, unknown>) => Promise<{ id: number }>,
}

/**
 * Essential required fields per entity type (at minimum).
 */
const REQUIRED_FIELDS: Record<string, Set<string>> = {
  models: new Set(["kod"]),
  articles: new Set(["artikul"]),
  products: new Set(["barkod"]),
}

/**
 * Determine which fields should appear in the create form.
 * - Not system fields
 * - Field type is text, number, reference, or select
 * - Field name does NOT end in _name (computed joins)
 */
function getFormFields(fieldDefs: FieldDefinition[]): FieldDefinition[] {
  return fieldDefs.filter((f) => {
    if (f.is_system) return false
    if (f.field_name.endsWith("_name")) return false
    if (f.field_name.endsWith("_count")) return false
    const allowedTypes = new Set(["text", "number", "reference", "select"])
    return allowedTypes.has(f.field_type)
  })
}

function isLookupField(fieldName: string): boolean {
  return fieldName in LOOKUP_TABLE_MAP
}

export function CreateRecordDialog({
  entityType,
  fieldDefs,
  lookupCache,
  open,
  onOpenChange,
  onCreated,
}: CreateRecordDialogProps) {
  const [formData, setFormData] = useState<Record<string, string | number | null>>({})
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const formFields = getFormFields(fieldDefs)
  const requiredSet = REQUIRED_FIELDS[entityType] ?? new Set()

  function handleOpenChange(next: boolean) {
    if (!next) {
      setFormData({})
      setError(null)
    }
    onOpenChange(next)
  }

  function handleFieldChange(fieldName: string, value: string | number | null) {
    setFormData((prev) => ({ ...prev, [fieldName]: value }))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    const createFn = CREATE_FN[entityType]
    if (!createFn) {
      setError(`Создание для "${entityType}" не поддерживается`)
      return
    }

    // Build payload: convert empty strings to null, parse numbers
    const payload: Record<string, unknown> = {}
    for (const field of formFields) {
      const raw = formData[field.field_name]
      if (raw === undefined || raw === null || raw === "") continue

      if (isLookupField(field.field_name)) {
        payload[field.field_name] = typeof raw === "number" ? raw : Number(raw)
      } else if (field.field_type === "number") {
        payload[field.field_name] = Number(raw)
      } else {
        payload[field.field_name] = raw
      }
    }

    setSubmitting(true)
    try {
      const created = await createFn(payload)
      handleOpenChange(false)
      onCreated(created.id)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Ошибка создания записи"
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const entityLabels: Record<string, string> = {
    models: "модель",
    articles: "артикул",
    products: "товар",
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            Создать {entityLabels[entityType] ?? entityType}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-3">
          {formFields.map((field) => {
            const isRequired = requiredSet.has(field.field_name)
            const lookupTable = LOOKUP_TABLE_MAP[field.field_name]
            const lookupOptions = lookupTable ? lookupCache[lookupTable] ?? [] : []

            if (isLookupField(field.field_name)) {
              return (
                <div key={field.field_name} className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    {field.display_name}
                    {isRequired && <span className="text-destructive"> *</span>}
                  </label>
                  <Select
                    value={formData[field.field_name] != null ? String(formData[field.field_name]) : ""}
                    onValueChange={(val) =>
                      handleFieldChange(field.field_name, val === "" ? null : Number(val))
                    }
                  >
                    <SelectTrigger className="h-8 w-full text-sm">
                      <SelectValue placeholder="Выберите..." />
                    </SelectTrigger>
                    <SelectContent>
                      {lookupOptions.map((opt) => (
                        <SelectItem key={opt.id} value={String(opt.id)} className="text-sm">
                          {opt.nazvanie}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )
            }

            return (
              <div key={field.field_name} className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">
                  {field.display_name}
                  {isRequired && <span className="text-destructive"> *</span>}
                </label>
                <Input
                  type={field.field_type === "number" ? "number" : "text"}
                  value={formData[field.field_name] ?? ""}
                  onChange={(e) => handleFieldChange(field.field_name, e.target.value)}
                  required={isRequired}
                  className="h-8 text-sm"
                  placeholder={field.display_name}
                />
              </div>
            )
          })}

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <DialogFooter>
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? "Создание..." : "Создать"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
