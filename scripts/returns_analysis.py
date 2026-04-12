"""Анализ возвратов по моделям за последние 3 месяца.

Источники данных:
- WB: abc_date (returns=шт, revenue_return_spp=руб до СПП)
- OZON: abc_date (count_return=шт, return_end=руб)
- OZON: returns table (детальные операции)
Группировка по модели через MODEL_OSNOVA_MAPPING.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict
from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection, to_float, format_num
from shared.model_mapping import get_osnova_sql


def get_wb_data():
    """WB возвраты и продажи по моделям, помесячно."""
    conn = _get_wb_connection()
    cur = conn.cursor()
    osnova_sql = get_osnova_sql("SPLIT_PART(article, '/', 1)")

    query = f"""
    SELECT
        TO_CHAR(date, 'YYYY-MM') as month,
        {osnova_sql} as model,
        COALESCE(SUM(returns), 0) as return_count,
        COALESCE(SUM(revenue_return_spp), 0) as returns_rub,
        COALESCE(SUM(full_counts), 0) as sales_count,
        COALESCE(SUM(revenue_spp), 0) as revenue_spp
    FROM abc_date
    WHERE date >= '2026-01-01' AND date < '2026-04-01'
    GROUP BY 1, 2
    ORDER BY 1, 4 DESC
    """
    cur.execute(query)
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results


def get_ozon_data():
    """OZON возвраты и продажи по моделям, помесячно."""
    conn = _get_ozon_connection()
    cur = conn.cursor()
    osnova_sql = get_osnova_sql("SPLIT_PART(article, '/', 1)")

    query = f"""
    SELECT
        TO_CHAR(date, 'YYYY-MM') as month,
        {osnova_sql} as model,
        COALESCE(SUM(count_return), 0) as return_count,
        COALESCE(SUM(return_end), 0) as returns_rub,
        COALESCE(SUM(count_end), 0) as sales_count,
        COALESCE(SUM(price_end), 0) as revenue
    FROM abc_date
    WHERE date >= '2026-01-01' AND date < '2026-04-01'
    GROUP BY 1, 2
    ORDER BY 1, 4 DESC
    """
    cur.execute(query)
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results


def get_ozon_returns_detail():
    """OZON returns table — детальные возвраты."""
    conn = _get_ozon_connection()
    cur = conn.cursor()
    query = """
    SELECT
        TO_CHAR(operation_date, 'YYYY-MM') as month,
        name,
        COUNT(*) as return_count,
        COALESCE(SUM(amount), 0) as total_amount
    FROM returns
    WHERE operation_date >= '2026-01-01' AND operation_date < '2026-04-01'
    GROUP BY 1, 2
    ORDER BY 1, 3 DESC
    """
    cur.execute(query)
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results


def build_model_data(wb_rows, ozon_rows):
    """Объединяем WB + OZON в единую структуру по модели и месяцу."""
    # model -> month -> {return_count, returns_rub, sales_count, revenue}
    data = defaultdict(lambda: defaultdict(lambda: {
        'wb_ret_cnt': 0, 'wb_ret_rub': 0, 'wb_sales': 0, 'wb_rev': 0,
        'oz_ret_cnt': 0, 'oz_ret_rub': 0, 'oz_sales': 0, 'oz_rev': 0,
    }))

    for row in wb_rows:
        month, model = row[0], row[1]
        d = data[model][month]
        d['wb_ret_cnt'] += int(to_float(row[2]))
        d['wb_ret_rub'] += to_float(row[3])
        d['wb_sales'] += int(to_float(row[4]))
        d['wb_rev'] += to_float(row[5])

    for row in ozon_rows:
        month, model = row[0], row[1]
        d = data[model][month]
        d['oz_ret_cnt'] += int(to_float(row[2]))
        d['oz_ret_rub'] += abs(to_float(row[3]))  # OZON returns are negative
        d['oz_sales'] += int(to_float(row[4]))
        d['oz_rev'] += to_float(row[5])

    return data


def print_channel_report(title, rows, channel):
    """Отчёт по одному каналу."""
    print(f"\n{'=' * 100}")
    print(f"  {title}")
    print(f"{'=' * 100}")

    # Собираем по модели
    models = defaultdict(dict)
    for row in rows:
        month, model = row[0], row[1]
        ret_cnt = int(to_float(row[2]))
        ret_rub = abs(to_float(row[3]))
        sales_cnt = int(to_float(row[4]))
        revenue = to_float(row[5])
        models[model][month] = {
            'cnt': ret_cnt, 'rub': ret_rub,
            'sales': sales_cnt, 'rev': revenue,
        }

    months = sorted(set(row[0] for row in rows))

    # Заголовок
    print(f"\n  {'Модель':<15}", end="")
    for m in months:
        print(f" | {m:^22}", end="")
    print(f" | {'Янв→Мар':>10}")
    print(f"  {'':<15}", end="")
    for m in months:
        print(f" | {'шт':>6}  {'руб':>12}", end="")
    print(f" | {'шт  %':>10}")
    print("  " + "-" * 98)

    # Сортируем по суммарным возвратам (руб)
    model_total = {}
    for model, mdata in models.items():
        total = sum(d['rub'] for d in mdata.values())
        model_total[model] = total

    for model in sorted(model_total, key=model_total.get, reverse=True):
        if model_total[model] == 0:
            continue
        mdata = models[model]
        line = f"  {model:<15}"
        cnts = []
        for m in months:
            d = mdata.get(m, {'cnt': 0, 'rub': 0})
            cnts.append(d['cnt'])
            line += f" | {d['cnt']:>6}  {format_num(d['rub']):>12}"

        # Динамика шт
        if len(cnts) >= 2 and cnts[0] > 0:
            change_cnt = ((cnts[-1] - cnts[0]) / cnts[0]) * 100
            arrow = "↑" if change_cnt > 5 else ("↓" if change_cnt < -5 else "→")
            line += f" | {arrow}{change_cnt:+.0f}%"
        elif len(cnts) >= 2 and cnts[0] == 0 and cnts[-1] > 0:
            line += " | ↑ new"
        else:
            line += " | →"
        print(line)

    # Итого
    print("  " + "-" * 98)
    totals_line = f"  {'ИТОГО':<15}"
    total_cnts = []
    for m in months:
        t_cnt = sum(mdata.get(m, {}).get('cnt', 0) for mdata in models.values())
        t_rub = sum(mdata.get(m, {}).get('rub', 0) for mdata in models.values())
        total_cnts.append(t_cnt)
        totals_line += f" | {t_cnt:>6}  {format_num(t_rub):>12}"
    if len(total_cnts) >= 2 and total_cnts[0] > 0:
        change = ((total_cnts[-1] - total_cnts[0]) / total_cnts[0]) * 100
        arrow = "↑" if change > 5 else ("↓" if change < -5 else "→")
        totals_line += f" | {arrow}{change:+.0f}%"
    print(totals_line)


def print_combined_report(data):
    """Сводный WB+OZON отчёт по моделям."""
    print(f"\n{'=' * 120}")
    print("  СВОДНЫЙ ОТЧЁТ: ВОЗВРАТЫ ПО МОДЕЛЯМ (WB + OZON) — ЯНВАРЬ-МАРТ 2026")
    print(f"{'=' * 120}")

    months = ['2026-01', '2026-02', '2026-03']

    print(f"\n  {'Модель':<15}", end="")
    for m in months:
        m_short = {'2026-01': 'Январь', '2026-02': 'Февраль', '2026-03': 'Март'}[m]
        print(f" | {m_short:^26}", end="")
    print(f" | {'Янв→Мар':^12} | {'% возвр':>7}")
    print(f"  {'':<15}", end="")
    for _ in months:
        print(f" | {'шт':>6}  {'руб':>12} {'%ret':>5}", end="")
    print(f" | {'шт':>6} {'%':>4} | {'сред':>7}")
    print("  " + "-" * 118)

    # Агрегируем
    model_totals = {}
    for model, month_data in data.items():
        total_ret = sum(
            d['wb_ret_cnt'] + d['oz_ret_cnt']
            for d in month_data.values()
        )
        total_rub = sum(
            d['wb_ret_rub'] + d['oz_ret_rub']
            for d in month_data.values()
        )
        if total_ret > 0 or total_rub > 0:
            model_totals[model] = total_rub

    for model in sorted(model_totals, key=model_totals.get, reverse=True):
        month_data = data[model]
        line = f"  {model:<15}"
        cnts = []
        rubs = []
        ret_rates = []

        for m in months:
            d = month_data.get(m, {
                'wb_ret_cnt': 0, 'wb_ret_rub': 0, 'wb_sales': 0, 'wb_rev': 0,
                'oz_ret_cnt': 0, 'oz_ret_rub': 0, 'oz_sales': 0, 'oz_rev': 0,
            })
            total_cnt = d['wb_ret_cnt'] + d['oz_ret_cnt']
            total_rub = d['wb_ret_rub'] + d['oz_ret_rub']
            total_sales = d['wb_sales'] + d['oz_sales']
            ret_rate = (total_cnt / total_sales * 100) if total_sales > 0 else 0

            cnts.append(total_cnt)
            rubs.append(total_rub)
            ret_rates.append(ret_rate)

            line += f" | {total_cnt:>6}  {format_num(total_rub):>12} {ret_rate:>4.1f}%"

        # Динамика
        if len(cnts) >= 2 and cnts[0] > 0:
            cnt_change = ((cnts[-1] - cnts[0]) / cnts[0]) * 100
            arrow = "↑" if cnt_change > 5 else ("↓" if cnt_change < -5 else "→")
            line += f" | {arrow}{cnt_change:>+5.0f}%"
        elif cnts[0] == 0 and cnts[-1] > 0:
            line += " |  ↑new"
        else:
            line += " |     →"

        # Средний % возвратов
        avg_rate = sum(ret_rates) / len(ret_rates) if ret_rates else 0
        line += f"  | {avg_rate:>5.1f}%"

        print(line)

    # Итого
    print("  " + "-" * 118)
    totals_line = f"  {'ИТОГО':<15}"
    total_cnts = []
    total_rubs = []
    for m in months:
        t_cnt = sum(
            data[model].get(m, {
                'wb_ret_cnt': 0, 'oz_ret_cnt': 0
            }).get('wb_ret_cnt', 0) + data[model].get(m, {
                'wb_ret_cnt': 0, 'oz_ret_cnt': 0
            }).get('oz_ret_cnt', 0)
            for model in model_totals
        )
        t_rub = sum(
            data[model].get(m, {
                'wb_ret_rub': 0, 'oz_ret_rub': 0
            }).get('wb_ret_rub', 0) + data[model].get(m, {
                'wb_ret_rub': 0, 'oz_ret_rub': 0
            }).get('oz_ret_rub', 0)
            for model in model_totals
        )
        t_sales = sum(
            data[model].get(m, {
                'wb_sales': 0, 'oz_sales': 0
            }).get('wb_sales', 0) + data[model].get(m, {
                'wb_sales': 0, 'oz_sales': 0
            }).get('oz_sales', 0)
            for model in model_totals
        )
        t_rate = (t_cnt / t_sales * 100) if t_sales > 0 else 0
        total_cnts.append(t_cnt)
        total_rubs.append(t_rub)
        totals_line += f" | {t_cnt:>6}  {format_num(t_rub):>12} {t_rate:>4.1f}%"

    if len(total_cnts) >= 2 and total_cnts[0] > 0:
        change = ((total_cnts[-1] - total_cnts[0]) / total_cnts[0]) * 100
        arrow = "↑" if change > 5 else ("↓" if change < -5 else "→")
        totals_line += f" | {arrow}{change:>+5.0f}%"
    print(totals_line)


def print_top_growing(data):
    """Топ моделей с наибольшим ростом возвратов."""
    print(f"\n{'=' * 80}")
    print("  ⚠️  МОДЕЛИ С РАСТУЩИМ ТРЕНДОМ ВОЗВРАТОВ")
    print(f"{'=' * 80}")

    growth_models = []
    for model, month_data in data.items():
        jan = month_data.get('2026-01', {})
        mar = month_data.get('2026-03', {})

        jan_cnt = jan.get('wb_ret_cnt', 0) + jan.get('oz_ret_cnt', 0)
        mar_cnt = mar.get('wb_ret_cnt', 0) + mar.get('oz_ret_cnt', 0)

        jan_rub = jan.get('wb_ret_rub', 0) + jan.get('oz_ret_rub', 0)
        mar_rub = mar.get('wb_ret_rub', 0) + mar.get('oz_ret_rub', 0)

        if jan_cnt > 0:
            pct_change = ((mar_cnt - jan_cnt) / jan_cnt) * 100
        elif mar_cnt > 0:
            pct_change = 999  # new
        else:
            pct_change = 0

        if mar_cnt > 3:  # минимальный порог значимости
            growth_models.append({
                'model': model,
                'jan_cnt': jan_cnt,
                'mar_cnt': mar_cnt,
                'jan_rub': jan_rub,
                'mar_rub': mar_rub,
                'pct_change': pct_change,
                'abs_change': mar_cnt - jan_cnt,
            })

    # Сортируем по абсолютному росту
    growth_models.sort(key=lambda x: x['abs_change'], reverse=True)

    print(f"\n  {'Модель':<15} | {'Янв (шт)':>10} | {'Мар (шт)':>10} | {'Δ шт':>8} | {'Δ %':>8} | {'Мар (руб)':>12}")
    print("  " + "-" * 78)

    for gm in growth_models:
        if gm['abs_change'] > 0:
            flag = "🔴" if gm['abs_change'] > 10 else "🟡"
        elif gm['abs_change'] < 0:
            flag = "🟢"
        else:
            flag = "⚪"
        print(f"  {flag} {gm['model']:<13} | {gm['jan_cnt']:>10} | {gm['mar_cnt']:>10} | {gm['abs_change']:>+8} | {gm['pct_change']:>+7.0f}% | {format_num(gm['mar_rub']):>12}")


def main():
    print("🔍 АНАЛИЗ ВОЗВРАТОВ ПО МОДЕЛЯМ — ЯНВАРЬ-МАРТ 2026")
    print("=" * 80)
    print("  Период: 2026-01-01 — 2026-03-31")
    print("  Источник: БД WB (pbi_wb_wookiee) + OZON (pbi_ozon_wookiee)")
    print("  Группировка: по модели (osnova)")

    # 1. Получаем данные
    print("\n📊 Загрузка данных...")
    wb_data = get_wb_data()
    print(f"  WB: {len(wb_data)} строк")

    ozon_data = get_ozon_data()
    print(f"  OZON: {len(ozon_data)} строк")

    # 2. Отчёты по каналам
    print_channel_report("WB — Возвраты по моделям", wb_data, "WB")
    print_channel_report("OZON — Возвраты по моделям", ozon_data, "OZON")

    # 3. Сводный отчёт
    combined = build_model_data(wb_data, ozon_data)
    print_combined_report(combined)

    # 4. Топ растущие
    print_top_growing(combined)

    # 5. OZON детали
    print(f"\n{'=' * 80}")
    print("  OZON returns table — топ товаров по возвратам (январь-март 2026)")
    print(f"{'=' * 80}")
    try:
        detail = get_ozon_returns_detail()
        if detail:
            months_data = defaultdict(list)
            for row in detail:
                months_data[row[0]].append(row)

            for m in sorted(months_data.keys()):
                m_name = {'2026-01': 'Январь', '2026-02': 'Февраль', '2026-03': 'Март'}.get(m, m)
                print(f"\n  {m_name}:")
                for row in months_data[m][:5]:
                    _, name, cnt, amount = row
                    print(f"    {name[:50]:<50} | {cnt:>5} шт | {format_num(abs(to_float(amount))):>10} ₽")
    except Exception as e:
        print(f"  Ошибка: {e}")

    print(f"\n{'=' * 80}")
    print("✅ Анализ завершён")


if __name__ == "__main__":
    main()
