import { ExternalLink } from "lucide-react"
import type { Atribut } from "@/lib/catalog/service"
import { AssetUploader } from "./asset-uploader"
import {
  FieldWrap,
  NumberField,
  StringSelectField,
  TextField,
  TextareaField,
  type FieldLevel,
} from "./fields"

// W6.3: универсальный контрол для рендера атрибута по его `type`.
// Заменяет fallback на TextField в TabAttributes — теперь все 10 типов из
// `AtributType` имеют свой widget. Helper text (`atribut.helper_text`)
// рендерится одинаково под любым контролом.

interface AttributeControlProps {
  atribut: Atribut
  value: unknown
  onChange: (v: unknown) => void
  readonly?: boolean
  level?: FieldLevel
}

// ─── Local helpers ─────────────────────────────────────────────────────────

function slugify(s: string): string {
  return (
    s
      .toLowerCase()
      .replace(/[^a-z0-9-]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "file"
  )
}

function extFromMime(mime: string): string {
  if (mime === "image/jpeg" || mime === "image/jpg") return "jpg"
  if (mime === "image/png") return "png"
  if (mime === "image/webp") return "webp"
  if (mime === "image/gif") return "gif"
  if (mime === "application/pdf") return "pdf"
  return "bin"
}

/** `attributes/{key}/{slug}.{ext}` — buildPath для file_url widget. */
function buildAttributeAssetPath(atributKey: string, file: File): string {
  const base = file.name.replace(/\.[^.]+$/, "")
  return `attributes/${slugify(atributKey)}/${slugify(base)}.${extFromMime(file.type)}`
}

function isValidUrl(s: string): boolean {
  if (!s) return false
  try {
    const u = new URL(s)
    return u.protocol === "http:" || u.protocol === "https:"
  } catch {
    return false
  }
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return ""
  // Принимаем как ISO (YYYY-MM-DD), так и любую парсимую дату.
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (m) return `${m[3]}.${m[2]}.${m[1]}`
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const dd = String(d.getDate()).padStart(2, "0")
  const mm = String(d.getMonth() + 1).padStart(2, "0")
  const yyyy = d.getFullYear()
  return `${dd}.${mm}.${yyyy}`
}

const EMPTY = <span className="text-stone-400 italic">не задано</span>

function HelperText({ text }: { text: string | null }) {
  if (!text) return null
  return <p className="text-[11px] text-stone-400 mt-1">{text}</p>
}

// ─── Component ─────────────────────────────────────────────────────────────

export function AttributeControl({
  atribut,
  value,
  onChange,
  readonly,
  level,
}: AttributeControlProps) {
  const { type, label, options, helper_text } = atribut

  switch (type) {
    case "text": {
      const v = (value as string | null) ?? ""
      return (
        <div>
          <TextField
            label={label}
            value={v}
            onChange={(s) => onChange(s)}
            readonly={readonly}
            level={level}
          />
          <HelperText text={helper_text} />
        </div>
      )
    }

    case "number": {
      const raw = value
      const numVal =
        typeof raw === "number"
          ? raw
          : typeof raw === "string" && raw !== "" && !Number.isNaN(Number(raw))
            ? Number(raw)
            : null
      return (
        <div>
          <NumberField
            label={label}
            value={numVal}
            onChange={(n) => onChange(n)}
            readonly={readonly}
            level={level}
          />
          <HelperText text={helper_text} />
        </div>
      )
    }

    case "textarea": {
      const v = (value as string | null) ?? ""
      return (
        <div className="col-span-2">
          <TextareaField
            label={label}
            value={v}
            onChange={(s) => onChange(s)}
            readonly={readonly}
            level={level}
            full
          />
          <HelperText text={helper_text} />
        </div>
      )
    }

    case "select": {
      const v = (value as string | null) ?? ""
      return (
        <div>
          <StringSelectField
            label={label}
            value={v}
            options={options}
            onChange={(s) => onChange(s)}
            readonly={readonly}
            level={level}
          />
          <HelperText text={helper_text} />
        </div>
      )
    }

    case "multiselect": {
      // Value хранится как `\n`-separated string. Парсинг — split('\n'),
      // обратная сериализация — join('\n').
      const raw = (value as string | null) ?? ""
      const selected = raw
        ? raw
            .split("\n")
            .map((x) => x.trim())
            .filter((x) => x.length > 0)
        : []
      const toggle = (opt: string) => {
        const next = selected.includes(opt)
          ? selected.filter((x) => x !== opt)
          : [...selected, opt]
        onChange(next.join("\n"))
      }
      return (
        <div>
          <FieldWrap label={label} level={level}>
            {readonly ? (
              <div className="px-2.5 py-1.5 text-sm text-stone-900">
                {selected.length > 0 ? selected.join(", ") : EMPTY}
              </div>
            ) : (
              <div className="flex flex-col gap-1.5">
                {options.length === 0 ? (
                  <div className="text-xs text-stone-400 italic">
                    Нет опций — добавьте в реестре атрибутов
                  </div>
                ) : (
                  options.map((o) => {
                    const active = selected.includes(o)
                    return (
                      <label
                        key={o}
                        className="flex items-center gap-2 text-sm cursor-pointer select-none"
                      >
                        <input
                          type="checkbox"
                          checked={active}
                          onChange={() => toggle(o)}
                          className="w-3.5 h-3.5 accent-stone-900"
                        />
                        <span className="text-stone-700">{o}</span>
                      </label>
                    )
                  })
                )}
              </div>
            )}
          </FieldWrap>
          <HelperText text={helper_text} />
        </div>
      )
    }

    case "pills": {
      const v = (value as string | null) ?? ""
      return (
        <div>
          <FieldWrap label={label} level={level}>
            {readonly ? (
              <div className="px-2.5 py-1.5 text-sm text-stone-900">
                {v || EMPTY}
              </div>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {options.length === 0 ? (
                  <div className="text-xs text-stone-400 italic">
                    Нет опций — добавьте в реестре атрибутов
                  </div>
                ) : (
                  options.map((o) => {
                    const active = v === o
                    return (
                      <button
                        key={o}
                        type="button"
                        onClick={() => onChange(active ? "" : o)}
                        className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                          active
                            ? "bg-stone-900 text-white border-stone-900"
                            : "bg-white border-stone-200 text-stone-600 hover:border-stone-400"
                        }`}
                      >
                        {o}
                      </button>
                    )
                  })
                )}
              </div>
            )}
          </FieldWrap>
          <HelperText text={helper_text} />
        </div>
      )
    }

    case "url": {
      const v = (value as string | null) ?? ""
      return (
        <div>
          <FieldWrap label={label} level={level}>
            {readonly ? (
              v ? (
                isValidUrl(v) ? (
                  <a
                    href={v}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 text-sm text-stone-700 hover:text-stone-900 hover:underline truncate"
                  >
                    <span className="truncate">{v}</span>
                    <ExternalLink className="w-3 h-3 shrink-0" />
                  </a>
                ) : (
                  <div className="px-2.5 py-1.5 text-sm text-stone-900 truncate">{v}</div>
                )
              ) : (
                <div className="px-2.5 py-1.5 text-sm">{EMPTY}</div>
              )
            ) : (
              <div className="relative">
                <input
                  type="url"
                  value={v}
                  onChange={(e) => onChange(e.target.value)}
                  placeholder="https://…"
                  className="w-full px-2.5 py-1.5 pr-9 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
                />
                {isValidUrl(v) && (
                  <a
                    href={v}
                    target="_blank"
                    rel="noreferrer noopener"
                    title="Открыть в новой вкладке"
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-700"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>
            )}
          </FieldWrap>
          <HelperText text={helper_text} />
        </div>
      )
    }

    case "file_url": {
      const path = (value as string | null) ?? null
      return (
        <div>
          <FieldWrap label={label} level={level}>
            <AssetUploader
              path={path}
              kind="image-or-pdf"
              buildPath={(file) => buildAttributeAssetPath(atribut.key, file)}
              onChange={(p) => onChange(p)}
              disabled={readonly}
              label={label}
            />
          </FieldWrap>
          <HelperText text={helper_text} />
        </div>
      )
    }

    case "date": {
      const v = (value as string | null) ?? ""
      return (
        <div>
          <FieldWrap label={label} level={level}>
            {readonly ? (
              <div className="px-2.5 py-1.5 text-sm text-stone-900 tabular-nums">
                {v ? formatDate(v) : EMPTY}
              </div>
            ) : (
              <input
                type="date"
                value={v}
                onChange={(e) => onChange(e.target.value)}
                className="w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
              />
            )}
          </FieldWrap>
          <HelperText text={helper_text} />
        </div>
      )
    }

    case "checkbox": {
      // Value хранится как boolean. Принимаем и "true"/"false" строки от
      // старых данных в text-колонке.
      const v =
        value === true ||
        value === "true" ||
        value === 1 ||
        value === "1"
      return (
        <div>
          <FieldWrap label={label} level={level}>
            {readonly ? (
              <div className="px-2.5 py-1.5 text-sm text-stone-900">
                {v ? "✓" : <span className="text-stone-400">—</span>}
              </div>
            ) : (
              <label className="flex items-center gap-2 px-2.5 py-1.5 text-sm cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={v}
                  onChange={(e) => onChange(e.target.checked)}
                  className="w-4 h-4 accent-stone-900"
                />
                <span className="text-stone-700">{label}</span>
              </label>
            )}
          </FieldWrap>
          <HelperText text={helper_text} />
        </div>
      )
    }

    default: {
      // Unknown type — fallback на TextField, чтобы новый тип в БД не ломал UI.
      const v = (value as string | null) ?? ""
      return (
        <div>
          <TextField
            label={label}
            value={v}
            onChange={(s) => onChange(s)}
            readonly={readonly}
            level={level}
          />
          <HelperText text={helper_text} />
        </div>
      )
    }
  }
}
