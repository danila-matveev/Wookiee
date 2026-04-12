import { useState } from "react"
import { Lock, ArrowUpRight, CalendarIcon, Link } from "lucide-react"
import { format, parseISO } from "date-fns"
import { ru } from "date-fns/locale"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"
import { Calendar } from "@/components/ui/calendar"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { IMMUTABLE_FIELDS, COMPUTED_FIELD_PATTERN, ENTITY_TITLE_FIELD } from "./types"
import { useMatrixStore } from "@/stores/matrix-store"
import type { PanelFieldRowProps, MatrixEntity } from "./types"

interface PanelFieldRowExtendedProps extends PanelFieldRowProps {
  inherited?: boolean
  parentEntityType?: string | null
  parentEntityId?: number | null
  parentData?: Record<string, unknown> | null
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—"
  if (typeof value === "boolean") return value ? "Да" : "Нет"
  return String(value)
}

function formatDateDisplay(value: unknown): string {
  if (!value) return "Выберите дату"
  try {
    const dateStr = String(value)
    // Accept ISO strings or date-only strings
    const parsed = dateStr.includes("T") ? parseISO(dateStr) : new Date(dateStr)
    if (isNaN(parsed.getTime())) return String(value)
    return format(parsed, "d MMM yyyy", { locale: ru })
  } catch {
    return String(value)
  }
}

function parseEditDate(value: unknown): Date | undefined {
  if (!value) return undefined
  try {
    const dateStr = String(value)
    const parsed = dateStr.includes("T") ? parseISO(dateStr) : new Date(dateStr)
    return isNaN(parsed.getTime()) ? undefined : parsed
  } catch {
    return undefined
  }
}

// Key fields to show in the inherited parent popover preview
const PARENT_PREVIEW_FIELDS: Record<string, string[]> = {
  models: ["kod", "kategoriya_name", "kollekciya_name", "fabrika_name"],
  articles: ["artikul", "model_name", "cvet_name", "status_name"],
}

// Fields where editing requires extra care — shown with subtle amber tint
const SENSITIVE_FIELDS = new Set(["kod", "artikul", "barkod_perehod", "tnved"])

export function PanelFieldRow({
  def,
  value,
  editValue,
  isEditing,
  lookupOptions,
  onChange,
  inherited = false,
  parentEntityType,
  parentEntityId,
  parentData,
}: PanelFieldRowExtendedProps) {
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)
  const [dateOpen, setDateOpen] = useState(false)

  // Skip computed _name fields — they are shown via the parent field row
  if (COMPUTED_FIELD_PATTERN.test(def.field_name)) return null

  const isImmutable = IMMUTABLE_FIELDS.has(def.field_name)
  const isSystemField = def.is_system
  const displayValue = formatValue(value)
  const isSensitive = SENSITIVE_FIELDS.has(def.field_name)

  // ── Read-only display node ────────────────────────────────────────────────
  const lockIcon =
    isImmutable || (isSystemField && isEditing) ? (
      <Lock className="h-3 w-3 text-muted-foreground/50 shrink-0 ml-1" />
    ) : null

  const readValueNode = (
    <span
      className={cn(
        "flex-1 text-sm text-foreground break-words",
        isImmutable && "text-muted-foreground/80",
      )}
    >
      {displayValue}
    </span>
  )

  // ── Edit input node ───────────────────────────────────────────────────────
  function renderEditInput() {
    // Immutable or system fields → read-only with lock
    if (isImmutable || isSystemField) {
      return (
        <div className="flex items-center flex-1 min-w-0">
          <span className="flex-1 text-sm text-muted-foreground/70 break-words italic">
            {displayValue}
          </span>
          <Lock className="h-3 w-3 text-muted-foreground/40 shrink-0 ml-1" title="Системное поле" />
        </div>
      )
    }

    const sensitiveClass = isSensitive
      ? "border-amber-400/60 focus-visible:ring-amber-400/40 bg-amber-50/30 dark:bg-amber-950/20"
      : ""

    switch (def.field_type) {
      case "text":
      case "url":
        return (
          <div className="flex items-center flex-1 min-w-0 gap-1">
            <Input
              value={editValue != null ? String(editValue) : ""}
              onChange={(e) => onChange(def.field_name, e.target.value)}
              className={cn("h-7 text-xs flex-1", sensitiveClass)}
              placeholder={def.display_name}
            />
            {def.field_type === "url" && editValue && (
              <a
                href={String(editValue)}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 text-muted-foreground hover:text-foreground"
                tabIndex={-1}
              >
                <Link className="h-3.5 w-3.5" />
              </a>
            )}
          </div>
        )

      case "number":
        return (
          <Input
            type="number"
            value={editValue != null ? String(editValue) : ""}
            onChange={(e) => {
              const raw = e.target.value
              onChange(def.field_name, raw === "" ? null : Number(raw))
            }}
            className={cn("h-7 text-xs flex-1", sensitiveClass)}
            placeholder={def.display_name}
          />
        )

      case "select":
        return (
          <Select
            value={editValue != null ? String(editValue) : ""}
            onValueChange={(val) => onChange(def.field_name, val === "" ? null : Number(val))}
          >
            <SelectTrigger className={cn("h-7 text-xs flex-1", sensitiveClass)}>
              <SelectValue placeholder="Выберите..." />
            </SelectTrigger>
            <SelectContent>
              {(lookupOptions ?? []).map((opt) => (
                <SelectItem key={opt.id} value={String(opt.id)} className="text-xs">
                  {opt.nazvanie}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )

      case "textarea":
        return (
          <Textarea
            value={editValue != null ? String(editValue) : ""}
            onChange={(e) => onChange(def.field_name, e.target.value)}
            rows={3}
            className={cn("text-xs flex-1 resize-none", sensitiveClass)}
            placeholder={def.display_name}
          />
        )

      case "checkbox":
        return (
          <div className="flex items-center flex-1">
            <Checkbox
              checked={!!editValue}
              onCheckedChange={(checked) => onChange(def.field_name, checked === true)}
            />
          </div>
        )

      case "date": {
        const selectedDate = parseEditDate(editValue)
        return (
          <Popover open={dateOpen} onOpenChange={setDateOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className={cn(
                  "h-7 text-xs flex-1 justify-start gap-1.5",
                  !editValue && "text-muted-foreground",
                  sensitiveClass,
                )}
              >
                <CalendarIcon className="h-3.5 w-3.5 shrink-0" />
                {formatDateDisplay(editValue)}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar
                mode="single"
                selected={selectedDate}
                onSelect={(date) => {
                  onChange(def.field_name, date ? format(date, "yyyy-MM-dd") : null)
                  setDateOpen(false)
                }}
                locale={ru}
                initialFocus
              />
            </PopoverContent>
          </Popover>
        )
      }

      default:
        // Fallback: text input
        return (
          <Input
            value={editValue != null ? String(editValue) : ""}
            onChange={(e) => onChange(def.field_name, e.target.value)}
            className={cn("h-7 text-xs flex-1", sensitiveClass)}
            placeholder={def.display_name}
          />
        )
    }
  }

  // ── Row wrapper ───────────────────────────────────────────────────────────
  const content = (
    <div
      className={cn(
        "flex items-start gap-2 rounded px-2 py-1.5 text-sm group",
        "hover:bg-accent/20 transition-colors",
        inherited && "bg-muted/30 hover:bg-muted/50",
        isEditing && isSensitive && !isImmutable && !isSystemField && "bg-amber-50/20 dark:bg-amber-950/10",
      )}
    >
      {/* Label */}
      <span className="w-[44%] shrink-0 text-xs text-muted-foreground pt-0.5 leading-relaxed truncate">
        {def.display_name}
        {inherited && (
          <ArrowUpRight className="inline-block h-3 w-3 ml-0.5 text-muted-foreground/50" />
        )}
      </span>

      {/* Value / Input */}
      {isEditing && !inherited ? (
        renderEditInput()
      ) : (
        <div className="flex items-center flex-1 min-w-0">
          {readValueNode}
          {lockIcon}
        </div>
      )}
    </div>
  )

  // ── Inherited field with popover ──────────────────────────────────────────
  if (inherited && parentEntityType && parentEntityId != null) {
    const previewFields = PARENT_PREVIEW_FIELDS[parentEntityType] ?? []
    const parentTitleField = ENTITY_TITLE_FIELD[parentEntityType]
    const parentTitle = parentData ? formatValue(parentData[parentTitleField]) : "—"

    return (
      <Popover>
        <PopoverTrigger render={<div className="cursor-pointer">{content}</div>} />
        <PopoverContent side="left" sideOffset={8} className="w-64 p-3">
          {/* Mini-preview of parent entity */}
          <div className="space-y-2">
            <div className="font-medium text-sm border-b border-border pb-1.5 mb-1">
              {parentTitle}
            </div>
            {previewFields.map((fieldKey) => (
              <div key={fieldKey} className="flex gap-2 text-xs">
                <span className="text-muted-foreground w-[45%] shrink-0 truncate">
                  {fieldKey.replace(/_name$/, "").replace(/_/g, " ")}
                </span>
                <span className="text-foreground">
                  {parentData ? formatValue(parentData[fieldKey]) : "—"}
                </span>
              </div>
            ))}
            <Button
              variant="ghost"
              size="sm"
              className="w-full h-7 text-xs mt-1 gap-1"
              onClick={() => {
                openDetailPanel(parentEntityId, parentEntityType as MatrixEntity)
              }}
            >
              <ArrowUpRight className="h-3.5 w-3.5" />
              Перейти к {parentEntityType === "models" ? "модели" : "артикулу"}
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    )
  }

  return content
}
