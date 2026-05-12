// W7.2 — CSV import wizard for catalog entities (modeli / artikuly / tovary).
//
// Trёhshagovyy wizard: pick → preview → confirm.
//
// Шаг 1 (pick): выбрать сущность + загрузить CSV (drag-drop / file picker).
//   • Кнопка «Скачать шаблон CSV» генерирует пустой CSV с правильными
//     заголовками через `Papa.unparse`.
// Шаг 2 (preview): сопоставить колонки CSV с колонками таблицы.
//   • Если имена совпали — автоматически.
//   • Несовпавшие — селекты для маппинга / skip.
//   • Показываем первые 10 строк.
// Шаг 3 (confirm): клиентская валидация + dry-run + commit.
//   • Required fields filled, numeric fields parse as Number.
//   • Unique-check (kod / artikul / barkod) — single SELECT count.
//   • Insert чанками по 100 строк через `supabase.from(...).insert(rows)`.
//
// SUPABASE INSERT — напрямую через `supabase.from('<table>').insert(rows)`.
// Никаких RPC `bulkInsert*` — их в БД нет, упоминание в плане ошибочное.

import { useCallback, useMemo, useRef, useState } from "react"
import Papa from "papaparse"
import {
  Upload,
  Download,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  XCircle,
  Loader2,
  FileText,
  Trash2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { supabase } from "@/lib/supabase"
import { PageShell } from "./references/_shared"

// ─── Entity schemas ────────────────────────────────────────────────────────
//
// Каждая сущность описывает:
//   • table — имя таблицы в Postgres,
//   • label — человекочитаемое имя,
//   • columns — список колонок шаблона (key + type + required),
//   • uniqueKey — поле, по которому проверяем уникальность перед insert.

type FieldType = "string" | "number" | "integer"

interface ImportField {
  key: string
  label: string
  type: FieldType
  required: boolean
  /** Иммутабельный — будет уникальным ключом для check'а перед insert. */
  unique?: boolean
}

interface ImportEntity {
  value: string
  table: string
  label: string
  fields: ImportField[]
  /** Поле для uniqueness pre-check (kod / artikul / barkod). */
  uniqueKey: string
}

const ENTITIES: ImportEntity[] = [
  {
    value: "modeli",
    table: "modeli_osnova",
    label: "Модели (modeli_osnova)",
    uniqueKey: "kod",
    fields: [
      { key: "kod",                label: "Код модели",     type: "string",  required: true,  unique: true },
      { key: "brand_id",           label: "Бренд",          type: "integer", required: false },
      { key: "kategoriya_id",      label: "Категория",      type: "integer", required: false },
      { key: "kollekciya_id",      label: "Коллекция",      type: "integer", required: false },
      { key: "tip_kollekcii_id",   label: "Тип коллекции",  type: "integer", required: false },
      { key: "fabrika_id",         label: "Производитель",  type: "integer", required: false },
      { key: "importer_id",        label: "Импортер",       type: "integer", required: false },
      { key: "status_id",          label: "Статус",         type: "integer", required: false },
    ],
  },
  {
    value: "artikuly",
    table: "artikuly",
    label: "Артикулы (artikuly)",
    uniqueKey: "artikul",
    fields: [
      { key: "model_id",  label: "Модель",  type: "integer", required: true },
      { key: "cvet_id",   label: "Цвет",    type: "integer", required: false },
      { key: "status_id", label: "Статус",  type: "integer", required: false },
      { key: "artikul",   label: "Артикул", type: "string",  required: true, unique: true },
    ],
  },
  {
    value: "tovary",
    table: "tovary",
    label: "SKU (tovary)",
    uniqueKey: "barkod",
    fields: [
      { key: "artikul_id",       label: "Артикул",        type: "integer", required: true },
      { key: "razmer_id",        label: "Размер",         type: "integer", required: false },
      { key: "barkod",           label: "Баркод",         type: "string",  required: true, unique: true },
      { key: "status_id",        label: "Статус",         type: "integer", required: false },
      { key: "status_ozon_id",   label: "Статус OZON",    type: "integer", required: false },
      { key: "status_sayt_id",   label: "Статус Сайт",    type: "integer", required: false },
      { key: "status_lamoda_id", label: "Статус Lamoda",  type: "integer", required: false },
    ],
  },
]

const ENTITY_MAP: Record<string, ImportEntity> = Object.fromEntries(
  ENTITIES.map((e) => [e.value, e]),
)

// ─── Types ─────────────────────────────────────────────────────────────────

type Step = "pick" | "preview" | "confirm"

type RawRow = Record<string, string>

/** Маппинг: имя_колонки_таблицы → имя_колонки_CSV (или null = skip). */
type Mapping = Record<string, string | null>

interface ValidatedRow {
  idx: number
  raw: RawRow
  payload: Record<string, string | number | null>
  errors: string[]
}

// ─── Component ─────────────────────────────────────────────────────────────

export function CatalogImportPage() {
  const [step, setStep] = useState<Step>("pick")
  const [entityValue, setEntityValue] = useState<string>(ENTITIES[0].value)
  const [fileName, setFileName] = useState<string>("")
  const [rows, setRows] = useState<RawRow[]>([])
  const [headers, setHeaders] = useState<string[]>([])
  const [parseError, setParseError] = useState<string | null>(null)
  const [mapping, setMapping] = useState<Mapping>({})
  const [validation, setValidation] = useState<{
    valid: ValidatedRow[]
    invalid: ValidatedRow[]
  } | null>(null)
  const [validating, setValidating] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{
    inserted: number
    error: string | null
  } | null>(null)

  const entity = ENTITY_MAP[entityValue]

  const reset = useCallback(() => {
    setStep("pick")
    setFileName("")
    setRows([])
    setHeaders([])
    setParseError(null)
    setMapping({})
    setValidation(null)
    setImportResult(null)
  }, [])

  // ─── Step 1: pick ──────────────────────────────────────────────────────

  const downloadTemplate = useCallback(() => {
    const csv = Papa.unparse({
      fields: entity.fields.map((f) => f.key),
      data: [],
    })
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${entity.table}_template.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, [entity])

  const handleFile = useCallback(
    (file: File) => {
      setParseError(null)
      setFileName(file.name)
      Papa.parse<RawRow>(file, {
        header: true,
        skipEmptyLines: true,
        transformHeader: (h) => h.trim(),
        complete: (results) => {
          if (results.errors.length > 0) {
            setParseError(
              `Ошибка парсинга CSV: ${results.errors[0].message} (строка ${results.errors[0].row ?? "?"})`,
            )
            return
          }
          const data = results.data as RawRow[]
          const csvHeaders =
            results.meta.fields ??
            (data.length > 0 ? Object.keys(data[0]) : [])
          if (csvHeaders.length === 0) {
            setParseError("CSV без заголовков — заголовки обязательны.")
            return
          }
          setRows(data)
          setHeaders(csvHeaders)
          // Авто-маппинг: если имя колонки таблицы есть в CSV — подставляем.
          const autoMap: Mapping = {}
          for (const f of entity.fields) {
            autoMap[f.key] = csvHeaders.includes(f.key) ? f.key : null
          }
          setMapping(autoMap)
          setStep("preview")
        },
        error: (err) => {
          setParseError(`Ошибка чтения файла: ${err.message}`)
        },
      })
    },
    [entity],
  )

  // ─── Step 2: preview / mapping ─────────────────────────────────────────

  const updateMapping = (tableKey: string, csvKey: string) => {
    setMapping((prev) => ({ ...prev, [tableKey]: csvKey === "" ? null : csvKey }))
  }

  // ─── Step 3: validation + commit ───────────────────────────────────────

  /**
   * Клиентская валидация всех строк CSV:
   *   1. Required-поля заполнены.
   *   2. Числовые поля парсятся через Number (NaN → error).
   *   3. Уникальный ключ существующих записей в БД → проверка через
   *      single SELECT с фильтром `IN (...)`.
   *
   * Возвращает разделённый список { valid, invalid }.
   */
  const validate = useCallback(async () => {
    setValidating(true)
    try {
      const out: ValidatedRow[] = []
      const uniqueField = entity.fields.find((f) => f.unique)
      const uniqueValues: string[] = []

      for (let i = 0; i < rows.length; i++) {
        const raw = rows[i]
        const errors: string[] = []
        const payload: Record<string, string | number | null> = {}

        for (const field of entity.fields) {
          const csvCol = mapping[field.key]
          const rawValue = csvCol ? (raw[csvCol] ?? "").trim() : ""

          // Required check
          if (field.required && !rawValue) {
            errors.push(`«${field.label}» обязательно`)
            payload[field.key] = null
            continue
          }

          // Empty optional → null
          if (!rawValue) {
            payload[field.key] = null
            continue
          }

          // Type coercion
          if (field.type === "integer" || field.type === "number") {
            const n = Number(rawValue)
            if (!Number.isFinite(n)) {
              errors.push(`«${field.label}» — не число: «${rawValue}»`)
              payload[field.key] = null
              continue
            }
            if (field.type === "integer" && !Number.isInteger(n)) {
              errors.push(`«${field.label}» — не целое число: «${rawValue}»`)
              payload[field.key] = null
              continue
            }
            payload[field.key] = n
          } else {
            payload[field.key] = rawValue
          }
        }

        // Collect unique values for batch DB-check
        if (uniqueField) {
          const uVal = payload[uniqueField.key]
          if (typeof uVal === "string" && uVal.length > 0) {
            uniqueValues.push(uVal)
          } else if (typeof uVal === "number") {
            uniqueValues.push(String(uVal))
          }
        }

        out.push({ idx: i, raw, payload, errors })
      }

      // Уникальность — один батч-запрос, фильтр `IN (uniqueValues)`.
      if (uniqueField && uniqueValues.length > 0) {
        const { data: existing, error } = await supabase
          .from(entity.table)
          .select(uniqueField.key)
          .in(uniqueField.key, uniqueValues)

        if (error) {
          // Если справочник пустой / RLS-проблема — не блокируем, но в каждую
          // строку добавляем warning.
          for (const r of out) {
            r.errors.push(`Не удалось проверить уникальность: ${error.message}`)
          }
        } else {
          const existingRows =
            (existing ?? []) as unknown as Record<string, unknown>[]
          const existingSet = new Set(
            existingRows.map((row) => String(row[uniqueField.key])),
          )
          for (const r of out) {
            const uVal = r.payload[uniqueField.key]
            if (uVal != null && existingSet.has(String(uVal))) {
              r.errors.push(
                `«${uniqueField.label}» уже существует в БД: «${uVal}»`,
              )
            }
          }
        }

        // In-CSV duplicates check
        const seenInCsv = new Map<string, number>()
        for (const r of out) {
          const uVal = r.payload[uniqueField.key]
          if (uVal == null) continue
          const key = String(uVal)
          const prevIdx = seenInCsv.get(key)
          if (prevIdx !== undefined) {
            r.errors.push(
              `Дубликат «${uniqueField.label}» в CSV (уже встречалось в строке ${prevIdx + 1})`,
            )
          } else {
            seenInCsv.set(key, r.idx)
          }
        }
      }

      const valid = out.filter((r) => r.errors.length === 0)
      const invalid = out.filter((r) => r.errors.length > 0)
      setValidation({ valid, invalid })
      setStep("confirm")
    } finally {
      setValidating(false)
    }
  }, [rows, mapping, entity])

  const doImport = useCallback(async () => {
    if (!validation) return
    setImporting(true)
    setImportResult(null)
    try {
      const CHUNK = 100
      const payloads = validation.valid.map((r) => {
        // Убираем null-значения для required-полей — не должны быть здесь,
        // но на всякий случай. Также для optional-null оставляем null —
        // супабейс поймёт это как «не задавать», и default-ы сработают.
        const clean: Record<string, string | number | null> = {}
        for (const k of Object.keys(r.payload)) {
          clean[k] = r.payload[k]
        }
        return clean
      })

      let inserted = 0
      for (let i = 0; i < payloads.length; i += CHUNK) {
        const chunk = payloads.slice(i, i + CHUNK)
        const { error } = await supabase.from(entity.table).insert(chunk)
        if (error) {
          setImportResult({
            inserted,
            error: `Ошибка на чанке ${i / CHUNK + 1}: ${error.message}`,
          })
          return
        }
        inserted += chunk.length
      }

      setImportResult({ inserted, error: null })
    } finally {
      setImporting(false)
    }
  }, [validation, entity])

  // ─── Render ────────────────────────────────────────────────────────────

  return (
    <PageShell>
      <Header step={step} />

      {step === "pick" && (
        <PickStep
          entityValue={entityValue}
          onEntityChange={setEntityValue}
          onDownloadTemplate={downloadTemplate}
          onFile={handleFile}
          parseError={parseError}
          fileName={fileName}
        />
      )}

      {step === "preview" && (
        <PreviewStep
          entity={entity}
          headers={headers}
          rows={rows}
          mapping={mapping}
          onUpdateMapping={updateMapping}
          onBack={() => {
            setStep("pick")
            setRows([])
            setHeaders([])
            setMapping({})
          }}
          onNext={() => void validate()}
          validating={validating}
        />
      )}

      {step === "confirm" && validation && (
        <ConfirmStep
          entity={entity}
          mapping={mapping}
          validation={validation}
          importing={importing}
          importResult={importResult}
          onBack={() => {
            setStep("preview")
            setImportResult(null)
          }}
          onImport={() => void doImport()}
          onReset={reset}
        />
      )}
    </PageShell>
  )
}

// ─── Header (wizard breadcrumbs) ───────────────────────────────────────────

function Header({ step }: { step: Step }) {
  const items: { value: Step; label: string }[] = [
    { value: "pick", label: "1. Файл" },
    { value: "preview", label: "2. Маппинг" },
    { value: "confirm", label: "3. Импорт" },
  ]
  const idx = items.findIndex((i) => i.value === step)
  return (
    <div className="mb-6">
      <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1">
        Каталог · Импорт
      </div>
      <h1
        className="text-3xl text-stone-900 italic mb-4"
        style={{ fontFamily: "'Instrument Serif', ui-serif, Georgia, serif" }}
      >
        Импорт данных из CSV
      </h1>
      <div className="flex items-center gap-2 text-xs">
        {items.map((it, i) => {
          const active = i === idx
          const done = i < idx
          return (
            <div key={it.value} className="flex items-center gap-2">
              <span
                className={cn(
                  "px-2 py-1 rounded-md border",
                  active && "bg-stone-900 text-white border-stone-900",
                  done && "bg-stone-100 text-stone-700 border-stone-200",
                  !active && !done && "bg-white text-stone-400 border-stone-200",
                )}
              >
                {it.label}
              </span>
              {i < items.length - 1 && (
                <span className="text-stone-300">→</span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Step 1: Pick ──────────────────────────────────────────────────────────

interface PickStepProps {
  entityValue: string
  onEntityChange: (v: string) => void
  onDownloadTemplate: () => void
  onFile: (file: File) => void
  parseError: string | null
  fileName: string
}

function PickStep({
  entityValue,
  onEntityChange,
  onDownloadTemplate,
  onFile,
  parseError,
  fileName,
}: PickStepProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) onFile(file)
  }

  return (
    <div className="space-y-5 max-w-3xl">
      {/* Entity picker */}
      <div>
        <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">
          Что импортируем?
        </label>
        <select
          value={entityValue}
          onChange={(e) => onEntityChange(e.target.value)}
          className="w-full max-w-md px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
        >
          {ENTITIES.map((e) => (
            <option key={e.value} value={e.value}>
              {e.label}
            </option>
          ))}
        </select>
      </div>

      {/* Template download */}
      <div>
        <button
          type="button"
          onClick={onDownloadTemplate}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-xs text-stone-700 border border-stone-200 rounded-md bg-white hover:bg-stone-50 transition-colors"
        >
          <Download className="w-3.5 h-3.5" />
          Скачать шаблон CSV
        </button>
        <p className="text-[11px] text-stone-400 mt-1">
          В шаблоне — все колонки таблицы без данных. UTF-8, разделитель «,».
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors",
          dragging
            ? "border-stone-900 bg-stone-50"
            : "border-stone-300 bg-white hover:bg-stone-50",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) onFile(file)
            e.target.value = ""
          }}
        />
        <Upload className="w-8 h-8 text-stone-400 mx-auto mb-2" />
        <div className="text-sm text-stone-700 font-medium">
          {fileName ? fileName : "Перетащите CSV сюда или нажмите, чтобы выбрать"}
        </div>
        <div className="text-[11px] text-stone-400 mt-1">
          Папарсе разберёт файл, дальше — маппинг колонок.
        </div>
      </div>

      {parseError && (
        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {parseError}
        </div>
      )}
    </div>
  )
}

// ─── Step 2: Preview ───────────────────────────────────────────────────────

interface PreviewStepProps {
  entity: ImportEntity
  headers: string[]
  rows: RawRow[]
  mapping: Mapping
  onUpdateMapping: (tableKey: string, csvKey: string) => void
  onBack: () => void
  onNext: () => void
  validating: boolean
}

function PreviewStep({
  entity,
  headers,
  rows,
  mapping,
  onUpdateMapping,
  onBack,
  onNext,
  validating,
}: PreviewStepProps) {
  const preview = rows.slice(0, 10)
  const mappedCount = entity.fields.filter((f) => mapping[f.key]).length
  const requiredMissing = entity.fields.filter(
    (f) => f.required && !mapping[f.key],
  )

  return (
    <div className="space-y-5">
      <div className="bg-white border border-stone-200 rounded-lg p-4">
        <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-2">
          Маппинг колонок — {entity.label}
        </div>
        <p className="text-xs text-stone-500 mb-3">
          Сопоставьте колонки таблицы с колонками вашего CSV. Совпадающие
          имена подставлены автоматически.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {entity.fields.map((f) => (
            <div key={f.key} className="flex items-center gap-2">
              <div className="w-1/2 text-xs text-stone-700">
                <span className="font-mono">{f.key}</span>
                {f.required && <span className="text-red-500 ml-0.5">*</span>}
                <span className="text-stone-400 ml-1">({f.type})</span>
              </div>
              <select
                value={mapping[f.key] ?? ""}
                onChange={(e) => onUpdateMapping(f.key, e.target.value)}
                className="w-1/2 px-2 py-1 text-xs border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
              >
                <option value="">— пропустить —</option>
                {headers.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
        <div className="mt-3 text-[11px] text-stone-500">
          Сопоставлено: {mappedCount}/{entity.fields.length}
          {requiredMissing.length > 0 && (
            <span className="text-red-600 ml-3">
              ⚠ Не заполнены обязательные:{" "}
              {requiredMissing.map((f) => f.key).join(", ")}
            </span>
          )}
        </div>
      </div>

      {/* Preview table — first 10 rows */}
      <div>
        <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-2">
          Предпросмотр (первые 10 строк из {rows.length})
        </div>
        <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-stone-50/80 border-b border-stone-200">
              <tr className="text-left text-[10px] uppercase tracking-wider text-stone-500">
                <th className="px-2 py-2 font-medium w-10">#</th>
                {headers.map((h) => (
                  <th key={h} className="px-2 py-2 font-medium font-mono">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.map((r, i) => (
                <tr key={i} className="border-b border-stone-100 last:border-0">
                  <td className="px-2 py-1.5 text-stone-400 tabular-nums">
                    {i + 1}
                  </td>
                  {headers.map((h) => (
                    <td key={h} className="px-2 py-1.5 text-stone-700 font-mono">
                      {r[h] ?? ""}
                    </td>
                  ))}
                </tr>
              ))}
              {preview.length === 0 && (
                <tr>
                  <td
                    colSpan={headers.length + 1}
                    className="px-3 py-6 text-center text-stone-400 italic"
                  >
                    Пустой CSV
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Footer
        onBack={onBack}
        onNext={onNext}
        nextDisabled={validating || requiredMissing.length > 0 || rows.length === 0}
        nextLabel={validating ? "Проверяем…" : "Далее"}
        nextIcon={
          validating ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <ArrowRight className="w-4 h-4" />
          )
        }
      />
    </div>
  )
}

// ─── Step 3: Confirm ───────────────────────────────────────────────────────

interface ConfirmStepProps {
  entity: ImportEntity
  mapping: Mapping
  validation: { valid: ValidatedRow[]; invalid: ValidatedRow[] }
  importing: boolean
  importResult: { inserted: number; error: string | null } | null
  onBack: () => void
  onImport: () => void
  onReset: () => void
}

function ConfirmStep({
  entity,
  mapping,
  validation,
  importing,
  importResult,
  onBack,
  onImport,
  onReset,
}: ConfirmStepProps) {
  const { valid, invalid } = validation
  const mappedFields = useMemo(
    () => entity.fields.filter((f) => mapping[f.key]),
    [entity, mapping],
  )

  // ─── Success screen ────────────────────────────────────────────────────
  if (importResult && importResult.error === null) {
    return (
      <div className="space-y-5 max-w-2xl">
        <div className="bg-green-50 border border-green-200 rounded-lg p-5 flex items-center gap-3">
          <CheckCircle2 className="w-6 h-6 text-green-600 shrink-0" />
          <div>
            <div className="text-sm font-medium text-green-900">
              Импортировано {importResult.inserted} строк в «{entity.label}».
            </div>
            <div className="text-xs text-green-700 mt-0.5">
              Можно загрузить ещё один файл или вернуться в каталог.
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onReset}
            className="px-3 py-1.5 text-sm text-white bg-stone-900 hover:bg-stone-800 rounded-md inline-flex items-center gap-2"
          >
            <Upload className="w-4 h-4" />
            Импортировать ещё
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <SummaryCard
          icon={<FileText className="w-4 h-4 text-stone-500" />}
          label="Всего строк"
          value={valid.length + invalid.length}
          tone="neutral"
        />
        <SummaryCard
          icon={<CheckCircle2 className="w-4 h-4 text-green-600" />}
          label="Готовы к импорту"
          value={valid.length}
          tone="success"
        />
        <SummaryCard
          icon={<XCircle className="w-4 h-4 text-red-600" />}
          label="С ошибками"
          value={invalid.length}
          tone="error"
        />
      </div>

      {/* Invalid rows */}
      {invalid.length > 0 && (
        <div>
          <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-2">
            Строки с ошибками — пропустим
          </div>
          <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-red-50/60 border-b border-stone-200">
                <tr className="text-left text-[10px] uppercase tracking-wider text-red-700">
                  <th className="px-2 py-2 font-medium w-10">#</th>
                  <th className="px-2 py-2 font-medium">Причина</th>
                  {mappedFields.slice(0, 3).map((f) => (
                    <th key={f.key} className="px-2 py-2 font-medium font-mono">
                      {f.key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {invalid.slice(0, 50).map((r) => (
                  <tr
                    key={r.idx}
                    className="border-b border-stone-100 last:border-0 bg-red-50/30"
                  >
                    <td className="px-2 py-1.5 text-stone-400 tabular-nums">
                      {r.idx + 1}
                    </td>
                    <td className="px-2 py-1.5 text-red-700">
                      {r.errors.join("; ")}
                    </td>
                    {mappedFields.slice(0, 3).map((f) => (
                      <td
                        key={f.key}
                        className="px-2 py-1.5 text-stone-700 font-mono"
                      >
                        {String(r.payload[f.key] ?? "—")}
                      </td>
                    ))}
                  </tr>
                ))}
                {invalid.length > 50 && (
                  <tr>
                    <td
                      colSpan={mappedFields.slice(0, 3).length + 2}
                      className="px-3 py-2 text-center text-stone-400 italic"
                    >
                      … и ещё {invalid.length - 50} строк с ошибками
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Valid rows */}
      {valid.length > 0 && (
        <div>
          <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-2">
            Валидные строки — будут импортированы
          </div>
          <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-green-50/60 border-b border-stone-200">
                <tr className="text-left text-[10px] uppercase tracking-wider text-green-700">
                  <th className="px-2 py-2 font-medium w-10">#</th>
                  {mappedFields.map((f) => (
                    <th key={f.key} className="px-2 py-2 font-medium font-mono">
                      {f.key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {valid.slice(0, 50).map((r) => (
                  <tr
                    key={r.idx}
                    className="border-b border-stone-100 last:border-0 bg-green-50/20"
                  >
                    <td className="px-2 py-1.5 text-stone-400 tabular-nums">
                      {r.idx + 1}
                    </td>
                    {mappedFields.map((f) => (
                      <td
                        key={f.key}
                        className="px-2 py-1.5 text-stone-700 font-mono"
                      >
                        {String(r.payload[f.key] ?? "—")}
                      </td>
                    ))}
                  </tr>
                ))}
                {valid.length > 50 && (
                  <tr>
                    <td
                      colSpan={mappedFields.length + 1}
                      className="px-3 py-2 text-center text-stone-400 italic"
                    >
                      … и ещё {valid.length - 50} строк
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {importResult?.error && (
        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {importResult.error}
          {importResult.inserted > 0 && (
            <div className="text-xs text-red-600 mt-1">
              Успешно импортировано до ошибки: {importResult.inserted} строк.
            </div>
          )}
        </div>
      )}

      <Footer
        onBack={onBack}
        onNext={onImport}
        nextDisabled={importing || valid.length === 0}
        nextLabel={
          importing
            ? "Импортируем…"
            : `Импортировать ${valid.length} валидных строк`
        }
        nextIcon={
          importing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <ArrowRight className="w-4 h-4" />
          )
        }
        extra={
          <button
            type="button"
            onClick={onReset}
            className="px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-100 rounded-md inline-flex items-center gap-1.5"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Сбросить
          </button>
        }
      />
    </div>
  )
}

// ─── Shared subcomponents ─────────────────────────────────────────────────

interface FooterProps {
  onBack: () => void
  onNext: () => void
  nextDisabled?: boolean
  nextLabel: string
  nextIcon?: React.ReactNode
  extra?: React.ReactNode
}

function Footer({
  onBack,
  onNext,
  nextDisabled,
  nextLabel,
  nextIcon,
  extra,
}: FooterProps) {
  return (
    <div className="flex items-center justify-between pt-2">
      <button
        type="button"
        onClick={onBack}
        className="px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-100 rounded-md inline-flex items-center gap-1.5"
      >
        <ArrowLeft className="w-4 h-4" />
        Назад
      </button>
      <div className="flex items-center gap-2">
        {extra}
        <button
          type="button"
          onClick={onNext}
          disabled={nextDisabled}
          className={cn(
            "px-3 py-1.5 text-sm text-white bg-stone-900 hover:bg-stone-800 rounded-md inline-flex items-center gap-1.5",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          {nextLabel}
          {nextIcon}
        </button>
      </div>
    </div>
  )
}

interface SummaryCardProps {
  icon: React.ReactNode
  label: string
  value: number
  tone: "neutral" | "success" | "error"
}

function SummaryCard({ icon, label, value, tone }: SummaryCardProps) {
  const toneCls =
    tone === "success"
      ? "border-green-200 bg-green-50/40"
      : tone === "error"
        ? "border-red-200 bg-red-50/40"
        : "border-stone-200 bg-white"
  return (
    <div className={cn("rounded-lg border p-3", toneCls)}>
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-stone-500 mb-1">
        {icon}
        {label}
      </div>
      <div className="text-2xl text-stone-900 tabular-nums">{value}</div>
    </div>
  )
}
