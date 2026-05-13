// W10.14 + W10.15 + W10.35 — ReferenceDrawer.
//
// Универсальный drawer-карточка для всех справочных страниц
// (/catalog/references/*). Открывается из реестра по single-click на строку
// (вместо старой модалки RefModal). Cтиль match-у-с ArtikulDrawer:
//   rounded-l-2xl + shadow-2xl + backdrop + Esc-close.
//
// Контракт:
//   <ReferenceDrawer
//     title="Бренды"
//     subtitle="WOOKIEE"
//     fields={...}                    // те же RefFieldDef, что и в RefModal
//     initial={...}                   // текущие значения
//     onSave={async (vals) => ...}
//     onClose={() => setOpen(false)}
//     linkedSections={[
//       { kind: "models", title: "Модели", refColumn: "brand_id", refId: 5, readOnly: true },
//       { kind: "atributy", title: "Атрибуты категории", kategoriyaId: 7 },
//     ]}
//   />
//
// Каждая `linkedSection` — отдельный блок в табе «Привязанные».

import { useEffect, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Loader2, Save, X, Plus, Search } from "lucide-react"

import { FieldInput, type RefFieldDef } from "@/components/catalog/ui/ref-modal"
import { translateError } from "@/lib/catalog/error-translator"
import { toast } from "@/lib/catalog/toast"
import {
  fetchModeliByRef,
  fetchModeliWithoutRef,
  setModelRef,
  fetchAttributesForCategory,
  fetchAtributyNotLinkedToKategoriya,
  linkAtributToKategoriya,
  unlinkAtributFromKategoriya,
  type ModelMini,
  type ModelRefColumn,
  type Atribut,
} from "@/lib/catalog/service"

type FormValues = Record<string, unknown>

// ─── Linked section spec ───────────────────────────────────────────────────

export type LinkedSectionSpec =
  | {
      kind: "models"
      title: string
      refColumn: ModelRefColumn
      refId: number
      /** Если true — только список, без add/remove. Для brendy (brand_id NOT NULL). */
      readOnly?: boolean
      /** Подсказка под заголовком (например, почему readOnly). */
      hint?: string
    }
  | {
      kind: "atributy"
      title: string
      kategoriyaId: number
    }

// ─── Props ─────────────────────────────────────────────────────────────────

interface ReferenceDrawerProps {
  /** Заголовок drawer'а — родовое слово («Бренд», «Категория», …). */
  kind: string
  /** Имя записи — отображается под kind крупно. */
  title: string
  fields: RefFieldDef[]
  initial: FormValues
  onSave: (values: FormValues) => Promise<void> | void
  onClose: () => void
  linkedSections?: LinkedSectionSpec[]
}

type TabId = "description" | "linked"

export function ReferenceDrawer({
  kind,
  title,
  fields,
  initial,
  onSave,
  onClose,
  linkedSections,
}: ReferenceDrawerProps) {
  const [tab, setTab] = useState<TabId>("description")
  const [values, setValues] = useState<FormValues>(() => ({ ...initial }))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Esc → close.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  // Если initial обновился (например, после save и refetch родителя) — синхронизируемся.
  useEffect(() => {
    setValues({ ...initial })
  }, [initial])

  const isDirty = useMemo(() => {
    return fields.some((f) => {
      const a = values[f.key]
      const b = initial[f.key]
      if (a == null && b == null) return false
      if (a == null || b == null) return true
      return String(a) !== String(b)
    })
  }, [values, initial, fields])

  const handleSave = async () => {
    // Required check.
    for (const f of fields) {
      if (!f.required) continue
      const v = values[f.key]
      if (v == null || v === "" || (Array.isArray(v) && v.length === 0)) {
        setError(`Заполните обязательное поле «${f.label}»`)
        return
      }
    }
    setError(null)
    setSaving(true)
    try {
      await onSave(values)
      toast.success("Сохранено")
    } catch (e) {
      setError(translateError(e))
    } finally {
      setSaving(false)
    }
  }

  const hasLinked = (linkedSections?.length ?? 0) > 0
  const linkedCount = (linkedSections ?? []).filter((s) => s.kind !== "atributy" ? true : true).length // visual placeholder

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} aria-hidden="true" />
      <div
        className="fixed inset-y-0 right-0 w-[640px] bg-white rounded-l-2xl shadow-2xl z-50 overflow-hidden flex flex-col"
        role="dialog"
        aria-label={`Карточка: ${kind}`}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-stone-200 bg-white shrink-0">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-0.5">
                {kind}
              </div>
              <h2
                className="text-2xl text-stone-900 italic truncate"
                style={{ fontFamily: "'Instrument Serif', ui-serif, Georgia, serif" }}
                title={title}
              >
                {title}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded hover:bg-stone-100 text-stone-500 shrink-0"
              aria-label="Закрыть"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        {hasLinked && (
          <div className="border-b border-stone-200 bg-white px-6 flex gap-1 shrink-0">
            <TabBtn id="description" active={tab === "description"} onClick={() => setTab("description")}>
              Описание
            </TabBtn>
            <TabBtn id="linked" active={tab === "linked"} onClick={() => setTab("linked")}>
              Привязанные
              {linkedCount > 0 && (
                <span className="ml-1.5 text-xs text-stone-400 tabular-nums">{linkedCount}</span>
              )}
            </TabBtn>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-auto bg-stone-50">
          {tab === "description" && (
            <div className="px-6 py-5">
              <div className="grid grid-cols-2 gap-3">
                {fields.map((f) => (
                  <FieldInput
                    key={f.key}
                    field={f}
                    value={values[f.key]}
                    onChange={(v) => setValues((prev) => ({ ...prev, [f.key]: v }))}
                  />
                ))}
              </div>
              {error && (
                <div className="mt-4 px-3 py-2 text-xs text-red-600 bg-red-50 border border-red-100 rounded-md">
                  {error}
                </div>
              )}
            </div>
          )}
          {tab === "linked" && (
            <div className="px-6 py-5 space-y-6">
              {(linkedSections ?? []).map((sec, idx) => {
                if (sec.kind === "models") {
                  return (
                    <LinkedModelsSection
                      key={`${sec.refColumn}-${idx}`}
                      title={sec.title}
                      refColumn={sec.refColumn}
                      refId={sec.refId}
                      readOnly={sec.readOnly}
                      hint={sec.hint}
                    />
                  )
                }
                return (
                  <LinkedAtributySection
                    key={`atributy-${idx}`}
                    title={sec.title}
                    kategoriyaId={sec.kategoriyaId}
                  />
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        {tab === "description" && (
          <div className="border-t border-stone-200 bg-white px-6 py-3 flex items-center justify-end gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setValues({ ...initial })}
              disabled={!isDirty || saving}
              className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-md disabled:opacity-40"
            >
              Отменить
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={!isDirty || saving}
              className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md disabled:opacity-40 flex items-center gap-1.5"
            >
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              {saving ? "Сохраняем…" : "Сохранить"}
            </button>
          </div>
        )}
      </div>
    </>
  )
}

// ─── Tab button ────────────────────────────────────────────────────────────

function TabBtn({
  active,
  children,
  onClick,
}: {
  id: TabId
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-2.5 text-sm border-b-2 -mb-px transition-colors ${
        active
          ? "border-stone-900 text-stone-900 font-medium"
          : "border-transparent text-stone-500 hover:text-stone-700"
      }`}
    >
      {children}
    </button>
  )
}

// ─── Linked: модели через FK на modeli_osnova ──────────────────────────────

function LinkedModelsSection({
  title,
  refColumn,
  refId,
  readOnly,
  hint,
}: {
  title: string
  refColumn: ModelRefColumn
  refId: number
  readOnly?: boolean
  hint?: string
}) {
  const qc = useQueryClient()
  const listQ = useQuery<ModelMini[]>({
    queryKey: ["catalog", "reference", "linked-models", refColumn, refId],
    queryFn: () => fetchModeliByRef(refColumn, refId),
    staleTime: 30 * 1000,
  })
  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["catalog", "reference", "linked-models", refColumn, refId] })

  const setMut = useMutation({
    mutationFn: async ({ modelId, value }: { modelId: number; value: number | null }) => {
      await setModelRef(modelId, refColumn, value)
    },
    onSuccess: () => {
      void invalidate()
      void qc.invalidateQueries({ queryKey: ["catalog"] })
    },
    onError: (err) => toast.error(translateError(err)),
  })

  const rows = listQ.data ?? []
  const [picking, setPicking] = useState(false)

  return (
    <section>
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="text-sm font-medium text-stone-800">
          {title}
          <span className="ml-1.5 text-xs text-stone-400 tabular-nums">{rows.length}</span>
        </h3>
        {!readOnly && (
          <button
            type="button"
            onClick={() => setPicking((v) => !v)}
            className="text-xs text-stone-700 hover:text-stone-900 flex items-center gap-1"
          >
            <Plus className="w-3.5 h-3.5" /> Добавить
          </button>
        )}
      </div>
      {hint && <p className="text-[11px] text-stone-500 mb-2">{hint}</p>}

      {listQ.isLoading ? (
        <div className="text-xs text-stone-400 flex items-center gap-1.5">
          <Loader2 className="w-3 h-3 animate-spin" /> Загрузка…
        </div>
      ) : rows.length === 0 ? (
        <div className="text-xs text-stone-400 italic py-3 text-center bg-white border border-stone-200 rounded-md">
          Пока ничего не привязано.
        </div>
      ) : (
        <div className="bg-white border border-stone-200 rounded-md divide-y divide-stone-100">
          {rows.map((m) => (
            <div
              key={m.id}
              className="flex items-center justify-between px-3 py-2 text-sm hover:bg-stone-50"
            >
              <div className="min-w-0 flex-1">
                <div className="font-mono text-xs text-stone-700">{m.kod}</div>
                {m.nazvanie && (
                  <div className="text-[11px] text-stone-500 truncate">{m.nazvanie}</div>
                )}
              </div>
              {!readOnly && (
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm(`Открепить «${m.kod}»?`)) {
                      setMut.mutate({ modelId: m.id, value: null })
                    }
                  }}
                  className="p-1 text-stone-400 hover:text-red-600 hover:bg-red-50 rounded"
                  aria-label="Открепить"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {picking && !readOnly && (
        <AddModelPicker
          refColumn={refColumn}
          onPick={(modelId) => {
            setMut.mutate({ modelId, value: refId })
            setPicking(false)
          }}
          onCancel={() => setPicking(false)}
        />
      )}
    </section>
  )
}

function AddModelPicker({
  refColumn,
  onPick,
  onCancel,
}: {
  refColumn: ModelRefColumn
  onPick: (modelId: number) => void
  onCancel: () => void
}) {
  const [search, setSearch] = useState("")
  const candidatesQ = useQuery<ModelMini[]>({
    queryKey: ["catalog", "reference", "model-picker", refColumn, search],
    queryFn: () => fetchModeliWithoutRef(refColumn, search),
    staleTime: 30 * 1000,
  })

  return (
    <div className="mt-3 bg-white border border-stone-200 rounded-md p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400 pointer-events-none" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по kod или названию…"
            className="w-full pl-7 pr-2 py-1 text-sm border border-stone-200 rounded outline-none focus:border-stone-400"
            autoFocus
          />
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs text-stone-500 hover:text-stone-700"
        >
          Отмена
        </button>
      </div>
      <div className="max-h-48 overflow-y-auto">
        {candidatesQ.isLoading ? (
          <div className="text-xs text-stone-400 py-2 text-center">Загрузка…</div>
        ) : (candidatesQ.data ?? []).length === 0 ? (
          <div className="text-xs text-stone-400 py-2 text-center italic">
            {search.trim() ? "Ничего не найдено" : "Все модели уже привязаны"}
          </div>
        ) : (
          (candidatesQ.data ?? []).map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => onPick(m.id)}
              className="w-full text-left px-2 py-1.5 hover:bg-stone-50 rounded text-sm flex items-baseline gap-2"
            >
              <span className="font-mono text-xs text-stone-700">{m.kod}</span>
              {m.nazvanie && (
                <span className="text-[11px] text-stone-500 truncate">{m.nazvanie}</span>
              )}
            </button>
          ))
        )}
      </div>
    </div>
  )
}

// ─── Linked: атрибуты категории через kategoriya_atributy ──────────────────

function LinkedAtributySection({
  title,
  kategoriyaId,
}: {
  title: string
  kategoriyaId: number
}) {
  const qc = useQueryClient()
  const listQ = useQuery<Atribut[]>({
    queryKey: ["catalog", "reference", "linked-atributy", kategoriyaId],
    queryFn: () => fetchAttributesForCategory(kategoriyaId),
    staleTime: 30 * 1000,
  })
  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["catalog", "reference", "linked-atributy", kategoriyaId] })

  const linkMut = useMutation({
    mutationFn: async (atributId: number) => {
      await linkAtributToKategoriya(atributId, kategoriyaId)
    },
    onSuccess: () => void invalidate(),
    onError: (err) => toast.error(translateError(err)),
  })
  const unlinkMut = useMutation({
    mutationFn: async (atributId: number) => {
      await unlinkAtributFromKategoriya(atributId, kategoriyaId)
    },
    onSuccess: () => void invalidate(),
    onError: (err) => toast.error(translateError(err)),
  })

  const rows = listQ.data ?? []
  const [picking, setPicking] = useState(false)

  return (
    <section>
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="text-sm font-medium text-stone-800">
          {title}
          <span className="ml-1.5 text-xs text-stone-400 tabular-nums">{rows.length}</span>
        </h3>
        <button
          type="button"
          onClick={() => setPicking((v) => !v)}
          className="text-xs text-stone-700 hover:text-stone-900 flex items-center gap-1"
        >
          <Plus className="w-3.5 h-3.5" /> Добавить
        </button>
      </div>

      {listQ.isLoading ? (
        <div className="text-xs text-stone-400 flex items-center gap-1.5">
          <Loader2 className="w-3 h-3 animate-spin" /> Загрузка…
        </div>
      ) : rows.length === 0 ? (
        <div className="text-xs text-stone-400 italic py-3 text-center bg-white border border-stone-200 rounded-md">
          Атрибуты к категории не привязаны.
        </div>
      ) : (
        <div className="bg-white border border-stone-200 rounded-md divide-y divide-stone-100">
          {rows.map((a) => (
            <div key={a.id} className="flex items-center justify-between px-3 py-2 text-sm hover:bg-stone-50">
              <div className="min-w-0 flex-1">
                <div className="text-stone-800">{a.label}</div>
                <div className="text-[11px] text-stone-500 font-mono">{a.key} · {a.type}</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  if (window.confirm(`Открепить атрибут «${a.label}» от категории?`)) {
                    unlinkMut.mutate(a.id)
                  }
                }}
                className="p-1 text-stone-400 hover:text-red-600 hover:bg-red-50 rounded"
                aria-label="Открепить"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {picking && (
        <AddAtributPicker
          kategoriyaId={kategoriyaId}
          onPick={(atributId) => {
            linkMut.mutate(atributId)
            setPicking(false)
          }}
          onCancel={() => setPicking(false)}
        />
      )}
    </section>
  )
}

function AddAtributPicker({
  kategoriyaId,
  onPick,
  onCancel,
}: {
  kategoriyaId: number
  onPick: (atributId: number) => void
  onCancel: () => void
}) {
  const [search, setSearch] = useState("")
  const candidatesQ = useQuery<Atribut[]>({
    queryKey: ["catalog", "reference", "atribut-picker", kategoriyaId, search],
    queryFn: () => fetchAtributyNotLinkedToKategoriya(kategoriyaId, search),
    staleTime: 30 * 1000,
  })

  return (
    <div className="mt-3 bg-white border border-stone-200 rounded-md p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400 pointer-events-none" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по label или key…"
            className="w-full pl-7 pr-2 py-1 text-sm border border-stone-200 rounded outline-none focus:border-stone-400"
            autoFocus
          />
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs text-stone-500 hover:text-stone-700"
        >
          Отмена
        </button>
      </div>
      <div className="max-h-48 overflow-y-auto">
        {candidatesQ.isLoading ? (
          <div className="text-xs text-stone-400 py-2 text-center">Загрузка…</div>
        ) : (candidatesQ.data ?? []).length === 0 ? (
          <div className="text-xs text-stone-400 py-2 text-center italic">
            {search.trim() ? "Ничего не найдено" : "Все атрибуты уже привязаны"}
          </div>
        ) : (
          (candidatesQ.data ?? []).map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => onPick(a.id)}
              className="w-full text-left px-2 py-1.5 hover:bg-stone-50 rounded text-sm"
            >
              <div className="text-stone-800">{a.label}</div>
              <div className="text-[11px] text-stone-500 font-mono">{a.key} · {a.type}</div>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
