"""
Анализ OZON: продажи, маржинальность, логистика и хранение по моделям.
Поиск моментов кратного роста расходов + расчёт выгодности перераспределения по складам.
"""

import os
import sys
from datetime import datetime
from decimal import Decimal

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.config import DB_CONFIG, DB_OZON


def to_float(val):
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    return float(val)


def format_num(num, decimals=0):
    if num is None:
        return "0"
    if decimals == 0:
        return f"{num:,.0f}".replace(",", " ")
    return f"{num:,.{decimals}f}".replace(",", " ")


def run_analysis():
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
    cur = conn.cursor()

    # =========================================================================
    # ЧАСТЬ 1: Общая сводка OZON по месяцам
    # =========================================================================
    print("=" * 100)
    print("ЧАСТЬ 1: ОБЩАЯ СВОДКА OZON ПО МЕСЯЦАМ")
    print("=" * 100)

    cur.execute("""
    SELECT
        TO_CHAR(date, 'YYYY-MM') as month,
        SUM(price_end) as revenue_before_spp,
        SUM(price_end_spp) as revenue_after_spp,
        SUM(marga) - SUM(nds) as margin,
        SUM(logist_end) as logistics,
        SUM(storage_end) as storage,
        SUM(sebes_end) as cost_of_goods,
        SUM(comission_end) as commission,
        SUM(reclama_end) as adv_internal,
        SUM(adv_vn) as adv_external,
        SUM(nds) as nds,
        SUM(count_end) as sales_count,
        ROUND((SUM(marga) - SUM(nds)) / NULLIF(SUM(price_end), 0) * 100, 2) as margin_pct
    FROM abc_date
    WHERE date >= '2024-01-01'
    GROUP BY TO_CHAR(date, 'YYYY-MM')
    ORDER BY month;
    """)
    rows = cur.fetchall()

    print(f"\n{'Месяц':<10} {'Выручка':>14} {'Маржа':>12} {'Марж%':>7} {'Логистика':>12} {'Хранение':>12} {'Себест.':>12} {'Комиссия':>12} {'Реклама':>12} {'Продажи':>8}")
    print("-" * 120)
    for r in rows:
        month = r[0]
        rev = to_float(r[1])
        margin = to_float(r[3])
        logist = to_float(r[4])
        storage = to_float(r[5])
        sebes = to_float(r[6])
        comis = to_float(r[7])
        adv = to_float(r[8]) + to_float(r[9])
        sales = to_float(r[11])
        mpct = to_float(r[12])
        print(f"{month:<10} {format_num(rev):>14} {format_num(margin):>12} {mpct:>6.1f}% {format_num(logist):>12} {format_num(storage):>12} {format_num(sebes):>12} {format_num(comis):>12} {format_num(adv):>12} {format_num(sales):>8}")

    # =========================================================================
    # ЧАСТЬ 2: Логистика и хранение по моделям — понедельная динамика
    # =========================================================================
    print("\n\n" + "=" * 100)
    print("ЧАСТЬ 2: ЛОГИСТИКА И ХРАНЕНИЕ ПО МОДЕЛЯМ — ПОНЕДЕЛЬНАЯ ДИНАМИКА")
    print("=" * 100)

    cur.execute("""
    SELECT model FROM (
        SELECT LOWER(SPLIT_PART(article, '/', 1)) as model, SUM(price_end) as total_rev
        FROM abc_date
        WHERE date >= '2024-01-01'
          AND price_end > 0
        GROUP BY LOWER(SPLIT_PART(article, '/', 1))
        HAVING SUM(price_end) > 50000
    ) sub
    ORDER BY total_rev DESC;
    """)
    models = [r[0] for r in cur.fetchall()]

    print(f"\nМодели с выручкой > 50К руб: {len(models)}")
    print(f"Список: {', '.join(models)}")

    # Для каждой модели: понедельная динамика логистики и хранения
    all_model_spikes = {}

    for model in models:
        cur.execute("""
        SELECT
            date_trunc('week', date)::date as week_start,
            SUM(logist_end) as logistics,
            SUM(storage_end) as storage,
            SUM(logist_end) + SUM(storage_end) as logist_storage_total,
            SUM(price_end) as revenue,
            SUM(count_end) as sales_count,
            SUM(marga) - SUM(nds) as margin,
            COUNT(DISTINCT date) as days_in_week
        FROM abc_date
        WHERE date >= '2024-01-01'
          AND LOWER(SPLIT_PART(article, '/', 1)) = %s
        GROUP BY date_trunc('week', date)
        ORDER BY week_start;
        """, (model,))
        weeks = cur.fetchall()

        if len(weeks) < 2:
            continue

        print(f"\n{'─' * 90}")
        print(f"МОДЕЛЬ: {model.upper()}")
        print(f"{'─' * 90}")
        print(f"{'Неделя':<12} {'Логистика':>11} {'Δ лог%':>8} {'Хранение':>11} {'Δ хран%':>8} {'Лог+Хран':>11} {'Выручка':>12} {'Маржа':>11} {'Продажи':>8}")
        print("-" * 100)

        spikes = []
        for i, w in enumerate(weeks):
            wk = w[0]
            log = to_float(w[1])
            stor = to_float(w[2])
            ls_total = to_float(w[3])
            rev = to_float(w[4])
            sales = to_float(w[5])
            margin = to_float(w[6])
            days = int(w[7])

            if i > 0:
                prev_log = to_float(weeks[i-1][1])
                prev_stor = to_float(weeks[i-1][2])
                prev_ls = to_float(weeks[i-1][3])

                log_chg = ((log - prev_log) / abs(prev_log) * 100) if prev_log != 0 else 0
                stor_chg = ((stor - prev_stor) / abs(prev_stor) * 100) if prev_stor != 0 else 0
                ls_chg = ((ls_total - prev_ls) / abs(prev_ls) * 100) if prev_ls != 0 else 0

                log_chg_str = f"{log_chg:+.0f}%"
                stor_chg_str = f"{stor_chg:+.0f}%"

                # Детектируем кратный рост (>80% за неделю) с учётом абсолютных значений
                if (log_chg > 80 or stor_chg > 80) and ls_total > 500:
                    spikes.append({
                        'week': wk,
                        'prev_week': weeks[i-1][0],
                        'logistics': log,
                        'prev_logistics': prev_log,
                        'storage': stor,
                        'prev_storage': prev_stor,
                        'log_change_pct': log_chg,
                        'stor_change_pct': stor_chg,
                        'revenue': rev,
                        'margin': margin,
                        'sales': sales,
                    })
            else:
                log_chg_str = "—"
                stor_chg_str = "—"

            # Подсветим строки с кратным ростом
            marker = ""
            if i > 0:
                prev_log = to_float(weeks[i-1][1])
                prev_stor = to_float(weeks[i-1][2])
                if prev_log > 0 and log / prev_log > 1.8 and log > 500:
                    marker += " ⚡ЛОГ"
                if prev_stor > 0 and stor / prev_stor > 1.8 and stor > 500:
                    marker += " ⚡ХРАН"

            print(f"{str(wk):<12} {format_num(log):>11} {log_chg_str:>8} {format_num(stor):>11} {stor_chg_str:>8} {format_num(ls_total):>11} {format_num(rev):>12} {format_num(margin):>11} {format_num(sales):>8}{marker}")

        if spikes:
            all_model_spikes[model] = spikes

    # =========================================================================
    # ЧАСТЬ 3: СВОДКА СКАЧКОВ — все модели
    # =========================================================================
    print("\n\n" + "=" * 100)
    print("ЧАСТЬ 3: СВОДКА СКАЧКОВ ЛОГИСТИКИ И ХРАНЕНИЯ (рост >80% за неделю)")
    print("=" * 100)

    if not all_model_spikes:
        print("\nСкачков не обнаружено.")
    else:
        for model, spikes in all_model_spikes.items():
            print(f"\n▸ {model.upper()}: {len(spikes)} скачок(ов)")
            for s in spikes:
                print(f"  Неделя {s['week']} (vs {s['prev_week']}):")
                if s['log_change_pct'] > 80:
                    print(f"    Логистика: {format_num(s['prev_logistics'])} → {format_num(s['logistics'])} ({s['log_change_pct']:+.0f}%)")
                if s['stor_change_pct'] > 80:
                    print(f"    Хранение:  {format_num(s['prev_storage'])} → {format_num(s['storage'])} ({s['stor_change_pct']:+.0f}%)")
                print(f"    Выручка: {format_num(s['revenue'])}, Маржа: {format_num(s['margin'])}, Продажи: {format_num(s['sales'])} шт")

    # =========================================================================
    # ЧАСТЬ 4: Детальный анализ причин скачков (дневная детализация)
    # =========================================================================
    print("\n\n" + "=" * 100)
    print("ЧАСТЬ 4: ДЕТАЛЬНЫЙ АНАЛИЗ ПРИЧИН СКАЧКОВ (дневная детализация вокруг скачков)")
    print("=" * 100)

    for model, spikes in all_model_spikes.items():
        for s in spikes:
            week = s['week']
            prev_week = s['prev_week']
            # Показываем дневные данные за обе недели
            cur.execute("""
            SELECT
                date,
                SUM(logist_end) as logistics,
                SUM(storage_end) as storage,
                SUM(price_end) as revenue,
                SUM(count_end) as sales_count,
                SUM(marga) - SUM(nds) as margin
            FROM abc_date
            WHERE LOWER(SPLIT_PART(article, '/', 1)) = %s
              AND date >= %s AND date < (%s::date + interval '14 days')
            GROUP BY date
            ORDER BY date;
            """, (model, prev_week, prev_week))
            daily = cur.fetchall()

            if daily:
                print(f"\n▸ {model.upper()} — скачок на неделе {week}")
                print(f"  {'Дата':<12} {'Логистика':>11} {'Хранение':>11} {'Выручка':>12} {'Продажи':>8} {'Маржа':>11}")
                print(f"  {'-'*70}")
                for d in daily:
                    print(f"  {str(d[0]):<12} {format_num(to_float(d[1])):>11} {format_num(to_float(d[2])):>11} {format_num(to_float(d[3])):>12} {format_num(to_float(d[4])):>8} {format_num(to_float(d[5])):>11}")

    # =========================================================================
    # ЧАСТЬ 5: Последние 3 месяца — логистика и хранение по моделям
    # =========================================================================
    print("\n\n" + "=" * 100)
    print("ЧАСТЬ 5: ПОСЛЕДНИЕ 3 МЕСЯЦА — ЛОГИСТИКА И ХРАНЕНИЕ ПО МОДЕЛЯМ (для расчёта перераспределения)")
    print("=" * 100)

    cur.execute("""
    SELECT
        LOWER(SPLIT_PART(article, '/', 1)) as model,
        SUM(logist_end) as logistics,
        SUM(storage_end) as storage,
        SUM(logist_end) + SUM(storage_end) as logist_storage_total,
        SUM(price_end) as revenue,
        SUM(count_end) as sales_count,
        SUM(marga) - SUM(nds) as margin,
        ROUND((SUM(marga) - SUM(nds)) / NULLIF(SUM(price_end), 0) * 100, 2) as margin_pct
    FROM abc_date
    WHERE date >= (CURRENT_DATE - interval '3 months')
    GROUP BY LOWER(SPLIT_PART(article, '/', 1))
    HAVING SUM(price_end) > 10000
    ORDER BY SUM(price_end) DESC;
    """)
    model_data = cur.fetchall()

    print(f"\n{'Модель':<20} {'Логистика':>12} {'Хранение':>12} {'Лог+Хран':>12} {'Выручка':>14} {'Продажи':>8} {'Маржа':>12} {'Марж%':>7}")
    print("-" * 110)

    total_logist = 0
    total_storage = 0
    total_ls = 0
    total_rev = 0
    total_sales = 0
    total_margin = 0
    redistribution_data = []

    for r in model_data:
        model = r[0]
        logist = to_float(r[1])
        storage = to_float(r[2])
        ls = to_float(r[3])
        rev = to_float(r[4])
        sales = to_float(r[5])
        margin = to_float(r[6])
        mpct = to_float(r[7])

        total_logist += logist
        total_storage += storage
        total_ls += ls
        total_rev += rev
        total_sales += sales
        total_margin += margin

        redistribution_data.append({
            'model': model,
            'logistics': logist,
            'storage': storage,
            'ls_total': ls,
            'revenue': rev,
            'sales': sales,
            'margin': margin,
            'margin_pct': mpct,
        })

        print(f"{model:<20} {format_num(logist):>12} {format_num(storage):>12} {format_num(ls):>12} {format_num(rev):>14} {format_num(sales):>8} {format_num(margin):>12} {mpct:>6.1f}%")

    print("-" * 110)
    total_mpct = (total_margin / total_rev * 100) if total_rev > 0 else 0
    print(f"{'ИТОГО':<20} {format_num(total_logist):>12} {format_num(total_storage):>12} {format_num(total_ls):>12} {format_num(total_rev):>14} {format_num(total_sales):>8} {format_num(total_margin):>12} {total_mpct:>6.1f}%")

    # =========================================================================
    # ЧАСТЬ 6: РАСЧЁТ ВЫГОДНОСТИ ПЕРЕРАСПРЕДЕЛЕНИЯ ПО СКЛАДАМ
    # =========================================================================
    print("\n\n" + "=" * 100)
    print("ЧАСТЬ 6: РАСЧЁТ ВЫГОДНОСТИ ПЕРЕРАСПРЕДЕЛЕНИЯ ПО СКЛАДАМ")
    print("=" * 100)
    print("\nУсловия:")
    print("  - Снижение логистики и хранения: до 40%")
    print("  - Стоимость перемещения: 45 руб / единица товара")
    print("  - Период анализа: последние 3 месяца")

    # Для расчёта количества единиц нужно понять текущие остатки
    cur.execute("""
    SELECT
        LOWER(SPLIT_PART(article, '/', 1)) as model,
        SUM(count_end) as total_sales_3m
    FROM abc_date
    WHERE date >= (CURRENT_DATE - interval '3 months')
    GROUP BY LOWER(SPLIT_PART(article, '/', 1))
    HAVING SUM(price_end) > 10000
    ORDER BY SUM(price_end) DESC;
    """)
    sales_3m = {r[0]: to_float(r[1]) for r in cur.fetchall()}

    # Текущие остатки на складах
    cur.execute("""
    SELECT
        LOWER(SPLIT_PART(offer_id, '/', 1)) as model,
        SUM(stockspresent) as total_stock
    FROM stocks
    WHERE dateupdate = (SELECT MAX(dateupdate) FROM stocks)
    GROUP BY LOWER(SPLIT_PART(offer_id, '/', 1));
    """)
    try:
        stock_data = {r[0]: to_float(r[1]) for r in cur.fetchall()}
    except Exception:
        stock_data = {}

    REDUCTION_PCT = 0.40  # 40% снижение
    MOVE_COST_PER_UNIT = 45  # руб за единицу

    print(f"\n{'Модель':<20} {'Лог+Хран 3м':>12} {'Экономия 40%':>13} {'Ед. на складе':>13} {'Цена переезда':>14} {'Чистая выгода':>14} {'Окупаемость':>12}")
    print("-" * 110)

    total_savings = 0
    total_move_cost = 0
    total_net = 0

    for d in redistribution_data:
        model = d['model']
        ls = d['ls_total']
        savings = ls * REDUCTION_PCT

        # Используем остатки на складах для расчёта стоимости перемещения
        units = stock_data.get(model, 0)
        if units == 0:
            # Если нет данных по остаткам, оцениваем как средний месячный объём продаж
            units = sales_3m.get(model, 0) / 3 * 1.5  # ~1.5 месяца остатков

        move_cost = units * MOVE_COST_PER_UNIT
        net = savings - move_cost

        # Окупаемость в месяцах (если savings > 0)
        monthly_savings = savings / 3  # за 3 месяца, пересчитываем на 1 мес
        if monthly_savings > 0:
            payback_months = move_cost / monthly_savings
            payback_str = f"{payback_months:.1f} мес"
        else:
            payback_str = "—"

        total_savings += savings
        total_move_cost += move_cost
        total_net += net

        profitable = "✓" if net > 0 else "✗"
        print(f"{model:<20} {format_num(ls):>12} {format_num(savings):>13} {format_num(units):>13} {format_num(move_cost):>14} {format_num(net):>14} {payback_str:>12} {profitable}")

    print("-" * 110)
    print(f"{'ИТОГО':<20} {format_num(total_ls):>12} {format_num(total_savings):>13} {'':>13} {format_num(total_move_cost):>14} {format_num(total_net):>14}")

    print(f"\n--- ВЫВОДЫ ---")
    print(f"Общие расходы на логистику + хранение (3 мес): {format_num(total_ls)} руб")
    print(f"Потенциальная экономия (40%): {format_num(total_savings)} руб")
    print(f"Стоимость перемещения: {format_num(total_move_cost)} руб")
    print(f"Чистая выгода за 3 месяца: {format_num(total_net)} руб")
    if total_net > 0:
        print(f"РЕШЕНИЕ: Перераспределение ВЫГОДНО (чистая выгода {format_num(total_net)} руб за 3 мес)")
    else:
        print(f"РЕШЕНИЕ: Перераспределение НЕ ВЫГОДНО (убыток {format_num(abs(total_net))} руб)")

    # Месячная перспектива
    monthly_savings_total = total_savings / 3
    if monthly_savings_total > 0:
        payback = total_move_cost / monthly_savings_total
        print(f"\nМесячная экономия: {format_num(monthly_savings_total)} руб/мес")
        print(f"Срок окупаемости перемещения: {payback:.1f} мес")

    # =========================================================================
    # ЧАСТЬ 7: Помесячная динамика логистики и хранения OZON (для понимания тренда)
    # =========================================================================
    print("\n\n" + "=" * 100)
    print("ЧАСТЬ 7: ПОМЕСЯЧНАЯ ДИНАМИКА ДОЛИ ЛОГИСТИКИ И ХРАНЕНИЯ В ВЫРУЧКЕ")
    print("=" * 100)

    cur.execute("""
    SELECT
        TO_CHAR(date, 'YYYY-MM') as month,
        LOWER(SPLIT_PART(article, '/', 1)) as model,
        SUM(logist_end) as logistics,
        SUM(storage_end) as storage,
        SUM(logist_end) + SUM(storage_end) as ls_total,
        SUM(price_end) as revenue,
        ROUND(SUM(logist_end) / NULLIF(SUM(price_end), 0) * 100, 2) as logist_pct,
        ROUND(SUM(storage_end) / NULLIF(SUM(price_end), 0) * 100, 2) as storage_pct,
        SUM(count_end) as sales_count,
        CASE WHEN SUM(count_end) > 0 THEN ROUND(SUM(logist_end) / SUM(count_end), 2) ELSE 0 END as logist_per_unit,
        CASE WHEN SUM(count_end) > 0 THEN ROUND(SUM(storage_end) / SUM(count_end), 2) ELSE 0 END as storage_per_unit
    FROM abc_date
    WHERE date >= '2024-01-01'
      AND LOWER(SPLIT_PART(article, '/', 1)) IN (
          SELECT LOWER(SPLIT_PART(article, '/', 1))
          FROM abc_date WHERE date >= '2024-06-01'
          GROUP BY 1 HAVING SUM(price_end) > 100000
      )
    GROUP BY TO_CHAR(date, 'YYYY-MM'), LOWER(SPLIT_PART(article, '/', 1))
    ORDER BY model, month;
    """)
    monthly_model_data = cur.fetchall()

    # Группируем по модели
    by_model = {}
    for r in monthly_model_data:
        model = r[1]
        if model not in by_model:
            by_model[model] = []
        by_model[model].append(r)

    for model, rows in by_model.items():
        print(f"\n{'─' * 80}")
        print(f"МОДЕЛЬ: {model.upper()}")
        print(f"{'Месяц':<10} {'Логистика':>11} {'Хранение':>11} {'Лог/ед':>8} {'Хран/ед':>8} {'Выручка':>12} {'Лог%':>6} {'Хран%':>6} {'Продажи':>8}")
        print("-" * 95)
        for r in rows:
            month = r[0]
            logist = to_float(r[2])
            storage = to_float(r[3])
            rev = to_float(r[5])
            logist_pct = to_float(r[6])
            storage_pct = to_float(r[7])
            sales = to_float(r[8])
            logist_pu = to_float(r[9])
            storage_pu = to_float(r[10])
            print(f"{month:<10} {format_num(logist):>11} {format_num(storage):>11} {logist_pu:>8.0f} {storage_pu:>8.0f} {format_num(rev):>12} {logist_pct:>5.1f}% {storage_pct:>5.1f}% {format_num(sales):>8}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    run_analysis()
