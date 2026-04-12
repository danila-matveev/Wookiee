import { Star } from "lucide-react"
import { StatusPill } from "@/components/shared/status-pill"
import { formatNumber } from "@/lib/format"
import type { CatalogModel } from "@/types/catalog"

interface CatalogTableProps {
  models: CatalogModel[]
}

const columns = [
  { key: "img", label: "", width: "w-[48px]" },
  { key: "name", label: "Модель" },
  { key: "category", label: "Категория" },
  { key: "collection", label: "Коллекция" },
  { key: "skus", label: "SKU" },
  { key: "price", label: "Цена" },
  { key: "rating", label: "Рейтинг" },
  { key: "orders", label: "Заказы" },
  { key: "status", label: "Статус" },
] as const

export function CatalogTable({ models }: CatalogTableProps) {
  return (
    <div className="bg-card border border-border rounded-[10px] overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border/[0.22]">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`text-left text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold px-3.5 py-2.5 ${"width" in col ? col.width : ""}`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {models.map((model) => (
            <tr
              key={model.id}
              className="border-b border-border/[0.22] hover:bg-bg-hover transition-colors cursor-pointer"
            >
              <td className="px-3.5 py-2.5 text-[20px]">{model.img}</td>
              <td className="px-3.5 py-2.5 text-[13px] font-semibold">{model.name}</td>
              <td className="px-3.5 py-2.5 text-[13px] text-muted-foreground">{model.category}</td>
              <td className="px-3.5 py-2.5">
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-accent-soft text-accent">
                  {model.collection}
                </span>
              </td>
              <td className="px-3.5 py-2.5 text-[13px] font-mono">{model.skus}</td>
              <td className="px-3.5 py-2.5 text-[13px] font-mono">{model.price}</td>
              <td className="px-3.5 py-2.5 text-[13px]">
                {model.rating !== null ? (
                  <span className="flex items-center gap-1">
                    <Star size={13} className="text-yellow-500 fill-yellow-500" />
                    {model.rating}
                  </span>
                ) : (
                  <span className="text-muted-foreground">&mdash;</span>
                )}
              </td>
              <td className="px-3.5 py-2.5 text-[13px] font-mono">
                {model.orders > 0 ? formatNumber(model.orders) : <span className="text-muted-foreground">&mdash;</span>}
              </td>
              <td className="px-3.5 py-2.5">
                <StatusPill
                  label={model.status === "active" ? "Активен" : "Черновик"}
                  color={model.status === "active" ? "var(--wk-green)" : "var(--text-dim)"}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
