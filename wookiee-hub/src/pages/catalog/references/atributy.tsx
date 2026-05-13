// W6.1+W6.2 — Atributy CRUD page.
//
// Реестр атрибутов: `id`, `key`, `label`, `type`, `options`, `default_value`,
// `helper_text`. До W6.1 хранилось хардкодом в `src/types/catalog.ts` —
// миграция 022 вынесла его в БД (`public.atributy`).
//
// Поведение:
//   • Таблица — все 10 типов + кастомные пользовательские.
//   • Создание/редактирование — через `RefModal` (key иммутабелен после save).
//   • Удаление — pre-check: атрибут не должен быть привязан к категориям
//     (FK ON DELETE CASCADE есть, но удалять «привязанный» атрибут — плохая
//     UX: пропадут данные у моделей).
//
// W6.3 (отдельный коммит) научит model-card отображать новые контролы
// (multiselect/pills/url/date/checkbox) — здесь только справочник.

import { useEffect, useMemo, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReferenceCrud } from "./_use-reference"
import { supabase } from "@/lib/supabase"
import {
  fetchAtributy,
  fetchKategorii,
  insertAtribut,
  updateAtribut,
  deleteAtribut,
  bulkLinkAtributToKategorii,
  type Atribut,
  type AtributPayload,
  type AtributType,
} from "@/lib/catalog/service"
import { translateError } from "@/lib/catalog/error-translator"
import { toast } from "@/lib/catalog/toast"
import {
  AddButton,
  ConfirmDialog,
  ErrorBlock,
  PageHeader,
  PageShell,
  RowActions,
  SearchBox,
  SkeletonTable,
} from "./_shared"

/**
 * Валидация `key`: snake_case, начинается с латинской буквы. Совпадает с
 * правилом, которое используется как имя колонки в `modeli_osnova`.
 */
const KEY_RE = /^[a-z][a-z0-9_]*$/

const TYPE_OPTIONS: { value: AtributType; label: string }[] = [
  { value: "text",        label: "Текст" },
  { value: "textarea",    label: "Текст (многострочный)" },
  { value: "number",      label: "Число" },
  { value: "select",      label: "Список (один)" },
  { value: "multiselect", label: "Список (несколько)" },
  { value: "pills",       label: "Пилюли (теги)" },
  { value: "file_url",    label: "Файл (URL)" },
  { value: "url",         label: "Ссылка" },
  { value: "date",        label: "Дата" },
  { value: "checkbox",    label: "Галочка" },
]

const TYPE_LABEL: Record<AtributType, string> = Object.fromEntries(
  TYPE_OPTIONS.map((o) => [o.value, o.label]),
) as Record<AtributType, string>

const TYPES_WITH_OPTIONS: AtributType[] = ["select", "multiselect", "pills"]

/** Подсчёт использования атрибута в `kategoriya_atributy` — для блокировки delete. */
async function fetchAtributUsage(): Promise<Record<number, number>> {
  const { data, error } = await supabase
    .from("kategoriya_atributy")
    .select("atribut_id")
  if (error) throw new Error(error.message)
  const acc: Record<number, number> = {}
  for (const row of (data ?? []) as { atribut_id: number | null }[]) {
    if (row.atribut_id == null) continue
    acc[row.atribut_id] = (acc[row.atribut_id] ?? 0) + 1
  }
  return acc
}

export function AtributyPage() {
  const qc = useQueryClient()
  const ref = useReferenceCrud<Atribut, AtributPayload>(
    "atributy",
    fetchAtributy,
    {
      insert: (data) => insertAtribut(data),
      update: (id, patch) => updateAtribut(id, patch),
      remove: (id) => deleteAtribut(id),
    },
  )

  const usageQ = useQuery({
    queryKey: ["catalog", "reference", "atributy", "usage"],
    queryFn: fetchAtributUsage,
    staleTime: 60 * 1000,
  })

  // W10.18: список категорий для multiselect в модалке создания.
  const kategoriiQ = useQuery({
    queryKey: ["catalog", "reference", "kategorii"],
    queryFn: fetchKategorii,
    staleTime: 5 * 60 * 1000,
  })

  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<Atribut | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<Atribut | null>(null)

  const filtered = useMemo(() => {
    const data = ref.list.data ?? []
    if (!search.trim()) return data
    const q = search.toLowerCase()
    return data.filter(
      (r) =>
        r.key.toLowerCase().includes(q) ||
        r.label.toLowerCase().includes(q) ||
        TYPE_LABEL[r.type].toLowerCase().includes(q) ||
        (r.helper_text ?? "").toLowerCase().includes(q),
    )
  }, [ref.list.data, search])

  const columns: TableColumn<Atribut>[] = [
    { key: "id", label: "ID", mono: true, dim: true },
    {
      key: "key",
      label: "Ключ",
      mono: true,
      render: (r) => (
        <span className="font-mono text-xs text-stone-700">{r.key}</span>
      ),
    },
    { key: "label", label: "Название" },
    {
      key: "type",
      label: "Тип",
      render: (r) => (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] bg-stone-100 text-stone-700 border border-stone-200">
          {TYPE_LABEL[r.type] ?? r.type}
        </span>
      ),
    },
    {
      key: "options",
      label: "Варианты",
      render: (r) => {
        if (!TYPES_WITH_OPTIONS.includes(r.type)) {
          return <span className="text-stone-300">—</span>
        }
        if (r.options.length === 0) {
          return <span className="text-stone-400 italic text-xs">пусто</span>
        }
        const preview = r.options.slice(0, 3).join(" · ")
        const extra = r.options.length > 3 ? r.options.length - 3 : 0
        return (
          <span
            className="text-stone-600 text-xs"
            title={r.options.join("\n")}
          >
            {preview}
            {extra > 0 && (
              <span className="text-stone-400"> · … ещё {extra}</span>
            )}
          </span>
        )
      },
    },
    {
      key: "helper_text",
      label: "Подсказка",
      render: (r) =>
        r.helper_text ? (
          <span className="text-stone-600 text-xs" title={r.helper_text}>
            {r.helper_text.length > 50
              ? `${r.helper_text.slice(0, 50)}…`
              : r.helper_text}
          </span>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
    {
      key: "usage",
      label: "Категорий",
      render: (r) => (
        <span className="text-stone-700 tabular-nums font-mono text-xs">
          {usageQ.data?.[r.id] ?? 0}
        </span>
      ),
    },
    {
      key: "actions",
      label: "",
      render: (r) => (
        <RowActions
          onEdit={() => setEditing(r)}
          onDelete={() => setDeleting(r)}
        />
      ),
    },
  ]

  const handleSave = async (
    vals: AtributPayload,
    isNew: boolean,
    kategoriyaIds: number[],
  ) => {
    if (isNew) {
      // insert возвращает полный Atribut с id — нужно для linkov.
      const created = (await ref.insert.mutateAsync(vals)) as Atribut
      // W10.18: если в модалке выбраны категории — линкуем одним INSERT-ом.
      if (kategoriyaIds.length > 0 && created?.id) {
        await bulkLinkAtributToKategorii(created.id, created.key, kategoriyaIds)
        // обновим usage-колонку («Категорий»).
        await qc.invalidateQueries({
          queryKey: ["catalog", "reference", "atributy", "usage"],
        })
      }
      setCreating(false)
    } else if (editing) {
      // `key` иммутабелен — не передаём в patch.
      const { key: _omit, ...patch } = vals
      void _omit
      await ref.update.mutateAsync({ id: editing.id, patch })
      setEditing(null)
    }
  }

  return (
    <PageShell>
      <PageHeader
        title="Атрибуты"
        subtitle="Поля модели — название, тип, варианты. Привязку к категориям можно задать сразу при создании или позже на странице «Категории»."
        count={ref.list.data?.length ?? 0}
        isLoading={ref.list.isLoading}
        actions={
          <AddButton onClick={() => setCreating(true)} label="Новый атрибут" />
        }
      />
      <SearchBox
        value={search}
        onChange={setSearch}
        placeholder="Поиск по ключу, названию, типу…"
      />
      {ref.list.error && <ErrorBlock message={ref.list.error.message} />}
      {ref.list.isLoading ? (
        <SkeletonTable rows={6} cols={6} />
      ) : (
        <CatalogTable
          columns={columns}
          data={filtered}
          emptyText="Атрибутов пока нет — нажмите «Новый атрибут»"
        />
      )}

      {(creating || editing) && (
        <AtributModal
          initial={editing}
          kategorii={kategoriiQ.data ?? []}
          onSave={(vals, kategoriyaIds) => handleSave(vals, creating, kategoriyaIds)}
          onCancel={() => {
            setEditing(null)
            setCreating(false)
          }}
        />
      )}

      <ConfirmDialog
        open={!!deleting}
        title="Удалить атрибут?"
        message={
          deleting
            ? `«${deleting.label}» (key: ${deleting.key}) будет удалён без возможности восстановления. ${
                (usageQ.data?.[deleting.id] ?? 0) > 0
                  ? `⚠ Используется в ${usageQ.data?.[deleting.id]} категори${
                      (usageQ.data?.[deleting.id] ?? 0) === 1 ? "и" : "ях"
                    } — удаление будет заблокировано.`
                  : "Атрибут не привязан ни к одной категории."
              }`
            : undefined
        }
        confirmLabel="Удалить"
        destructive={true}
        onConfirm={async () => {
          if (!deleting) return
          try {
            await ref.remove.mutateAsync(deleting.id)
            setDeleting(null)
          } catch (e) {
            toast.error(translateError(e))
          }
        }}
        onCancel={() => setDeleting(null)}
      />
    </PageShell>
  )
}

// ─── Modal ────────────────────────────────────────────────────────────────
//
// Кастомная модалка — потому что:
//   • `key` иммутабелен после save (нужен read-only вид при edit);
//   • поле «Варианты» (textarea, `\n`-separated) видно только для
//     select/multiselect/pills.
// RefModal не поддерживает динамическую видимость полей на основе других
// значений, поэтому пишем свою.

interface KategoriyaOption {
  id: number
  nazvanie: string
}

interface AtributModalProps {
  initial: Atribut | null
  /** Список категорий для multiselect в режиме создания (W10.18). */
  kategorii: KategoriyaOption[]
  onSave: (payload: AtributPayload, kategoriyaIds: number[]) => Promise<void>
  onCancel: () => void
}

function AtributModal({ initial, kategorii, onSave, onCancel }: AtributModalProps) {
  const isEdit = initial != null
  const [key, setKey] = useState(initial?.key ?? "")
  const [label, setLabel] = useState(initial?.label ?? "")
  const [type, setType] = useState<AtributType>(initial?.type ?? "text")
  const [optionsText, setOptionsText] = useState(
    (initial?.options ?? []).join("\n"),
  )
  const [defaultValue, setDefaultValue] = useState(initial?.default_value ?? "")
  const [helperText, setHelperText] = useState(initial?.helper_text ?? "")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // W10.18: выбранные категории для bulk-link при создании.
  const [selectedKategoriyaIds, setSelectedKategoriyaIds] = useState<number[]>([])
  const [kategoriiSearch, setKategoriiSearch] = useState("")

  const filteredKategorii = useMemo(() => {
    if (!kategoriiSearch.trim()) return kategorii
    const q = kategoriiSearch.toLowerCase()
    return kategorii.filter((k) => k.nazvanie.toLowerCase().includes(q))
  }, [kategorii, kategoriiSearch])

  const toggleKategoriya = (id: number) => {
    setSelectedKategoriyaIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    )
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onCancel])

  const showOptions = TYPES_WITH_OPTIONS.includes(type)

  const handleSubmit = async () => {
    setError(null)
    const trimmedKey = key.trim()
    const trimmedLabel = label.trim()
    if (!trimmedKey) {
      setError("Заполните «Ключ»")
      return
    }
    if (!isEdit && !KEY_RE.test(trimmedKey)) {
      setError(
        "Ключ должен начинаться с латинской буквы и содержать только латиницу, цифры и `_` (snake_case).",
      )
      return
    }
    if (!trimmedLabel) {
      setError("Заполните «Название»")
      return
    }
    const options = showOptions
      ? optionsText
          .split("\n")
          .map((s) => s.trim())
          .filter((s) => s.length > 0)
      : []
    if (showOptions && options.length === 0) {
      setError("Для списочных типов укажите хотя бы один вариант.")
      return
    }

    const payload: AtributPayload = {
      key: trimmedKey,
      label: trimmedLabel,
      type,
      options,
      default_value: defaultValue.trim() === "" ? null : defaultValue.trim(),
      helper_text: helperText.trim() === "" ? null : helperText.trim(),
    }

    setSaving(true)
    try {
      await onSave(payload, isEdit ? [] : selectedKategoriyaIds)
    } catch (e) {
      setError(translateError(e))
    } finally {
      setSaving(false)
    }
  }

  const inputCls =
    "w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"

  return (
    <div
      className="fixed inset-0 z-50 bg-stone-900/40 flex items-center justify-center p-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-lg bg-white rounded-xl shadow-2xl overflow-hidden border border-stone-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-stone-200">
          <h2
            className="cat-font-serif text-xl text-stone-900 italic"
            style={{ fontFamily: "'Instrument Serif', ui-serif, Georgia, serif" }}
          >
            {isEdit ? "Редактировать атрибут" : "Новый атрибут"}
          </h2>
          <button
            type="button"
            onClick={onCancel}
            className="p-1 hover:bg-stone-100 rounded"
            aria-label="Close"
          >
            <X className="w-4 h-4 text-stone-500" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-3 max-h-[70vh] overflow-y-auto">
          <Field
            label="Ключ"
            required
            hint={
              isEdit
                ? "Ключ нельзя изменить после создания — он используется как имя колонки."
                : "snake_case, латиница / цифры / `_`. Будет именем колонки в `modeli_osnova`."
            }
          >
            <input
              type="text"
              value={key}
              disabled={isEdit}
              placeholder="stepen_podderzhki"
              onChange={(e) => setKey(e.target.value)}
              className={cn(
                inputCls,
                isEdit && "bg-stone-50 text-stone-500 cursor-not-allowed",
              )}
            />
          </Field>

          <Field label="Название" required>
            <input
              type="text"
              value={label}
              placeholder="Степень поддержки"
              onChange={(e) => setLabel(e.target.value)}
              className={inputCls}
            />
          </Field>

          <Field label="Тип" required>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as AtributType)}
              className={inputCls}
            >
              {TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>

          {showOptions && (
            <Field
              label="Варианты"
              required
              hint="Один вариант на строку. Порядок сохраняется."
            >
              <textarea
                rows={5}
                value={optionsText}
                placeholder={"Низкая\nСредняя\nВысокая"}
                onChange={(e) => setOptionsText(e.target.value)}
                className={cn(inputCls, "resize-none font-mono text-xs")}
              />
            </Field>
          )}

          <Field
            label="Значение по умолчанию"
            hint="Используется в новых моделях. Опционально."
          >
            <input
              type="text"
              value={defaultValue}
              onChange={(e) => setDefaultValue(e.target.value)}
              className={inputCls}
            />
          </Field>

          <Field
            label="Подсказка"
            hint="Текст под полем в карточке модели. Опционально."
          >
            <textarea
              rows={2}
              value={helperText}
              onChange={(e) => setHelperText(e.target.value)}
              className={cn(inputCls, "resize-none")}
            />
          </Field>

          {/* W10.18: multiselect категорий — только при создании.
              В режиме edit привязка делается на странице «Категории». */}
          {!isEdit && (
            <Field
              label="Категории"
              hint={
                kategorii.length === 0
                  ? "Категории ещё не загружены — атрибут будет создан без привязки."
                  : "Выберите категории, к которым нужно сразу привязать атрибут. Можно оставить пусто и привязать позже."
              }
            >
              {kategorii.length > 7 && (
                <input
                  type="text"
                  value={kategoriiSearch}
                  onChange={(e) => setKategoriiSearch(e.target.value)}
                  placeholder="Поиск по категориям…"
                  className={cn(inputCls, "mb-2")}
                />
              )}
              <div className="max-h-48 overflow-y-auto rounded-md border border-stone-200 bg-stone-50 divide-y divide-stone-200">
                {filteredKategorii.length === 0 ? (
                  <div className="px-2.5 py-2 text-xs text-stone-400 italic">
                    {kategorii.length === 0 ? "Нет категорий" : "Ничего не найдено"}
                  </div>
                ) : (
                  filteredKategorii.map((k) => {
                    const checked = selectedKategoriyaIds.includes(k.id)
                    return (
                      <label
                        key={k.id}
                        className={cn(
                          "flex items-center gap-2 px-2.5 py-1.5 cursor-pointer hover:bg-white",
                          checked && "bg-white",
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleKategoriya(k.id)}
                          className="h-3.5 w-3.5 accent-stone-900"
                        />
                        <span className="text-sm text-stone-700">{k.nazvanie}</span>
                        <span className="ml-auto text-[10px] text-stone-400 font-mono">
                          #{k.id}
                        </span>
                      </label>
                    )
                  })
                )}
              </div>
              {selectedKategoriyaIds.length > 0 && (
                <div className="mt-1 text-[10px] text-stone-500">
                  Выбрано: {selectedKategoriyaIds.length}
                </div>
              )}
            </Field>
          )}
        </div>

        {error && (
          <div className="px-5 py-2 text-xs text-red-600 bg-red-50 border-t border-red-100">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-stone-200 bg-stone-50">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-100 rounded-md"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving}
            className={cn(
              "px-3 py-1.5 text-sm text-white bg-stone-900 hover:bg-stone-800 rounded-md",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {saving ? "Сохраняем…" : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
  )
}

interface FieldProps {
  label: string
  required?: boolean
  hint?: string
  children: React.ReactNode
}

function Field({ label, required, hint, children }: FieldProps) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {hint && <div className="text-[10px] text-stone-400 mt-1">{hint}</div>}
    </div>
  )
}
