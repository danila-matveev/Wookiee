import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { fetchRnpModels } from "@/api/rnp"
import { Button } from "@/components/ui/button"

export const PHASE_COLORS: Record<string, string> = {
  norm: "#185FA5", decline: "#E24B4A", recovery: "#1D9E75",
}

function mondayOf(d: Date): string {
  const day = d.getDay()
  const diff = (day === 0 ? -6 : 1 - day)
  const mon = new Date(d)
  mon.setDate(d.getDate() + diff)
  return mon.toISOString().slice(0, 10)
}

function sundayOf(d: Date): string {
  const mon = new Date(mondayOf(d))
  mon.setDate(mon.getDate() + 6)
  return mon.toISOString().slice(0, 10)
}

function weeksAgo(n: number): { from: string; to: string } {
  const today = new Date()
  const sun = new Date(sundayOf(new Date(today.setDate(today.getDate() - 7))))
  const mon = new Date(sun)
  mon.setDate(sun.getDate() - (n - 1) * 7 - 6)
  return { from: mon.toISOString().slice(0, 10), to: sun.toISOString().slice(0, 10) }
}

interface RnpFiltersProps {
  onApply: (params: { model: string; dateFrom: string; dateTo: string }) => void
  loading: boolean
}

export function RnpFilters({ onApply, loading }: RnpFiltersProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [models, setModels] = useState<string[]>([])

  const model    = searchParams.get("model") ?? ""
  const dateFrom = searchParams.get("from")  ?? weeksAgo(8).from
  const dateTo   = searchParams.get("to")    ?? weeksAgo(8).to

  useEffect(() => {
    fetchRnpModels().then(r => setModels(r.models)).catch(() => {})
  }, [])

  function setParam(key: string, value: string) {
    const p = new URLSearchParams(searchParams)
    p.set(key, value)
    setSearchParams(p)
  }

  function applyPreset(n: number) {
    const { from, to } = weeksAgo(n)
    const p = new URLSearchParams(searchParams)
    p.set("from", from); p.set("to", to)
    setSearchParams(p)
  }

  function handleApply() {
    if (!model) return
    onApply({ model, dateFrom, dateTo })
  }

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Модель</label>
        <select
          className="h-9 w-44 rounded-md border border-input bg-background px-3 text-sm"
          value={model}
          onChange={e => setParam("model", e.target.value)}
        >
          <option value="">Выберите модель</option>
          {models.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Период</label>
        <div className="flex gap-1">
          {[4, 8, 12].map(n => (
            <Button key={n} variant="outline" size="sm" onClick={() => applyPreset(n)}>
              {n} нед.
            </Button>
          ))}
          <input
            type="date"
            className="h-9 rounded-md border border-input px-2 text-sm"
            value={dateFrom}
            onChange={e => setParam("from", e.target.value)}
          />
          <span className="self-center text-muted-foreground">—</span>
          <input
            type="date"
            className="h-9 rounded-md border border-input px-2 text-sm"
            value={dateTo}
            onChange={e => setParam("to", e.target.value)}
          />
        </div>
      </div>

      <Button onClick={handleApply} disabled={!model || loading}>
        {loading ? "Загрузка..." : "Обновить"}
      </Button>
    </div>
  )
}
