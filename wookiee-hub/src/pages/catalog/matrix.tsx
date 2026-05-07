import React, { useState, useMemo, useCallback } from "react"
import { useSearchParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import {
  Search, Plus, ChevronRight, ChevronDown, AlertCircle,
  ArrowLeft, Save, Edit3, Archive, Copy, Info, Building2,
  ExternalLink, Link2, FileText, Box,
} from "lucide-react"
import {
  fetchMatrixList, fetchModelDetail, fetchArtikulyRegistry, fetchTovaryRegistry,
  type MatrixRow, type ModelDetail,
} from "@/lib/catalog/service"
import { StatusBadge, CATALOG_STATUSES } from "@/components/catalog/ui/status-badge"
import { CompletenessRing } from "@/components/catalog/ui/completeness-ring"
import { swatchColor, relativeDate, ATTRIBUTES_BY_CATEGORY, ATTRIBUTE_LABELS, TIPY_KOLLEKCII } from "@/lib/catalog/color-utils"
import { fetchKategorii } from "@/lib/catalog/service"

// ─── Shared helpers ────────────────────────────────────────────────────────

function ColorSwatch({ colorCode, size = 16 }: { colorCode: string | null; size?: number }) {
  if (!colorCode) return <div className="rounded-full bg-stone-200" style={{ width: size, height: size }} />
  return (
    <div
      className="rounded-full ring-1 ring-stone-200 shrink-0"
      style={{ width: size, height: size, background: swatchColor(colorCode) }}
    />
  )
}

function Section({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 p-5">
      <div className="font-medium text-stone-900 mb-1">{label}</div>
      {hint && <div className="text-xs text-stone-500 mb-4">{hint}</div>}
      {!hint && <div className="mb-4" />}
      {children}
    </div>
  )
}

function SidebarBlock({ title, badge, action, children }: {
  title: string; badge?: React.ReactNode; action?: React.ReactNode; children: React.ReactNode
}) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5 text-xs uppercase tracking-wider text-stone-400">
          {title} {badge}
        </div>
        {action}
      </div>
      {children}
    </div>
  )
}

function FieldWrap({ label, children, hint, full }: { label: string; children: React.ReactNode; hint?: string; full?: boolean }) {
  return (
    <div className={full ? "col-span-2" : ""}>
      <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">{label}</label>
      {children}
      {hint && <div className="text-[10px] text-stone-400 mt-1">{hint}</div>}
    </div>
  )
}

function ReadField({ value, mono }: { value: string | number | null | undefined; mono?: boolean }) {
  if (value === null || value === undefined || value === "") {
    return <div className="px-2.5 py-1.5 text-sm text-stone-400 italic">не задано</div>
  }
  return <div className={`px-2.5 py-1.5 text-sm text-stone-900 ${mono ? "font-mono" : ""}`}>{value}</div>
}

// ─── Model Card (5 tabs) ───────────────────────────────────────────────────

function ModelCard({ modelId, onBack }: { modelId: number; onBack: () => void }) {
  const [tab, setTab] = useState<"opisanie" | "atributy" | "artikuly" | "sku" | "kontent">("opisanie")
  const { data: m, isLoading, error } = useQuery({
    queryKey: ["model-detail", modelId],
    queryFn: () => fetchModelDetail(modelId),
    staleTime: 2 * 60 * 1000,
  })

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-stone-400 text-sm">
        Загрузка…
      </div>
    )
  }
  if (error || !m) {
    return (
      <div className="flex-1 flex items-center justify-center text-red-500 text-sm">
        Ошибка загрузки модели
      </div>
    )
  }

  const allArts = m.modeli.flatMap((v) => v.artikuly)
  const allSku = allArts.flatMap((a) => a.tovary)
  const cvetaSet = new Set(allArts.map((a) => a.cvet_color_code).filter(Boolean))
  const attrKeys = ATTRIBUTES_BY_CATEGORY[m.kategoriya_id ?? 0] ?? []
  const attrFilled = attrKeys.filter((k) => (m as any)[k]).length
  const completeness = Math.round(
    (attrKeys.filter((k) => (m as any)[k]).length + (m.nazvanie_sayt ? 1 : 0)) /
    Math.max(attrKeys.length + 1, 1) * 100
  )

  const TABS = [
    { id: "opisanie", label: "Описание" },
    { id: "atributy", label: "Атрибуты", count: `${attrFilled}/${attrKeys.length}` },
    { id: "artikuly", label: "Артикулы", count: allArts.length },
    { id: "sku", label: "SKU", count: allSku.length },
    { id: "kontent", label: "Контент и связи" },
  ] as const

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-stone-200 bg-white shrink-0">
        <div className="px-6 py-4 flex items-center gap-4">
          <button onClick={onBack} className="p-1.5 hover:bg-stone-100 rounded-md">
            <ArrowLeft className="w-4 h-4 text-stone-700" />
          </button>
          <div className="flex-1">
            <div className="text-xs text-stone-400 mb-0.5">
              Базовая модель · {m.kategoriya ?? "—"}
            </div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-medium text-stone-900 cat-font-serif">{m.kod}</h2>
              <StatusBadge statusId={m.status_id ?? 0} />
              {m.nazvanie_sayt && (
                <span className="text-sm text-stone-500 truncate max-w-[300px]">{m.nazvanie_sayt}</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5">
              <Copy className="w-3.5 h-3.5" /> Дублировать
            </button>
            <button className="px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5">
              <Archive className="w-3.5 h-3.5" /> В архив
            </button>
            <button className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5">
              <Edit3 className="w-3.5 h-3.5" /> Редактировать
            </button>
          </div>
        </div>
        <div className="px-6 flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id as typeof tab)}
              className={`relative px-3 py-2.5 text-sm transition-colors ${
                tab === t.id ? "text-stone-900 font-medium" : "text-stone-500 hover:text-stone-800"
              }`}
            >
              {t.label}
              {"count" in t && t.count !== undefined && (
                <span className="ml-1.5 text-[10px] tabular-nums text-stone-400">{t.count}</span>
              )}
              {tab === t.id && (
                <span className="absolute bottom-0 left-0 right-0 h-px bg-stone-900" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-6 py-6 grid grid-cols-3 gap-6">
          <div className="col-span-2 space-y-3">
            {tab === "opisanie" && <TabOpisanie m={m} />}
            {tab === "atributy" && <TabAtributy m={m} attrKeys={attrKeys} />}
            {tab === "artikuly" && <TabArtikuly m={m} />}
            {tab === "sku" && <TabSKU m={m} />}
            {tab === "kontent" && <TabKontent m={m} />}
          </div>
          <div className="col-span-1 space-y-4">
            <SidebarBlock title="Заполненность">
              <div className="flex items-center gap-3">
                <CompletenessRing value={allSku.length > 0 ? 0.7 : 0.3} size={56} />
                <div>
                  <div className="text-2xl font-medium tabular-nums text-stone-900">{attrFilled}/{attrKeys.length}</div>
                  <div className="text-xs text-stone-500">атрибутов заполнено</div>
                </div>
              </div>
            </SidebarBlock>

            <SidebarBlock
              title="Вариации"
              badge={<span className="text-xs text-stone-500 tabular-nums">{m.modeli.length}</span>}
            >
              <div className="space-y-1">
                {m.modeli.map((v) => (
                  <div key={v.id} className="flex items-center justify-between py-1.5 px-2 -mx-2 hover:bg-stone-50 rounded text-sm">
                    <span className="font-mono text-stone-900">{v.kod}</span>
                    <span className="text-[10px] text-stone-400 uppercase tracking-wider">
                      {v.importer_nazvanie?.split(" ")[0] ?? "—"}
                    </span>
                  </div>
                ))}
                {m.modeli.length === 0 && (
                  <div className="text-sm text-stone-400 italic">Нет вариаций</div>
                )}
              </div>
            </SidebarBlock>

            <SidebarBlock
              title="Цвета модели"
              badge={<span className="text-xs text-stone-500 tabular-nums">{cvetaSet.size}</span>}
            >
              <div className="flex flex-wrap gap-1.5">
                {[...cvetaSet].slice(0, 20).map((code) => (
                  <div key={code} className="flex items-center gap-1.5 bg-stone-50 rounded px-1.5 py-1 text-xs">
                    <ColorSwatch colorCode={code} size={14} />
                    <span className="font-mono text-[10px] text-stone-700">{code}</span>
                  </div>
                ))}
                {cvetaSet.size > 20 && (
                  <span className="text-xs text-stone-400 self-center">+{cvetaSet.size - 20}</span>
                )}
              </div>
            </SidebarBlock>

            <SidebarBlock title="Метрики" >
              <div className="space-y-1.5 text-sm text-stone-400">
                <div className="flex justify-between">
                  <span>Остаток на складе</span><span className="tabular-nums">— шт</span>
                </div>
                <div className="flex justify-between">
                  <span>Оборачиваемость</span><span className="tabular-nums">— дн</span>
                </div>
                <div className="flex justify-between">
                  <span>Продаж за 30 дн</span><span className="tabular-nums">— шт</span>
                </div>
                <div className="text-[10px] italic mt-2 pt-2 border-t border-stone-100">
                  Данные подтянутся из МойСклад / WB API
                </div>
              </div>
            </SidebarBlock>
          </div>
        </div>
      </div>
    </div>
  )
}

function TabOpisanie({ m }: { m: ModelDetail }) {
  return (
    <>
      <Section label="Основное">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <FieldWrap label="Код модели"><ReadField value={m.kod} mono /></FieldWrap>
          <FieldWrap label="Статус"><div className="px-2.5 py-1.5"><StatusBadge statusId={m.status_id ?? 0} /></div></FieldWrap>
          <FieldWrap label="Категория"><ReadField value={m.kategoriya} /></FieldWrap>
          <FieldWrap label="Коллекция"><ReadField value={m.kollekciya} /></FieldWrap>
          <FieldWrap label="Тип коллекции"><ReadField value={m.tip_kollekcii} /></FieldWrap>
          <FieldWrap label="Фабрика"><ReadField value={m.fabrika} /></FieldWrap>
        </div>
      </Section>
      <Section label="Производство">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <FieldWrap label="Размерная линейка" full>
            <ReadField value={m.razmery_modeli} />
          </FieldWrap>
          <FieldWrap label="Материал"><ReadField value={m.material} /></FieldWrap>
          <FieldWrap label="SKU China"><ReadField value={m.sku_china} mono /></FieldWrap>
          <FieldWrap label="Состав сырья" full><ReadField value={m.sostav_syrya} /></FieldWrap>
          <FieldWrap label="Срок производства"><ReadField value={m.srok_proizvodstva} /></FieldWrap>
          <FieldWrap label="Кратность короба"><ReadField value={m.kratnost_koroba} /></FieldWrap>
          <FieldWrap label="Вес, кг"><ReadField value={m.ves_kg} mono /></FieldWrap>
          <FieldWrap label="Длина, см"><ReadField value={m.dlina_cm} mono /></FieldWrap>
          <FieldWrap label="Ширина, см"><ReadField value={m.shirina_cm} mono /></FieldWrap>
          <FieldWrap label="Высота, см"><ReadField value={m.vysota_cm} mono /></FieldWrap>
        </div>
      </Section>
      <Section label="Юридическое">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <FieldWrap label="ТНВЭД"><ReadField value={m.tnved} mono /></FieldWrap>
          <FieldWrap label="Группа сертификата"><ReadField value={m.gruppa_sertifikata} /></FieldWrap>
        </div>
      </Section>
    </>
  )
}

function TabAtributy({ m, attrKeys }: { m: ModelDetail; attrKeys: string[] }) {
  if (attrKeys.length === 0) {
    return (
      <Section label="Атрибуты">
        <div className="text-sm text-stone-400 italic">
          Для этой категории атрибуты не настроены
        </div>
      </Section>
    )
  }
  return (
    <Section
      label={`Атрибуты категории «${m.kategoriya ?? "—"}»`}
      hint={`${attrKeys.length} полей для данной категории`}
    >
      <div className="grid grid-cols-2 gap-x-4 gap-y-4">
        {attrKeys.map((key) => (
          <FieldWrap key={key} label={ATTRIBUTE_LABELS[key] ?? key}>
            <ReadField value={(m as any)[key]} />
          </FieldWrap>
        ))}
      </div>
    </Section>
  )
}

function TabArtikuly({ m }: { m: ModelDetail }) {
  const allArts = m.modeli.flatMap((v) => v.artikuly.map((a) => ({ ...a, variantKod: v.kod })))
  return (
    <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-stone-200 flex items-center justify-between">
        <div>
          <div className="font-medium text-stone-900">Артикулы модели</div>
          <div className="text-xs text-stone-500">{allArts.length} артикулов</div>
        </div>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-stone-50/80 border-b border-stone-200">
          <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
            <th className="px-3 py-2 font-medium">Артикул</th>
            <th className="px-3 py-2 font-medium">Вариация</th>
            <th className="px-3 py-2 font-medium">Цвет</th>
            <th className="px-3 py-2 font-medium">Статус</th>
            <th className="px-3 py-2 font-medium">WB номенкл.</th>
            <th className="px-3 py-2 font-medium">OZON</th>
            <th className="px-3 py-2 font-medium text-right">SKU</th>
          </tr>
        </thead>
        <tbody>
          {allArts.map((a) => (
            <tr key={a.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
              <td className="px-3 py-2 font-mono text-xs text-stone-700">{a.artikul}</td>
              <td className="px-3 py-2 font-mono text-xs text-stone-600">{a.variantKod}</td>
              <td className="px-3 py-2">
                <div className="flex items-center gap-1.5">
                  <ColorSwatch colorCode={a.cvet_color_code} size={14} />
                  <span className="font-mono text-xs text-stone-700">{a.cvet_color_code ?? "—"}</span>
                  <span className="text-stone-500 text-xs">{a.cvet_nazvanie}</span>
                </div>
              </td>
              <td className="px-3 py-2"><StatusBadge statusId={a.status_id ?? 0} compact /></td>
              <td className="px-3 py-2 font-mono text-[11px] text-stone-500 tabular-nums">
                {a.nomenklatura_wb ?? "—"}
              </td>
              <td className="px-3 py-2 font-mono text-[11px] text-stone-500">
                {a.artikul_ozon ?? "—"}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-stone-700">{a.tovary.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TabSKU({ m }: { m: ModelDetail }) {
  const allSku = m.modeli.flatMap((v) =>
    v.artikuly.flatMap((a) =>
      a.tovary.map((t) => ({
        ...t,
        variantKod: v.kod,
        cvet_color_code: a.cvet_color_code,
      }))
    )
  )

  return (
    <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-stone-200">
        <div className="font-medium text-stone-900">SKU модели</div>
        <div className="text-xs text-stone-500">{allSku.length} SKU</div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-stone-50/80 border-b border-stone-200">
            <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
              <th className="px-3 py-2 font-medium">Баркод</th>
              <th className="px-3 py-2 font-medium">Вариация</th>
              <th className="px-3 py-2 font-medium">Цвет</th>
              <th className="px-3 py-2 font-medium">Размер</th>
              <th className="px-3 py-2 font-medium border-l border-stone-200">WB</th>
              <th className="px-3 py-2 font-medium">OZON</th>
              <th className="px-3 py-2 font-medium">Сайт</th>
              <th className="px-3 py-2 font-medium">Lamoda</th>
            </tr>
          </thead>
          <tbody>
            {allSku.slice(0, 100).map((t) => (
              <tr key={t.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2 font-mono text-xs text-stone-700">{t.barkod}</td>
                <td className="px-3 py-2 font-mono text-xs text-stone-600">{t.variantKod}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1.5">
                    <ColorSwatch colorCode={t.cvet_color_code ?? null} size={14} />
                    <span className="font-mono text-xs">{t.cvet_color_code ?? "—"}</span>
                  </div>
                </td>
                <td className="px-3 py-2 font-mono text-xs">{t.razmer_nazvanie ?? "—"}</td>
                <td className="px-3 py-2 border-l border-stone-100">
                  <StatusBadge statusId={t.status_id ?? 0} compact />
                </td>
                <td className="px-3 py-2"><StatusBadge statusId={t.status_ozon_id ?? 0} compact /></td>
                <td className="px-3 py-2"><StatusBadge statusId={t.status_sayt_id ?? 0} compact /></td>
                <td className="px-3 py-2"><StatusBadge statusId={t.status_lamoda_id ?? 0} compact /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {allSku.length > 100 && (
        <div className="px-3 py-2 text-xs text-stone-400 border-t border-stone-100">
          Показаны первые 100 из {allSku.length}.
        </div>
      )}
    </div>
  )
}

function TabKontent({ m }: { m: ModelDetail }) {
  return (
    <>
      <Section label="Контент">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-x-4 gap-y-4">
            <FieldWrap label="Название на этикетке">
              <ReadField value={m.nazvanie_etiketka} />
            </FieldWrap>
            <FieldWrap label="Название для сайта">
              <ReadField value={m.nazvanie_sayt} />
            </FieldWrap>
          </div>
          <FieldWrap label="Описание для сайта" full>
            <div className="px-2.5 py-1.5 text-sm text-stone-900 whitespace-pre-wrap">
              {m.opisanie_sayt || <span className="text-stone-400 italic">не задано</span>}
            </div>
          </FieldWrap>
          <FieldWrap label="Состав EN" full>
            <ReadField value={m.composition} />
          </FieldWrap>
          <FieldWrap label="Теги" full>
            <ReadField value={m.tegi} />
          </FieldWrap>
        </div>
      </Section>
      <Section label="Ссылки на материалы" hint="Notion-карточка, стратегия, фотоконтент">
        <div className="space-y-3">
          {m.notion_link ? (
            <a
              href={m.notion_link}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 px-3 py-2 bg-stone-50 hover:bg-stone-100 rounded-md text-sm"
            >
              <Link2 className="w-3.5 h-3.5 text-stone-500" />
              <span className="flex-1 truncate text-stone-700">{m.notion_link}</span>
              <ExternalLink className="w-3 h-3 text-stone-400 shrink-0" />
            </a>
          ) : (
            <div className="text-sm text-stone-400 italic">Notion-карточка не задана</div>
          )}
          <FieldWrap label="Упаковка" full>
            <ReadField value={m.upakovka} />
          </FieldWrap>
        </div>
      </Section>
    </>
  )
}

// ─── Matrix list view ──────────────────────────────────────────────────────

function ModeliOsnovaTable({
  rows,
  kategorii,
  onOpen,
}: {
  rows: MatrixRow[]
  kategorii: { id: number; nazvanie: string }[]
  onOpen: (id: number) => void
}) {
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [categoryFilter, setCategoryFilter] = useState("all")
  const [incompleteOnly, setIncompleteOnly] = useState(false)
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())

  const filtered = useMemo(() => {
    let res = rows
    if (statusFilter !== "all") {
      res = res.filter((r) => r.status_id === Number(statusFilter))
    }
    if (categoryFilter !== "all") {
      res = res.filter((r) => r.kategoriya_id === Number(categoryFilter))
    }
    if (incompleteOnly) {
      res = res.filter((r) => r.completeness < 0.85)
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      res = res.filter(
        (r) =>
          r.kod.toLowerCase().includes(q) ||
          (r.nazvanie_sayt ?? "").toLowerCase().includes(q)
      )
    }
    return res
  }, [rows, statusFilter, categoryFilter, incompleteOnly, search])

  const toggleExpand = useCallback((id: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const modelStatuses = CATALOG_STATUSES.filter((s) => s.tip === "model")

  return (
    <div className="px-6 py-4">
      {/* Filter bar */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по коду…"
            className="pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-64"
          />
        </div>
        <div className="h-5 w-px bg-stone-200 mx-1" />
        <div className="flex items-center gap-1">
          {[{ id: "all", label: "Все" }, ...modelStatuses.map((s) => ({ id: String(s.id), label: s.nazvanie }))].map(
            (opt) => (
              <button
                key={opt.id}
                onClick={() => setStatusFilter(opt.id)}
                className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                  statusFilter === opt.id
                    ? "bg-stone-900 text-white"
                    : "text-stone-600 hover:bg-stone-100"
                }`}
              >
                {opt.label}
              </button>
            )
          )}
        </div>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="px-2.5 py-1 text-xs border border-stone-200 rounded-md bg-white outline-none"
        >
          <option value="all">Все категории</option>
          {kategorii.map((k) => (
            <option key={k.id} value={k.id}>
              {k.nazvanie}
            </option>
          ))}
        </select>
        <button
          onClick={() => setIncompleteOnly(!incompleteOnly)}
          className={`px-2.5 py-1 text-xs rounded-md flex items-center gap-1.5 transition-colors ${
            incompleteOnly ? "bg-amber-100 text-amber-800" : "text-stone-600 hover:bg-stone-100"
          }`}
        >
          <AlertCircle className="w-3 h-3" /> Незаполненные
        </button>
        <div className="ml-auto text-xs text-stone-500 tabular-nums">
          {filtered.length} из {rows.length}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-stone-50/80 border-b border-stone-200">
            <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
              <th className="w-8 px-2 py-2.5" />
              <th className="px-3 py-2.5 font-medium">Код</th>
              <th className="px-3 py-2.5 font-medium">Категория</th>
              <th className="px-3 py-2.5 font-medium">Тип / Коллекция</th>
              <th className="px-3 py-2.5 font-medium">Фабрика</th>
              <th className="px-3 py-2.5 font-medium">Статус</th>
              <th className="px-3 py-2.5 font-medium">Заполнено</th>
              <th className="px-3 py-2.5 font-medium text-right">Цв / Арт / SKU</th>
              <th className="px-3 py-2.5 font-medium">Обновлено</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((m) => {
              const canExpand = m.modeli.length >= 2
              const isExpanded = expandedRows.has(m.id)
              return (
                <React.Fragment key={m.id}>
                  <tr
                    className="border-b border-stone-100 hover:bg-stone-50/60 group"
                  >
                    <td className="px-2 py-3">
                      {canExpand ? (
                        <button
                          onClick={() => toggleExpand(m.id)}
                          className="p-0.5 hover:bg-stone-200 rounded"
                        >
                          {isExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5 text-stone-500" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5 text-stone-500" />
                          )}
                        </button>
                      ) : (
                        <span className="text-stone-300 text-xs">·</span>
                      )}
                    </td>
                    <td
                      className="px-3 py-3 cursor-pointer"
                      onClick={() => onOpen(m.id)}
                    >
                      <div className="font-medium text-stone-900 hover:underline font-mono">
                        {m.kod}
                      </div>
                      <div className="text-xs text-stone-500 truncate max-w-[220px]">
                        {m.nazvanie_sayt || (
                          <span className="italic text-stone-400">без названия</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-stone-700">{m.kategoriya ?? "—"}</td>
                    <td className="px-3 py-3">
                      <div className="text-stone-700">{m.kollekciya}</div>
                      <div className="text-[11px] text-stone-400">{m.tip_kollekcii}</div>
                    </td>
                    <td className="px-3 py-3 text-stone-700">{m.fabrika ?? "—"}</td>
                    <td className="px-3 py-3">
                      <StatusBadge statusId={m.status_id ?? 0} />
                    </td>
                    <td className="px-3 py-3">
                      <CompletenessRing value={m.completeness} />
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums text-stone-600">
                      <span className="text-stone-900 font-medium">{m.cveta_cnt}</span>
                      <span className="text-stone-300 mx-1">/</span>
                      <span>{m.artikuly_cnt}</span>
                      <span className="text-stone-300 mx-1">/</span>
                      <span>{m.tovary_cnt}</span>
                    </td>
                    <td className="px-3 py-3 text-stone-500 text-xs">
                      {relativeDate(m.updated_at)}
                    </td>
                  </tr>
                  {isExpanded &&
                    m.modeli.map((v) => (
                      <tr
                        key={`v-${v.id}`}
                        className="bg-stone-50/40 border-b border-stone-100 text-xs"
                      >
                        <td />
                        <td className="pl-3 py-2 pr-3">
                          <div className="flex items-center gap-2">
                            <div className="w-4 h-px bg-stone-300" />
                            <span className="font-medium text-stone-800 font-mono">{v.kod}</span>
                          </div>
                          <div className="text-[11px] text-stone-500 ml-6 mt-0.5 truncate max-w-[200px]">
                            {v.nazvanie}
                          </div>
                        </td>
                        <td className="px-3 py-2 text-stone-400">—</td>
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-1 text-stone-500">
                            <Building2 className="w-3 h-3 text-stone-400" />
                            {v.importer_short ?? "—"}
                          </div>
                        </td>
                        <td className="px-3 py-2 font-mono text-[11px] text-stone-500">
                          {v.artikul_modeli}
                        </td>
                        <td className="px-3 py-2">
                          <StatusBadge statusId={v.status_id ?? 0} compact />
                        </td>
                        <td />
                        <td className="px-3 py-2 text-right tabular-nums text-stone-600">
                          <span className="text-stone-300">—</span>
                          <span className="text-stone-300 mx-1">/</span>
                          <span className="text-stone-700 font-medium">{v.artikuly_cnt}</span>
                          <span className="text-stone-300 mx-1">/</span>
                          <span>{v.tovary_cnt}</span>
                        </td>
                        <td className="px-3 py-2 text-stone-400">RU: {v.rossiyskiy_razmer ?? "—"}</td>
                      </tr>
                    ))}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-3 text-xs text-stone-500 flex items-center gap-2">
        <Info className="w-3.5 h-3.5 shrink-0" />
        <span>Стрелка ▶ раскрывает вариации. Клик по коду — карточка модели.</span>
      </div>
    </div>
  )
}

// ─── Artikuly registry tab ─────────────────────────────────────────────────

function ArtikulyTable() {
  const { data, isLoading } = useQuery({
    queryKey: ["artikuly-registry"],
    queryFn: fetchArtikulyRegistry,
    staleTime: 5 * 60 * 1000,
  })
  const [search, setSearch] = useState("")

  const filtered = useMemo(() => {
    if (!data) return []
    if (!search.trim()) return data
    const q = search.trim().toLowerCase()
    return data.filter(
      (a) =>
        a.artikul.toLowerCase().includes(q) ||
        (a.model_osnova_kod ?? "").toLowerCase().includes(q) ||
        (a.cvet_color_code ?? "").toLowerCase().includes(q)
    )
  }, [data, search])

  if (isLoading) {
    return <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
  }

  return (
    <div className="px-6 py-4">
      <div className="flex items-center gap-2 mb-4">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Артикул, модель, цвет…"
            className="pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-72"
          />
        </div>
        <div className="ml-auto text-xs text-stone-500 tabular-nums">
          {filtered.length} из {data?.length ?? 0}
        </div>
      </div>
      <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-stone-50/80 border-b border-stone-200">
            <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
              <th className="px-3 py-2.5 font-medium">Артикул</th>
              <th className="px-3 py-2.5 font-medium">Модель</th>
              <th className="px-3 py-2.5 font-medium">Вариация</th>
              <th className="px-3 py-2.5 font-medium">Цвет</th>
              <th className="px-3 py-2.5 font-medium">Статус</th>
              <th className="px-3 py-2.5 font-medium">WB номенкл.</th>
              <th className="px-3 py-2.5 font-medium">OZON</th>
              <th className="px-3 py-2.5 font-medium text-right">SKU</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 100).map((a) => (
              <tr key={a.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2.5 font-mono text-xs text-stone-900">{a.artikul}</td>
                <td className="px-3 py-2.5 font-medium text-stone-900 font-mono text-xs">{a.model_osnova_kod ?? "—"}</td>
                <td className="px-3 py-2.5 font-mono text-xs text-stone-600">{a.model_kod ?? "—"}</td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-1.5">
                    <ColorSwatch colorCode={a.cvet_color_code} size={14} />
                    <span className="font-mono text-xs text-stone-700">{a.cvet_color_code ?? "—"}</span>
                    <span className="text-stone-500 text-xs">{a.cvet_nazvanie}</span>
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  <StatusBadge statusId={a.status_id ?? 0} compact />
                </td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-stone-500 tabular-nums">
                  {a.nomenklatura_wb ?? "—"}
                </td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-stone-500">
                  {a.artikul_ozon ?? "—"}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums text-stone-700">{a.tovary_cnt}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length > 100 && (
          <div className="px-3 py-2 text-xs text-stone-400 border-t border-stone-100">
            Показаны первые 100 из {filtered.length}.
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Tovary registry tab ───────────────────────────────────────────────────

function TovaryTable() {
  const { data, isLoading } = useQuery({
    queryKey: ["tovary-registry"],
    queryFn: fetchTovaryRegistry,
    staleTime: 5 * 60 * 1000,
  })
  const [search, setSearch] = useState("")
  const [channelFilter, setChannelFilter] = useState<"all" | "wb" | "ozon" | "sayt" | "lamoda">("all")
  const [statusFilter, setStatusFilter] = useState<"all" | number>("all")
  const [visibleCount, setVisibleCount] = useState(100)

  const productStatuses = CATALOG_STATUSES.filter((s) => s.tip === "product")

  const filtered = useMemo(() => {
    if (!data) return []
    let res = data
    if (channelFilter === "wb") res = res.filter((t) => t.status_id !== null)
    else if (channelFilter === "ozon") res = res.filter((t) => t.status_ozon_id !== null)
    else if (channelFilter === "sayt") res = res.filter((t) => t.status_sayt_id !== null)
    else if (channelFilter === "lamoda") res = res.filter((t) => t.status_lamoda_id !== null)
    if (statusFilter !== "all") {
      res = res.filter((t) =>
        t.status_id === statusFilter ||
        t.status_ozon_id === statusFilter ||
        t.status_sayt_id === statusFilter ||
        t.status_lamoda_id === statusFilter
      )
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      res = res.filter(
        (t) =>
          t.barkod.includes(q) ||
          (t.model_osnova_kod ?? "").toLowerCase().includes(q) ||
          (t.artikul ?? "").toLowerCase().includes(q)
      )
    }
    return res
  }, [data, channelFilter, statusFilter, search])

  const visible = filtered.slice(0, visibleCount)

  const CHANNELS = [
    { id: "all", label: "Все" },
    { id: "wb", label: "WB" },
    { id: "ozon", label: "Ozon" },
    { id: "sayt", label: "Сайт" },
    { id: "lamoda", label: "Lamoda" },
  ] as const

  if (isLoading) {
    return <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
  }

  return (
    <div className="px-6 py-4">
      {/* Channel tabs */}
      <div className="flex items-center gap-1 mb-3">
        {CHANNELS.map((c) => (
          <button
            key={c.id}
            onClick={() => { setChannelFilter(c.id as typeof channelFilter); setVisibleCount(100) }}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              channelFilter === c.id
                ? "bg-stone-900 text-white"
                : "text-stone-600 hover:bg-stone-100"
            }`}
          >
            {c.label}
          </button>
        ))}
        <div className="h-4 w-px bg-stone-200 mx-1" />
        <select
          value={statusFilter === "all" ? "all" : String(statusFilter)}
          onChange={(e) => {
            setStatusFilter(e.target.value === "all" ? "all" : Number(e.target.value))
            setVisibleCount(100)
          }}
          className="px-2.5 py-1 text-xs border border-stone-200 rounded-md bg-white outline-none"
        >
          <option value="all">Все статусы</option>
          {productStatuses.map((s) => (
            <option key={s.id} value={s.id}>{s.nazvanie}</option>
          ))}
        </select>
      </div>

      {/* Search + count */}
      <div className="flex items-center gap-2 mb-4">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setVisibleCount(100) }}
            placeholder="Баркод, модель, артикул…"
            className="pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-72"
          />
        </div>
        <div className="ml-auto text-xs text-stone-500 tabular-nums">
          {filtered.length} из {data?.length ?? 0}
        </div>
      </div>

      <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-stone-50/80 border-b border-stone-200">
            <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
              <th className="px-3 py-2.5 font-medium">Баркод</th>
              <th className="px-3 py-2.5 font-medium">Модель</th>
              <th className="px-3 py-2.5 font-medium">Вариация</th>
              <th className="px-3 py-2.5 font-medium">Цвет</th>
              <th className="px-3 py-2.5 font-medium">Размер</th>
              <th className="px-3 py-2.5 font-medium border-l border-stone-200">WB</th>
              <th className="px-3 py-2.5 font-medium">OZON</th>
              <th className="px-3 py-2.5 font-medium">Сайт</th>
              <th className="px-3 py-2.5 font-medium">Lamoda</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((t) => (
              <tr key={t.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2.5 font-mono text-xs text-stone-700">{t.barkod}</td>
                <td className="px-3 py-2.5 font-medium text-stone-900 font-mono text-xs">{t.model_osnova_kod ?? "—"}</td>
                <td className="px-3 py-2.5 font-mono text-xs text-stone-600">{t.model_kod ?? "—"}</td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-1.5">
                    <ColorSwatch colorCode={t.cvet_color_code} size={14} />
                    <span className="font-mono text-xs">{t.cvet_color_code ?? "—"}</span>
                  </div>
                </td>
                <td className="px-3 py-2.5 font-mono text-xs">{t.razmer ?? "—"}</td>
                <td className="px-3 py-2.5 border-l border-stone-100">
                  <StatusBadge statusId={t.status_id ?? 0} compact />
                </td>
                <td className="px-3 py-2.5">
                  <StatusBadge statusId={t.status_ozon_id ?? 0} compact />
                </td>
                <td className="px-3 py-2.5">
                  <StatusBadge statusId={t.status_sayt_id ?? 0} compact />
                </td>
                <td className="px-3 py-2.5">
                  <StatusBadge statusId={t.status_lamoda_id ?? 0} compact />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length > visibleCount && (
          <div className="px-3 py-3 border-t border-stone-100 flex items-center justify-between">
            <span className="text-xs text-stone-400">Показано {visibleCount} из {filtered.length}</span>
            <button
              onClick={() => setVisibleCount((v) => v + 100)}
              className="text-xs text-stone-700 hover:text-stone-900 px-3 py-1 hover:bg-stone-100 rounded-md transition-colors"
            >
              Показать ещё 100
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Main MatrixPage ───────────────────────────────────────────────────────

export function MatrixPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [listTab, setListTab] = useState<"modeli_osnova" | "artikuly" | "tovary">("modeli_osnova")

  const modelIdParam = searchParams.get("id")
  const modelId = modelIdParam ? Number(modelIdParam) : null

  const openModel = useCallback(
    (id: number) => setSearchParams({ id: String(id) }),
    [setSearchParams]
  )
  const closeModel = useCallback(
    () => setSearchParams({}),
    [setSearchParams]
  )

  const matrixQ = useQuery({
    queryKey: ["matrix-list"],
    queryFn: fetchMatrixList,
    staleTime: 3 * 60 * 1000,
    enabled: !modelId,
  })

  const kategoriiQ = useQuery({
    queryKey: ["kategorii"],
    queryFn: fetchKategorii,
    staleTime: 10 * 60 * 1000,
  })

  // Prefetch matrix when on model card
  const matrixPrefetch = useQuery({
    queryKey: ["matrix-list"],
    queryFn: fetchMatrixList,
    staleTime: 3 * 60 * 1000,
    enabled: !!modelId,
  })

  if (modelId) {
    return <ModelCard modelId={modelId} onBack={closeModel} />
  }

  const rows = matrixQ.data ?? []
  const kategorii = kategoriiQ.data ?? []
  const totalArts = rows.reduce((s, r) => s + r.artikuly_cnt, 0)
  const totalSku = rows.reduce((s, r) => s + r.tovary_cnt, 0)

  const LIST_TABS = [
    { id: "modeli_osnova", label: "Базовые модели", count: rows.length },
    { id: "artikuly", label: "Артикулы (реестр)", count: totalArts },
    { id: "tovary", label: "SKU (реестр)", count: totalSku },
  ] as const

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-6 pb-3 shrink-0">
        <div className="flex items-end justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1">Каталог</div>
            <h1
              className="text-3xl text-stone-900 cat-font-serif"
            >
              Матрица товаров
            </h1>
            <div className="text-sm text-stone-500 mt-1">
              {rows.length} моделей · {totalArts} артикулов · {totalSku} SKU
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5">
              <Plus className="w-3.5 h-3.5" /> Новая модель
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-stone-200 px-6 shrink-0">
        <div className="flex gap-1">
          {LIST_TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setListTab(t.id as typeof listTab)}
              className={`relative px-3 py-2.5 text-sm transition-colors ${
                listTab === t.id
                  ? "text-stone-900 font-medium"
                  : "text-stone-500 hover:text-stone-800"
              }`}
            >
              {t.label}
              <span className="ml-1.5 text-[10px] tabular-nums text-stone-400">{t.count}</span>
              {listTab === t.id && (
                <span className="absolute bottom-0 left-0 right-0 h-px bg-stone-900" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {matrixQ.isLoading && listTab === "modeli_osnova" && (
          <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
        )}
        {matrixQ.error && (
          <div className="px-6 py-8 text-sm text-red-500">
            Ошибка загрузки: {String(matrixQ.error)}
          </div>
        )}
        {listTab === "modeli_osnova" && !matrixQ.isLoading && !matrixQ.error && (
          <ModeliOsnovaTable rows={rows} kategorii={kategorii} onOpen={openModel} />
        )}
        {listTab === "artikuly" && <ArtikulyTable />}
        {listTab === "tovary" && <TovaryTable />}
      </div>
    </div>
  )
}
