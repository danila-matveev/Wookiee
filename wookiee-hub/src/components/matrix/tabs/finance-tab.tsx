import { useState } from "react";
import { useApiQuery } from "@/hooks/use-api-query";
import { matrixApi, type FinanceResponse, type FinanceChannel, type FinanceDelta, type ExpenseItem } from "@/lib/matrix-api";
import { cn } from "@/lib/utils";

interface FinanceTabProps {
  entityType: string;
  entityId: number;
}

type ChannelFilter = "all" | "wb" | "ozon";

function fmtRub(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} млн`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)} тыс`;
  return n.toFixed(0);
}

function fmtPct(n: number): string {
  return `${n.toFixed(1)}%`;
}

function DeltaArrow({ value, suffix = "" }: { value: number | null; suffix?: string }) {
  if (value == null) return null;
  const color = value > 0 ? "text-green-600" : value < 0 ? "text-red-600" : "text-muted-foreground";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "→";
  return <span className={cn("text-sm", color)}>{arrow} {fmtRub(Math.abs(value))}{suffix}</span>;
}

function KpiCard({ title, mainValue, subValue, delta }: {
  title: string;
  mainValue: string;
  subValue?: string;
  delta?: number | null;
}) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className="mt-1 text-2xl font-bold">{mainValue}</p>
      {subValue && <p className="text-sm text-muted-foreground">{subValue}</p>}
      {delta != null && <DeltaArrow value={delta} />}
    </div>
  );
}

const EXPENSE_LABELS: Record<string, string> = {
  commission: "Комиссия",
  logistics: "Логистика",
  cost_price: "Себестоимость",
  advertising: "Реклама",
  storage: "Хранение",
  nds: "НДС",
  other: "Ост. расходы",
};

const EXPENSE_ORDER = ["commission", "logistics", "cost_price", "advertising", "storage", "nds", "other"];

function ExpenseTable({ expenses }: { expenses: Record<string, ExpenseItem> }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left text-muted-foreground">
          <th className="py-2">Расходы</th>
          <th className="py-2 text-right">Сумма</th>
          <th className="py-2 text-right">%</th>
          <th className="py-2 text-right">Δ</th>
          <th className="py-2 text-right">Δ%</th>
        </tr>
      </thead>
      <tbody>
        {EXPENSE_ORDER.map((key) => {
          const item = expenses[key];
          if (!item) return null;
          return (
            <tr key={key} className="border-b">
              <td className="py-2">{EXPENSE_LABELS[key] ?? key}</td>
              <td className="py-2 text-right font-mono">{fmtRub(item.value)}</td>
              <td className="py-2 text-right font-mono">{fmtPct(item.pct)}</td>
              <td className="py-2 text-right">
                <DeltaArrow value={item.delta_value} />
              </td>
              <td className="py-2 text-right">
                <DeltaArrow value={item.delta_pct} suffix=" п.п." />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function combineChannels(wb: FinanceChannel | null, ozon: FinanceChannel | null): FinanceChannel | null {
  if (!wb && !ozon) return null;
  if (!wb) return ozon;
  if (!ozon) return wb;

  const totalRev = wb.revenue_before_spp + ozon.revenue_before_spp;

  // Combine expenses
  const expenses: Record<string, ExpenseItem> = {};
  for (const key of EXPENSE_ORDER) {
    const wbE = wb.expenses[key];
    const ozE = ozon.expenses[key];
    const val = (wbE?.value ?? 0) + (ozE?.value ?? 0);
    const pct = totalRev > 0 ? (val / totalRev) * 100 : 0;
    const dv = (wbE?.delta_value ?? 0) + (ozE?.delta_value ?? 0);
    expenses[key] = { value: val, pct, delta_value: dv, delta_pct: null };
  }

  const totalMargin = wb.margin + ozon.margin;

  return {
    revenue_before_spp: totalRev,
    revenue_after_spp: wb.revenue_after_spp + ozon.revenue_after_spp,
    margin: totalMargin,
    margin_pct: totalRev > 0 ? (totalMargin / totalRev) * 100 : 0,
    orders_count: wb.orders_count + ozon.orders_count,
    orders_sum: wb.orders_sum + ozon.orders_sum,
    sales_count: wb.sales_count + ozon.sales_count,
    sales_sum: wb.sales_sum + ozon.sales_sum,
    avg_check_before_spp: totalRev / (wb.sales_count + ozon.sales_count || 1),
    avg_check_after_spp: (wb.revenue_after_spp + ozon.revenue_after_spp) / (wb.sales_count + ozon.sales_count || 1),
    spp_pct: totalRev > 0 ? (1 - (wb.revenue_after_spp + ozon.revenue_after_spp) / totalRev) * 100 : 0,
    buyout_pct: (wb.orders_count + ozon.orders_count) > 0
      ? ((wb.sales_count + ozon.sales_count) / (wb.orders_count + ozon.orders_count)) * 100
      : 0,
    returns_count: wb.returns_count + ozon.returns_count,
    returns_pct: (wb.orders_count + ozon.orders_count) > 0
      ? ((wb.returns_count + ozon.returns_count) / (wb.orders_count + ozon.orders_count)) * 100
      : 0,
    expenses,
    drr: {
      total: (wb.orders_sum + ozon.orders_sum) > 0
        ? ((wb.drr.total * wb.orders_sum + ozon.drr.total * ozon.orders_sum) / (wb.orders_sum + ozon.orders_sum))
        : 0,
      internal: (wb.orders_sum + ozon.orders_sum) > 0
        ? ((wb.drr.internal * wb.orders_sum + ozon.drr.internal * ozon.orders_sum) / (wb.orders_sum + ozon.orders_sum))
        : 0,
      external: (wb.orders_sum + ozon.orders_sum) > 0
        ? ((wb.drr.external * wb.orders_sum + ozon.drr.external * ozon.orders_sum) / (wb.orders_sum + ozon.orders_sum))
        : 0,
    },
  };
}

function combineDelta(wb: FinanceDelta | null, ozon: FinanceDelta | null): FinanceDelta | null {
  if (!wb && !ozon) return null;
  if (!wb) return ozon;
  if (!ozon) return wb;
  return {
    revenue_before_spp: wb.revenue_before_spp + ozon.revenue_before_spp,
    revenue_after_spp: wb.revenue_after_spp + ozon.revenue_after_spp,
    margin: wb.margin + ozon.margin,
    margin_pct: wb.margin_pct + ozon.margin_pct, // approximate sum of deltas
    orders_count: wb.orders_count + ozon.orders_count,
    orders_sum: wb.orders_sum + ozon.orders_sum,
    sales_count: wb.sales_count + ozon.sales_count,
    avg_check_before_spp: (wb.avg_check_before_spp + ozon.avg_check_before_spp) / 2,
    avg_check_after_spp: (wb.avg_check_after_spp + ozon.avg_check_after_spp) / 2,
    spp_pct: (wb.spp_pct + ozon.spp_pct) / 2,
    buyout_pct: (wb.buyout_pct + ozon.buyout_pct) / 2,
    returns_count: wb.returns_count + ozon.returns_count,
    returns_pct: (wb.returns_pct + ozon.returns_pct) / 2,
    drr_total: (wb.drr_total + ozon.drr_total) / 2,
    drr_internal: (wb.drr_internal + ozon.drr_internal) / 2,
    drr_external: (wb.drr_external + ozon.drr_external) / 2,
  };
}

export function FinanceTab({ entityType, entityId }: FinanceTabProps) {
  const [filter, setFilter] = useState<ChannelFilter>("all");

  const { data, loading } = useApiQuery(
    () => matrixApi.fetchEntityFinance(entityType, entityId),
    [entityType, entityId],
  );

  if (loading) {
    return (
      <div className="space-y-4 p-4">
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <div key={i} className="h-32 animate-pulse rounded-lg bg-muted" />)}
        </div>
        <div className="h-64 animate-pulse rounded-lg bg-muted" />
      </div>
    );
  }

  if (!data) return <p className="p-4 text-muted-foreground">Нет данных</p>;

  const ch: FinanceChannel | null =
    filter === "wb" ? data.wb :
    filter === "ozon" ? data.ozon :
    combineChannels(data.wb, data.ozon);

  const delta: FinanceDelta | null =
    filter === "wb" ? data.delta_wb :
    filter === "ozon" ? data.delta_ozon :
    combineDelta(data.delta_wb, data.delta_ozon);

  if (!ch) return <p className="p-4 text-muted-foreground">Нет финансовых данных для этого канала.</p>;

  return (
    <div className="space-y-6 p-4">
      {/* Channel filter */}
      <div className="flex gap-2">
        {(["all", "wb", "ozon"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-md px-3 py-1 text-sm transition-colors",
              filter === f ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-muted/80",
            )}
          >
            {f === "all" ? "Все" : f === "wb" ? "WB" : "Ozon"}
          </button>
        ))}
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <KpiCard
          title="Заказы до СПП"
          mainValue={`${fmtRub(ch.orders_sum)} ₽`}
          subValue={`${ch.orders_count.toLocaleString("ru-RU")} шт`}
          delta={delta?.orders_sum}
        />
        <KpiCard
          title="Продажи до СПП"
          mainValue={`${fmtRub(ch.sales_sum)} ₽`}
          subValue={`${ch.sales_count.toLocaleString("ru-RU")} шт`}
          delta={delta?.revenue_before_spp}
        />
        <KpiCard
          title="Маржа"
          mainValue={`${fmtRub(ch.margin)} ₽`}
          subValue={fmtPct(ch.margin_pct)}
          delta={delta?.margin}
        />
      </div>

      {/* Expense table */}
      <div className="rounded-lg border p-4">
        <ExpenseTable expenses={ch.expenses} />
      </div>

      {/* Additional metrics */}
      <div className="grid grid-cols-2 gap-4 rounded-lg border p-4 text-sm md:grid-cols-4">
        <div>
          <p className="text-muted-foreground">Ср. чек до СПП</p>
          <p className="font-mono font-medium">{fmtRub(ch.avg_check_before_spp)} ₽</p>
        </div>
        <div>
          <p className="text-muted-foreground">Ср. чек после СПП</p>
          <p className="font-mono font-medium">{fmtRub(ch.avg_check_after_spp)} ₽</p>
        </div>
        <div>
          <p className="text-muted-foreground">СПП</p>
          <p className="font-mono font-medium">{fmtPct(ch.spp_pct)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Выкупаемость</p>
          <p className="font-mono font-medium">{fmtPct(ch.buyout_pct)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Возвраты</p>
          <p className="font-mono font-medium">{ch.returns_count} шт ({fmtPct(ch.returns_pct)})</p>
        </div>
        <div>
          <p className="text-muted-foreground">DRR общий</p>
          <p className="font-mono font-medium">{fmtPct(ch.drr.total)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">DRR внутр.</p>
          <p className="font-mono font-medium">{fmtPct(ch.drr.internal)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">DRR внешн.</p>
          <p className="font-mono font-medium">{fmtPct(ch.drr.external)}</p>
        </div>
      </div>
    </div>
  );
}
