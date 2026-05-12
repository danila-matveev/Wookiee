import * as React from "react"
import { File as FileIcon, Upload, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { FieldWrap } from "./FieldWrap"

export interface FileUploadProps {
  id: string
  label?: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  labelAddon?: React.ReactNode

  value: File[] | null
  onChange: (next: File[]) => void

  /** Comma-separated MIME types or extensions. */
  accept?: string
  multiple?: boolean
  /** Per-file max size in bytes. Reject + show error if exceeded. */
  maxSize?: number
  disabled?: boolean
  className?: string

  /** Helper text rendered inside the drop zone (default: PNG, JPG, PDF до 10MB). */
  description?: React.ReactNode
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

export function FileUpload({
  id,
  label,
  hint,
  error,
  required,
  labelAddon,
  value,
  onChange,
  accept,
  multiple,
  maxSize,
  disabled,
  className,
  description,
}: FileUploadProps) {
  const [drag, setDrag] = React.useState(false)
  const [localError, setLocalError] = React.useState<string | null>(null)
  const inputRef = React.useRef<HTMLInputElement | null>(null)

  const files = value ?? []

  const acceptFiles = (incoming: File[]) => {
    setLocalError(null)
    if (maxSize) {
      const oversized = incoming.find((f) => f.size > maxSize)
      if (oversized) {
        setLocalError(
          `Файл «${oversized.name}» больше ${formatBytes(maxSize)}`,
        )
        return
      }
    }
    const next = multiple ? [...files, ...incoming] : incoming.slice(0, 1)
    onChange(next)
  }

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files
    if (!list) return
    acceptFiles(Array.from(list))
    // reset input value so the same file can be re-selected
    e.target.value = ""
  }

  const remove = (idx: number) => {
    onChange(files.filter((_, i) => i !== idx))
  }

  const displayedError = error ?? localError

  return (
    <FieldWrap
      id={id}
      label={label}
      hint={hint}
      error={displayedError ?? undefined}
      required={required}
      labelAddon={labelAddon}
      className={className}
    >
      <label
        htmlFor={id}
        onDragOver={(e) => {
          if (disabled) return
          e.preventDefault()
          setDrag(true)
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          if (disabled) return
          e.preventDefault()
          setDrag(false)
          acceptFiles(Array.from(e.dataTransfer.files))
        }}
        className={cn(
          "block rounded-lg border-2 border-dashed transition-colors p-5 text-center cursor-pointer",
          drag
            ? "border-accent bg-accent-soft"
            : "border-[var(--color-border-strong)] hover:border-accent hover:bg-surface-muted",
          displayedError && "border-[var(--color-danger)]",
          disabled && "opacity-50 cursor-not-allowed pointer-events-none",
        )}
      >
        <Upload className="w-5 h-5 mx-auto mb-1.5 text-muted" aria-hidden />
        <div className="text-sm text-secondary">
          Перетащите файлы или <span className="text-accent underline">выберите</span>
        </div>
        <div className="text-[10px] mt-1 text-muted">
          {description ??
            (maxSize
              ? `Максимум ${formatBytes(maxSize)} на файл`
              : "PNG, JPG, PDF до 10MB")}
        </div>
        <input
          ref={inputRef}
          id={id}
          type="file"
          accept={accept}
          multiple={multiple}
          disabled={disabled}
          onChange={onInputChange}
          className="sr-only"
        />
      </label>

      {files.length > 0 && (
        <div className="space-y-1 mt-2">
          {files.map((f, i) => (
            <div
              key={`${f.name}-${i}`}
              className="flex items-center justify-between px-2 py-1 rounded text-xs bg-surface-muted"
            >
              <span className="flex items-center gap-1.5 text-secondary min-w-0">
                <FileIcon className="w-3 h-3 shrink-0" aria-hidden />
                <span className="font-mono text-[11px] truncate">{f.name}</span>
                <span className="text-muted tabular-nums shrink-0">
                  {formatBytes(f.size)}
                </span>
              </span>
              <button
                type="button"
                disabled={disabled}
                onClick={() => remove(i)}
                aria-label={`Удалить ${f.name}`}
                className="p-0.5 rounded hover:bg-surface text-muted hover:text-primary shrink-0"
              >
                <X className="w-3 h-3" aria-hidden />
              </button>
            </div>
          ))}
        </div>
      )}
    </FieldWrap>
  )
}
