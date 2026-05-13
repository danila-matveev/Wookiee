import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"
import { Plus, Search } from "lucide-react"
import {
  fetchSkleykiWb,
  fetchSkleykiOzon,
  findSkleykiByBarkod,
  createSkleyka,
  type SkleykaRow,
} from "@/lib/catalog/service"
import { RefModal, type RefFieldDef } from "@/components/catalog/ui/ref-modal"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { CellText } from "@/components/catalog/ui/cell-text"
import { relativeDate } from "@/lib/catalog/color-utils"
import { SkleykaCard } from "./skleyka-card"

type ChannelFilter = "all" | "wb" | "ozon"

const MAX_SKU = 30

function fillingColor(pct: number): string {
  // <10/30 (33%) — red, <20/30 (67%) — amber, <30/30 — blue, =30/30 green
  if (pct >= 1) return "#10B981" // green
  if (pct >= 0.67) return "#3B82F6" // blue
  if (pct >= 0.33) return "#F59E0B" // amber
  return "#EF4444" // red
}

function FillingBar({ count }: { count: number }) {
  const pct = Math.min(count / MAX_SKU, 1)
  const color = fillingColor(pct)
  return (
    <div className="flex items-center gap-2">
      <div className="w-28 h-1.5 bg-stone-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${Math.min(100, pct * 100)}%`, background: color }}
        />
      </div>
      <span className="text-xs tabular-nums text-stone-600 font-medium w-12 shrink-0">
        {count}/{MAX_SKU}
      </span>
    </div>
  )
}

function ChannelBadge({ channel }: { channel: "wb" | "ozon" }) {
  if (channel === "wb") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium bg-pink-50 text-pink-700 ring-1 ring-inset ring-pink-600/20">
        <span className="w-1.5 h-1.5 rounded-full bg-pink-500" />
        WB
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/20">
      <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
      OZON
    </span>
  )
}

interface SkleykiListProps {
  onOpen: (channel: "wb" | "ozon", id: number) => void
  onCreateClick: () => void
}

function SkleykiList({ onOpen, onCreateClick }: SkleykiListProps) {
  const wbQ = useQuery({
    queryKey: ["skleyki-wb", "with-counts"],
    queryFn: fetchSkleykiWb,
    staleTime: 3 * 60 * 1000,
  })
  const ozonQ = useQuery({
    queryKey: ["skleyki-ozon", "with-counts"],
    queryFn: fetchSkleykiOzon,
    staleTime: 3 * 60 * 1000,
  })

  const [channelFilter, setChannelFilter] = useState<ChannelFilter>("all")
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "empty" | "overflow">("all")
  const [search, setSearch] = useState("")

  const all: SkleykaRow[] = useMemo(() => {
    const wb = (wbQ.data ?? []).map((s) => ({ ...s, channel: "wb" as const }))
    const ozon = (ozonQ.data ?? []).map((s) => ({ ...s, channel: "ozon" as const }))
    return [...wb, ...ozon]
  }, [wbQ.data, ozonQ.data])

  // Search by barkod cross-reference (when query is digits-heavy)
  const searchTrim = search.trim()
  const looksLikeBarkod = searchTrim.length >= 4 && /^\d+$/.test(searchTrim)
  const barkodWbQ = useQuery({
    queryKey: ["skleyki-by-barkod", "wb", searchTrim],
    queryFn: () => findSkleykiByBarkod(searchTrim, "wb"),
    staleTime: 60 * 1000,
    enabled: looksLikeBarkod,
  })
  const barkodOzonQ = useQuery({
    queryKey: ["skleyki-by-barkod", "ozon", searchTrim],
    queryFn: () => findSkleykiByBarkod(searchTrim, "ozon"),
    staleTime: 60 * 1000,
    enabled: looksLikeBarkod,
  })

  const filtered = useMemo(() => {
    let res = all
    if (channelFilter !== "all") res = res.filter((s) => s.channel === channelFilter)

    if (statusFilter === "empty") res = res.filter((s) => (s.count_tovary ?? 0) === 0)
    else if (statusFilter === "active") res = res.filter((s) => (s.count_tovary ?? 0) > 0 && (s.count_tovary ?? 0) <= MAX_SKU)
    else if (statusFilter === "overflow") res = res.filter((s) => (s.count_tovary ?? 0) > MAX_SKU)

    const q = searchTrim.toLowerCase()
    if (q) {
      const wbIds = barkodWbQ.data
      const ozonIds = barkodOzonQ.data
      res = res.filter((s) => {
        const nameMatch = s.nazvanie.toLowerCase().includes(q)
        if (nameMatch) return true
        if (looksLikeBarkod) {
          if (s.channel === "wb" && wbIds?.has(s.id)) return true
          if (s.channel === "ozon" && ozonIds?.has(s.id)) return true
        }
        return false
      })
    }
    return res
  }, [all, channelFilter, statusFilter, searchTrim, barkodWbQ.data, barkodOzonQ.data, looksLikeBarkod])

  const counts = useMemo(() => {
    const active = all.filter((s) => (s.count_tovary ?? 0) > 0).length
    const empty = all.filter((s) => (s.count_tovary ?? 0) === 0).length
    return { total: all.length, active, empty }
  }, [all])

  const isLoading = wbQ.isLoading || ozonQ.isLoading
  const error = wbQ.error ?? ozonQ.error

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-6 pb-3 shrink-0">
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1">Каталог</div>
            <h1 className="text-3xl text-stone-900 cat-font-serif italic">Склейки маркетплейсов</h1>
            <div className="text-sm text-stone-500 mt-1 max-w-2xl">
              До {MAX_SKU} SKU в склейке. {counts.active} активных, {counts.empty} пустых.
            </div>
          </div>
          <button
            type="button"
            onClick={onCreateClick}
            className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" /> Создать склейку
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="px-6 pb-3 flex items-center gap-3 shrink-0 flex-wrap">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по названию или баркоду…"
            className="pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400 w-72"
          />
        </div>

        <span className="text-xs text-stone-500 ml-1">Канал:</span>
        {(
          [
            { id: "all", label: "Все" },
            { id: "wb", label: "WB" },
            { id: "ozon", label: "OZON" },
          ] as const
        ).map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => setChannelFilter(opt.id)}
            className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
              channelFilter === opt.id
                ? "bg-stone-900 text-white"
                : "text-stone-600 hover:bg-stone-100"
            }`}
          >
            {opt.label}
          </button>
        ))}

        <span className="text-xs text-stone-500 ml-3">Статус:</span>
        {(
          [
            { id: "all", label: "Все" },
            { id: "active", label: "Активные" },
            { id: "empty", label: "Пустые" },
            { id: "overflow", label: `> ${MAX_SKU}` },
          ] as const
        ).map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => setStatusFilter(opt.id)}
            className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
              statusFilter === opt.id
                ? "bg-stone-900 text-white"
                : "text-stone-600 hover:bg-stone-100"
            }`}
          >
            {opt.label}
          </button>
        ))}

        <div className="ml-auto text-xs text-stone-500 tabular-nums">
          {filtered.length} из {all.length}
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 pb-6">
        {isLoading && <div className="text-sm text-stone-400">Загрузка…</div>}
        {error && <div className="text-sm text-red-500">Ошибка загрузки склеек</div>}
        {!isLoading && !error && (
          <div className="bg-white rounded-lg border border-stone-200 overflow-x-auto">
            {/* W10.2 — min-w даёт горизонтальный скролл при недостатке viewport-а. */}
            <table className="w-full text-sm min-w-[1100px]">
              <thead className="bg-stone-50/80 border-b border-stone-200">
                <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
                  <th className="px-3 py-2.5 font-medium">Название</th>
                  <th className="px-3 py-2.5 font-medium">Канал</th>
                  <th className="px-3 py-2.5 font-medium">Заполненность</th>
                  <th className="px-3 py-2.5 font-medium text-right">Кол-во SKU</th>
                  <th className="px-3 py-2.5 font-medium">Создана</th>
                  <th className="px-3 py-2.5 font-medium">Статус</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => {
                  const cnt = s.count_tovary ?? 0
                  const status = cnt === 0
                    ? { nazvanie: "Пустая", color: "gray" as const }
                    : cnt > MAX_SKU
                      ? { nazvanie: "Переполнена", color: "red" as const }
                      : cnt >= MAX_SKU
                        ? { nazvanie: "Полная", color: "green" as const }
                        : { nazvanie: "Активна", color: "blue" as const }
                  return (
                    <tr
                      key={`${s.channel}-${s.id}`}
                      onClick={() => onOpen(s.channel!, s.id)}
                      className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60 cursor-pointer"
                    >
                      <td className="px-3 py-3">
                        <CellText className="font-medium text-stone-900" title={s.nazvanie ?? ""}>
                          {s.nazvanie}
                        </CellText>
                        {s.importer_nazvanie && (
                          <CellText className="text-[11px] text-stone-400" title={s.importer_nazvanie}>
                            {s.importer_nazvanie}
                          </CellText>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <ChannelBadge channel={s.channel ?? "wb"} />
                      </td>
                      <td className="px-3 py-3">
                        <FillingBar count={cnt} />
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums text-stone-700">{cnt}</td>
                      <td className="px-3 py-3 text-stone-500 text-xs">{relativeDate(s.created_at)}</td>
                      <td className="px-3 py-3">
                        <StatusBadge status={status} compact />
                      </td>
                    </tr>
                  )
                })}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-3 py-8 text-center text-sm text-stone-400 italic">
                      Ничего не найдено
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Create modal ─────────────────────────────────────────────────────────

interface CreateModalProps {
  onCancel: () => void
  onCreated: (channel: "wb" | "ozon", id: number) => void
}

function CreateSkleykaModal({ onCancel, onCreated }: CreateModalProps) {
  const fields: RefFieldDef[] = [
    {
      key: "nazvanie",
      label: "Название склейки",
      type: "text",
      required: true,
      placeholder: "Например: Audrey · палитра нейтрал",
      full: true,
    },
    {
      key: "channel",
      label: "Канал",
      type: "select",
      required: true,
      options: [
        { value: "wb", label: "Wildberries" },
        { value: "ozon", label: "Ozon" },
      ],
      full: true,
      hint: "После создания SKU добавляются из реестра /catalog/tovary через bulk-действие.",
    },
  ]

  return (
    <RefModal
      title="Новая склейка"
      fields={fields}
      onCancel={onCancel}
      saveLabel="Создать"
      onSave={async (values) => {
        const nazvanie = String(values.nazvanie ?? "").trim()
        const channel = values.channel as "wb" | "ozon"
        if (!nazvanie || !channel) return
        const { id } = await createSkleyka(nazvanie, channel)
        onCreated(channel, id)
      }}
    />
  )
}

// ─── Page wrapper ─────────────────────────────────────────────────────────

export function SkleykiPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const idParam = searchParams.get("id")
  const channelParam = searchParams.get("kanal") as "wb" | "ozon" | null
  const id = idParam ? Number(idParam) : null
  const channel = channelParam === "wb" || channelParam === "ozon" ? channelParam : null

  const [createOpen, setCreateOpen] = useState(false)

  const openSkleyka = (ch: "wb" | "ozon", sId: number) => {
    setSearchParams({ kanal: ch, id: String(sId) })
  }
  const closeSkleyka = () => setSearchParams({})

  if (id != null && channel) {
    return <SkleykaCard id={id} channel={channel} onBack={closeSkleyka} />
  }

  return (
    <>
      <SkleykiList onOpen={openSkleyka} onCreateClick={() => setCreateOpen(true)} />
      {createOpen && (
        <CreateSkleykaModal
          onCancel={() => setCreateOpen(false)}
          onCreated={(ch, sId) => {
            setCreateOpen(false)
            openSkleyka(ch, sId)
          }}
        />
      )}
    </>
  )
}
