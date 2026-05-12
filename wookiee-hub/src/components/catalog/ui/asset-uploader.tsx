import { useEffect, useRef, useState } from "react"
import { Upload, Trash2, FileText, Loader2 } from "lucide-react"
import {
  deleteCatalogAsset,
  getCatalogAssetSignedUrl,
  uploadCatalogAsset,
  validateCatalogAsset,
} from "@/lib/catalog/service"

type AssetKind = "image" | "pdf" | "image-or-pdf"

interface BaseUploaderProps {
  /** Текущий path в bucket (или null, если файла нет). */
  path: string | null | undefined
  /** Тип принимаемых файлов. */
  kind: AssetKind
  /** Резолвится в path внутри bucket. Вызывается ДО `onChange(path)`. */
  buildPath: (file: File) => string
  /** Callback после upload — родитель должен записать `path` в БД. */
  onChange: (path: string | null) => void | Promise<void>
  /** disabled — для read-only режима карточки. */
  disabled?: boolean
  /** label под превью (для accessibility и заглушек). */
  label?: string
}

/**
 * Загружает изображение или PDF в Supabase Storage bucket `catalog-assets`,
 * рендерит превью (для image) или ссылку «открыть» (для pdf) и кнопку удалить.
 *
 * Превью получается через signed URL (TTL 1h, refresh при mount/path change).
 * Drag-drop работает: dropzone подсвечивается на dragOver.
 *
 * Что НЕ делает: не управляет состоянием БД — родитель должен записать
 * новый path в свою таблицу после `onChange(path)`.
 */
export function AssetUploader({
  path,
  kind,
  buildPath,
  onChange,
  disabled,
  label,
}: BaseUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [signedUrl, setSignedUrl] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  useEffect(() => {
    let cancelled = false
    if (!path) {
      setSignedUrl(null)
      return
    }
    void getCatalogAssetSignedUrl(path)
      .then((url) => {
        if (!cancelled) setSignedUrl(url)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      cancelled = true
    }
  }, [path])

  const accept =
    kind === "image"
      ? "image/png,image/jpeg,image/webp,image/gif"
      : kind === "pdf"
        ? "application/pdf"
        : "image/png,image/jpeg,image/webp,image/gif,application/pdf"

  async function handleFile(file: File) {
    setError(null)
    const validation = validateCatalogAsset(file, kind)
    if (!validation.ok) {
      setError(validation.reason)
      return
    }
    setBusy(true)
    try {
      const newPath = buildPath(file)
      await uploadCatalogAsset(newPath, file, { contentType: file.type })
      await onChange(newPath)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    if (!path) return
    setBusy(true)
    setError(null)
    try {
      await deleteCatalogAsset(path)
      await onChange(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const isPdf = path?.toLowerCase().endsWith(".pdf") ?? false
  const showImagePreview = path && !isPdf && signedUrl
  const showPdfPreview = path && isPdf

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => {
          if (disabled) return
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          if (disabled) return
          const file = e.dataTransfer.files?.[0]
          if (file) void handleFile(file)
        }}
        className={`relative border-2 border-dashed rounded-lg transition-colors ${
          dragOver ? "border-stone-900 bg-stone-50" : "border-stone-300 bg-stone-50/40"
        } ${disabled ? "opacity-50" : ""}`}
      >
        {showImagePreview ? (
          <div className="relative p-2">
            <img
              src={signedUrl}
              alt={label ?? "Изображение"}
              className="w-full max-h-48 object-contain rounded"
            />
            {!disabled && (
              <button
                type="button"
                onClick={handleDelete}
                disabled={busy}
                className="absolute top-3 right-3 p-1.5 bg-white border border-stone-200 rounded shadow-sm hover:bg-stone-50 disabled:opacity-50"
                title="Удалить"
              >
                <Trash2 className="w-3.5 h-3.5 text-stone-600" />
              </button>
            )}
          </div>
        ) : showPdfPreview ? (
          <div className="flex items-center justify-between gap-3 p-3">
            <a
              href={signedUrl ?? "#"}
              target="_blank"
              rel="noreferrer noopener"
              className="flex items-center gap-2 text-sm text-stone-700 hover:underline truncate"
            >
              <FileText className="w-4 h-4 shrink-0" />
              <span className="truncate">{path?.split("/").pop()}</span>
            </a>
            {!disabled && (
              <button
                type="button"
                onClick={handleDelete}
                disabled={busy}
                className="p-1.5 hover:bg-stone-100 rounded disabled:opacity-50 shrink-0"
                title="Удалить"
              >
                <Trash2 className="w-3.5 h-3.5 text-stone-600" />
              </button>
            )}
          </div>
        ) : (
          <button
            type="button"
            disabled={disabled || busy}
            onClick={() => inputRef.current?.click()}
            className="w-full flex flex-col items-center justify-center gap-1.5 px-4 py-8 text-stone-600 hover:bg-stone-100/60 disabled:cursor-not-allowed"
          >
            {busy ? (
              <Loader2 className="w-6 h-6 animate-spin text-stone-400" />
            ) : (
              <Upload className="w-6 h-6 text-stone-400" />
            )}
            <div className="text-xs">
              {busy ? "Загружаем…" : "Перетащите файл или нажмите"}
            </div>
            <div className="text-[11px] text-stone-400">
              {kind === "pdf"
                ? "PDF, до 10 МБ"
                : kind === "image"
                  ? "PNG / JPG / WebP / GIF, до 10 МБ"
                  : "PNG / JPG / WebP / GIF / PDF, до 10 МБ"}
            </div>
          </button>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void handleFile(file)
            e.target.value = ""
          }}
        />
      </div>
      {path && !disabled && (showImagePreview || showPdfPreview) && (
        <button
          type="button"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
          className="text-xs text-stone-500 hover:text-stone-700 underline disabled:opacity-50"
        >
          Заменить
        </button>
      )}
      {error && <div className="text-xs text-rose-600">{error}</div>}
    </div>
  )
}
