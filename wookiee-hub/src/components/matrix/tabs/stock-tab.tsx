import { useApiQuery } from "@/hooks/use-api-query";
import { matrixApi, type StockResponse, type StockChannel, type MoySkladStock } from "@/lib/matrix-api";
import { cn } from "@/lib/utils";

interface StockTabProps {
  entityType: string;
  entityId: number;
}

function turnoverColor(days: number): string {
  if (days < 3) return "text-red-600 bg-red-50 border-red-200";
  if (days < 7) return "text-yellow-600 bg-yellow-50 border-yellow-200";
  if (days <= 30) return "text-green-600 bg-green-50 border-green-200";
  return "text-gray-500 bg-gray-50 border-gray-200";
}

function turnoverLabel(days: number): string {
  if (days < 3) return "Риск OOS";
  if (days < 7) return "Мало";
  if (days <= 30) return "Норма";
  return "Затоваривание";
}

function formatNum(n: number): string {
  return n.toLocaleString("ru-RU", { maximumFractionDigits: 1 });
}

function ChannelCard({ title, channel }: { title: string; channel: StockChannel }) {
  return (
    <div className={cn("rounded-lg border p-4", turnoverColor(channel.turnover_days))}>
      <h3 className="text-sm font-medium opacity-70">{title}</h3>
      <p className="mt-1 text-2xl font-bold">{formatNum(channel.stock_mp)} шт</p>
      <div className="mt-2 space-y-1 text-sm">
        <p>{formatNum(channel.turnover_days)} дн. ({turnoverLabel(channel.turnover_days)})</p>
        <p>{formatNum(channel.daily_sales)} шт/день</p>
        <p className="opacity-70">Продаж за период: {channel.sales_count}</p>
      </div>
    </div>
  );
}

function MoySkladCard({ data }: { data: MoySkladStock }) {
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-blue-700">
      <h3 className="text-sm font-medium opacity-70">МойСклад</h3>
      <p className="mt-1 text-2xl font-bold">{formatNum(data.total)} шт</p>
      <div className="mt-2 space-y-1 text-sm">
        <p>Склад: {formatNum(data.stock_main)}</p>
        <p>В пути: {formatNum(data.stock_transit)}</p>
        {data.is_stale && (
          <p className="text-orange-600">Данные от {data.snapshot_date}</p>
        )}
      </div>
    </div>
  );
}

export function StockTab({ entityType, entityId }: StockTabProps) {
  const { data, loading } = useApiQuery(
    () => matrixApi.fetchEntityStock(entityType, entityId),
    [entityType, entityId],
  );

  if (loading) {
    return (
      <div className="grid grid-cols-3 gap-4 p-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-40 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    );
  }

  if (!data) {
    return <p className="p-4 text-muted-foreground">Нет данных</p>;
  }

  return (
    <div className="space-y-4 p-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {data.wb && <ChannelCard title="WB FBO" channel={data.wb} />}
        {data.ozon && <ChannelCard title="Ozon FBO" channel={data.ozon} />}
        {data.moysklad && <MoySkladCard data={data.moysklad} />}
      </div>

      {!data.wb && !data.ozon && !data.moysklad && (
        <p className="text-muted-foreground">Нет данных об остатках для этой записи.</p>
      )}

      <div className="flex items-center gap-6 rounded-lg border bg-muted/30 p-3 text-sm">
        <span>Итого: <strong>{formatNum(data.total_stock)} шт</strong></span>
        {data.total_turnover_days != null && (
          <span>Оборачиваемость: <strong>{formatNum(data.total_turnover_days)} дней</strong></span>
        )}
      </div>
    </div>
  );
}
