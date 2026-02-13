"""
Расчёт выгодности перераспределения товаров OZON по складам.
Ключевой нюанс: перемещать нужно не все остатки, а только часть —
ту, которая сконцентрирована не в тех регионах, где есть спрос.
"""

import os
import sys
from decimal import Decimal
from collections import defaultdict

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.config import DB_CONFIG, DB_OZON


def to_float(val):
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    return float(val)


def fmt(num, decimals=0):
    if num is None:
        return "0"
    if decimals == 0:
        return f"{num:,.0f}".replace(",", " ")
    return f"{num:,.{decimals}f}".replace(",", " ")


def run():
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
    cur = conn.cursor()

    MOVE_COST_PER_UNIT = 45  # руб за перемещение 1 единицы
    REDUCTION_PCT = 0.40     # ожидаемое снижение логистики+хранения

    # =========================================================================
    # ЧАСТЬ 1: Текущее распределение остатков vs спроса по складам (модель)
    # =========================================================================
    print("=" * 120)
    print("ЧАСТЬ 1: ДИСБАЛАНС ОСТАТКОВ VS СПРОСА ПО СКЛАДАМ (по моделям)")
    print("=" * 120)

    # Остатки по модели × склад (сегодня)
    cur.execute("""
    SELECT
        LOWER(SPLIT_PART(offer_id, '/', 1)) as model,
        warehouse_name,
        SUM(stockspresent) as stock
    FROM stocks
    WHERE dateupdate = (SELECT MAX(dateupdate) FROM stocks)
      AND stockspresent > 0
    GROUP BY LOWER(SPLIT_PART(offer_id, '/', 1)), warehouse_name;
    """)
    stock_by_model_wh = defaultdict(lambda: defaultdict(float))
    stock_by_model = defaultdict(float)
    for r in cur.fetchall():
        stock_by_model_wh[r[0]][r[1]] = to_float(r[2])
        stock_by_model[r[0]] += to_float(r[2])

    # Заказы по модели × склад отгрузки (янв-фев 2026)
    cur.execute("""
    SELECT
        LOWER(SPLIT_PART(offer_id, '/', 1)) as model,
        warehouse_name,
        COUNT(*) as orders_cnt
    FROM orders
    WHERE in_process_at >= '2026-01-01' AND in_process_at < '2026-03-01'
      AND status != 'cancelled'
    GROUP BY LOWER(SPLIT_PART(offer_id, '/', 1)), warehouse_name;
    """)
    orders_by_model_wh = defaultdict(lambda: defaultdict(float))
    orders_by_model = defaultdict(float)
    for r in cur.fetchall():
        orders_by_model_wh[r[0]][r[1]] = to_float(r[2])
        orders_by_model[r[0]] += to_float(r[2])

    # Для каждой модели: считаем дисбаланс
    # Идея: если на складе X лежит 30% остатков модели, а заказов оттуда 10%,
    #        значит 20% остатков на этом складе — избыток, их нужно переместить.
    # Сумма всех избытков = количество единиц, которые нужно перевезти.

    model_move_units = {}  # сколько единиц каждой модели нужно переместить

    # Отбираем модели с продажами
    active_models = sorted(
        [m for m in stock_by_model if orders_by_model.get(m, 0) > 10],
        key=lambda m: -orders_by_model.get(m, 0)
    )

    for model in active_models:
        total_stock = stock_by_model[model]
        total_orders = orders_by_model.get(model, 0)

        if total_stock == 0 or total_orders == 0:
            continue

        # Собираем все склады
        all_warehouses = set(stock_by_model_wh[model].keys()) | set(orders_by_model_wh[model].keys())

        excess_units = 0  # единицы, которые нужно убрать (избыток)
        deficit_units = 0  # единицы, которых не хватает (дефицит)

        wh_details = []
        for wh in sorted(all_warehouses):
            stk = stock_by_model_wh[model].get(wh, 0)
            ords = orders_by_model_wh[model].get(wh, 0)

            stk_pct = (stk / total_stock * 100) if total_stock > 0 else 0
            ord_pct = (ords / total_orders * 100) if total_orders > 0 else 0

            # Целевое количество на этом складе = total_stock * (ord_pct / 100)
            target_stock = total_stock * (ord_pct / 100)
            diff = stk - target_stock

            if diff > 0:
                excess_units += diff
            else:
                deficit_units += abs(diff)

            if stk > 0 or ords > 0:
                wh_details.append((wh, stk, stk_pct, ords, ord_pct, diff))

        # Количество единиц к перемещению = min(excess, deficit) (они равны теоретически)
        units_to_move = round(min(excess_units, deficit_units))
        move_pct = (units_to_move / total_stock * 100) if total_stock > 0 else 0
        model_move_units[model] = units_to_move

        print(f"\n{'─' * 100}")
        print(f"МОДЕЛЬ: {model.upper()}")
        print(f"Остатки: {fmt(total_stock)} шт | Заказы янв-фев: {fmt(total_orders)} шт | "
              f"Нужно переместить: {fmt(units_to_move)} шт ({move_pct:.0f}% от остатков)")

        # Показываем топ дисбалансов
        sorted_details = sorted(wh_details, key=lambda x: -abs(x[5]))
        print(f"  {'Склад':<30} {'Остаток':>8} {'% ост':>7} {'Заказы':>8} {'% зак':>7} {'Дисбаланс':>10}")
        print(f"  {'-' * 75}")
        for wh, stk, stk_pct, ords, ord_pct, diff in sorted_details[:10]:
            marker = " ▲ изб" if diff > 3 else (" ▼ деф" if diff < -3 else "")
            print(f"  {wh:<30} {fmt(stk):>8} {stk_pct:>6.1f}% {fmt(ords):>8} {ord_pct:>6.1f}% {diff:>+9.0f}{marker}")

    # =========================================================================
    # ЧАСТЬ 2: ЭКОНОМИЧЕСКИЙ РАСЧЁТ ПЕРЕРАСПРЕДЕЛЕНИЯ
    # =========================================================================
    print("\n\n" + "=" * 120)
    print("ЧАСТЬ 2: ЭКОНОМИЧЕСКИЙ РАСЧЁТ ПЕРЕРАСПРЕДЕЛЕНИЯ")
    print("=" * 120)
    print(f"\nУсловия:")
    print(f"  - Улучшение индекса распределения → снижение логистики и хранения на 40%")
    print(f"  - Стоимость перемещения: {MOVE_COST_PER_UNIT} руб/ед")
    print(f"  - Перемещаем только избыточные единицы (не все остатки!)")

    # Логистика и хранение за январь 2026 (полный месяц)
    cur.execute("""
    SELECT
        LOWER(SPLIT_PART(article, '/', 1)) as model,
        SUM(logist_end) as logistics,
        SUM(storage_end) as storage,
        SUM(logist_end) + SUM(storage_end) as ls_total,
        SUM(price_end) as revenue,
        SUM(count_end) as sales,
        SUM(marga) - SUM(nds) as margin
    FROM abc_date
    WHERE date >= '2026-01-01' AND date < '2026-02-01'
    GROUP BY LOWER(SPLIT_PART(article, '/', 1))
    HAVING SUM(price_end) > 1000
    ORDER BY SUM(price_end) DESC;
    """)
    jan_data = {r[0]: {
        'logistics': to_float(r[1]),
        'storage': to_float(r[2]),
        'ls_total': to_float(r[3]),
        'revenue': to_float(r[4]),
        'sales': to_float(r[5]),
        'margin': to_float(r[6]),
    } for r in cur.fetchall()}

    print(f"\n{'Модель':<18} {'Лог янв':>10} {'Хран янв':>10} {'Лог+Хр':>10} "
          f"{'Эконом/мес':>11} {'Переместить':>12} {'Расх пер':>10} "
          f"{'Окупаем':>8} {'Маржа янв':>10} {'Маржа +40%':>11} {'Δ марж%':>8}")
    print("-" * 145)

    total_ls = 0
    total_savings_monthly = 0
    total_move_cost = 0
    total_margin_now = 0
    total_margin_after = 0
    total_revenue = 0
    total_units_to_move = 0

    results = []
    for model in active_models:
        if model not in jan_data:
            continue

        d = jan_data[model]
        units_to_move = model_move_units.get(model, 0)

        monthly_savings = d['ls_total'] * REDUCTION_PCT
        move_cost = units_to_move * MOVE_COST_PER_UNIT
        margin_after = d['margin'] + monthly_savings

        # Окупаемость в месяцах
        payback = (move_cost / monthly_savings) if monthly_savings > 0 else 99

        margin_pct_now = (d['margin'] / d['revenue'] * 100) if d['revenue'] > 0 else 0
        margin_pct_after = (margin_after / d['revenue'] * 100) if d['revenue'] > 0 else 0
        delta_mpct = margin_pct_after - margin_pct_now

        total_ls += d['ls_total']
        total_savings_monthly += monthly_savings
        total_move_cost += move_cost
        total_margin_now += d['margin']
        total_margin_after += margin_after
        total_revenue += d['revenue']
        total_units_to_move += units_to_move

        ok = "OK" if payback < 3 else ("~" if payback < 6 else "долго")

        results.append({
            'model': model,
            'ls': d['ls_total'],
            'savings': monthly_savings,
            'units': units_to_move,
            'move_cost': move_cost,
            'payback': payback,
            'margin_now': d['margin'],
            'margin_after': margin_after,
            'delta_mpct': delta_mpct,
            'revenue': d['revenue'],
            'ok': ok,
        })

        print(f"{model:<18} {fmt(d['logistics']):>10} {fmt(d['storage']):>10} {fmt(d['ls_total']):>10} "
              f"{fmt(monthly_savings):>11} {fmt(units_to_move):>12} {fmt(move_cost):>10} "
              f"{payback:>6.1f}м {fmt(d['margin']):>10} {fmt(margin_after):>11} {delta_mpct:>+7.1f}% [{ok}]")

    print("-" * 145)
    total_mpct_now = (total_margin_now / total_revenue * 100) if total_revenue > 0 else 0
    total_mpct_after = (total_margin_after / total_revenue * 100) if total_revenue > 0 else 0
    total_payback = (total_move_cost / total_savings_monthly) if total_savings_monthly > 0 else 99

    print(f"{'ИТОГО':<18} {'':>10} {'':>10} {fmt(total_ls):>10} "
          f"{fmt(total_savings_monthly):>11} {fmt(total_units_to_move):>12} {fmt(total_move_cost):>10} "
          f"{total_payback:>6.1f}м {fmt(total_margin_now):>10} {fmt(total_margin_after):>11} {total_mpct_after - total_mpct_now:>+7.1f}%")

    # =========================================================================
    # ЧАСТЬ 3: СВОДКА — ИТОГИ И РЕКОМЕНДАЦИИ
    # =========================================================================
    print("\n\n" + "=" * 120)
    print("ЧАСТЬ 3: ИТОГИ И РЕКОМЕНДАЦИИ")
    print("=" * 120)

    print(f"\n--- ТЕКУЩАЯ СИТУАЦИЯ (январь 2026) ---")
    print(f"  Логистика + хранение за январь: {fmt(total_ls)} руб")
    print(f"  Маржа за январь: {fmt(total_margin_now)} руб ({total_mpct_now:.1f}%)")
    print(f"  Общие остатки на складах: {fmt(sum(stock_by_model[m] for m in active_models if m in jan_data))} шт")

    print(f"\n--- РАСЧЁТ ПЕРЕРАСПРЕДЕЛЕНИЯ ---")
    print(f"  Единиц к перемещению: {fmt(total_units_to_move)} шт "
          f"(из {fmt(sum(stock_by_model[m] for m in active_models if m in jan_data))} общих остатков, "
          f"{total_units_to_move / sum(stock_by_model[m] for m in active_models if m in jan_data) * 100:.0f}%)")
    print(f"  Разовый расход на перемещение: {fmt(total_move_cost)} руб")
    print(f"  Ежемесячная экономия (40% от лог+хран): {fmt(total_savings_monthly)} руб/мес")
    print(f"  Окупаемость: {total_payback:.1f} месяцев")

    print(f"\n--- МАРЖА ПОСЛЕ ПЕРЕРАСПРЕДЕЛЕНИЯ ---")
    print(f"  Маржа сейчас (янв): {fmt(total_margin_now)} руб ({total_mpct_now:.1f}%)")
    print(f"  Маржа после (янв): {fmt(total_margin_after)} руб ({total_mpct_after:.1f}%)")
    print(f"  Прирост маржинальности: {total_mpct_after - total_mpct_now:+.1f} п.п.")

    # Через сколько месяцев чистый плюс
    net_after_1m = total_savings_monthly * 1 - total_move_cost
    net_after_2m = total_savings_monthly * 2 - total_move_cost
    net_after_3m = total_savings_monthly * 3 - total_move_cost
    net_after_6m = total_savings_monthly * 6 - total_move_cost

    print(f"\n--- ФИНАНСОВЫЙ ЭФФЕКТ ПО МЕСЯЦАМ ---")
    print(f"  Через 1 мес: {fmt(net_after_1m)} руб {'(+)' if net_after_1m > 0 else '(-)'}")
    print(f"  Через 2 мес: {fmt(net_after_2m)} руб {'(+)' if net_after_2m > 0 else '(-)'}")
    print(f"  Через 3 мес: {fmt(net_after_3m)} руб {'(+)' if net_after_3m > 0 else '(-)'}")
    print(f"  Через 6 мес: {fmt(net_after_6m)} руб {'(+)' if net_after_6m > 0 else '(-)'}")

    # Рекомендации по приоритету
    print(f"\n--- ПРИОРИТЕТ МОДЕЛЕЙ ДЛЯ ПЕРЕРАСПРЕДЕЛЕНИЯ ---")
    print(f"(отсортировано по скорости окупаемости)")
    print(f"\n  {'Модель':<18} {'Окупаемость':>11} {'Переместить':>12} {'Расход':>10} {'Эконом/мес':>11} {'Вердикт':<20}")
    print(f"  {'-' * 90}")

    for r in sorted(results, key=lambda x: x['payback']):
        verdict = ""
        if r['payback'] < 1.5:
            verdict = "ОБЯЗАТЕЛЬНО"
        elif r['payback'] < 3:
            verdict = "РЕКОМЕНДУЕТСЯ"
        elif r['payback'] < 6:
            verdict = "НА УСМОТРЕНИЕ"
        else:
            verdict = "НЕ ПРИОРИТЕТ"

        print(f"  {r['model']:<18} {r['payback']:>9.1f}м {fmt(r['units']):>12} {fmt(r['move_cost']):>10} {fmt(r['savings']):>11} {verdict:<20}")

    # =========================================================================
    # ЧАСТЬ 4: Детальный анализ топ-моделей — что именно перемещать
    # =========================================================================
    print("\n\n" + "=" * 120)
    print("ЧАСТЬ 4: ДЕТАЛЬНОЕ ПЕРЕМЕЩЕНИЕ — ТОП МОДЕЛИ")
    print("=" * 120)

    # Берём модели с окупаемостью < 6 мес
    priority_models = [r['model'] for r in results if r['payback'] < 6 and r['units'] > 0]

    for model in priority_models:
        total_stock = stock_by_model[model]
        total_orders = orders_by_model.get(model, 0)

        if total_stock == 0 or total_orders == 0:
            continue

        all_wh = set(stock_by_model_wh[model].keys()) | set(orders_by_model_wh[model].keys())

        print(f"\n{'─' * 90}")
        print(f"МОДЕЛЬ: {model.upper()} | Остатки: {fmt(total_stock)} | Заказы: {fmt(total_orders)}")
        print(f"  {'Склад':<30} {'Остаток':>8} {'Целевой':>8} {'Действие':>15}")
        print(f"  {'-' * 65}")

        actions = []
        for wh in sorted(all_wh):
            stk = stock_by_model_wh[model].get(wh, 0)
            ords = orders_by_model_wh[model].get(wh, 0)
            ord_pct = (ords / total_orders) if total_orders > 0 else 0
            target = round(total_stock * ord_pct)
            diff = round(stk - target)

            if abs(diff) >= 1:
                actions.append((wh, stk, target, diff))

        # Сортируем: сначала откуда забрать (diff > 0), потом куда завезти (diff < 0)
        take_from = sorted([a for a in actions if a[3] > 0], key=lambda x: -x[3])
        send_to = sorted([a for a in actions if a[3] < 0], key=lambda x: x[3])

        if take_from:
            print(f"\n  ЗАБРАТЬ:")
            for wh, stk, target, diff in take_from[:8]:
                print(f"  {wh:<30} {fmt(stk):>8} {fmt(target):>8} {'← убрать ' + fmt(diff):>15}")

        if send_to:
            print(f"\n  ЗАВЕЗТИ:")
            for wh, stk, target, diff in send_to[:8]:
                print(f"  {wh:<30} {fmt(stk):>8} {fmt(target):>8} {'→ довезти ' + fmt(abs(diff)):>15}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    run()
