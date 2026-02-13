"""
Анализ обвала маржи OZON в январе-феврале 2026.
Фокус: что именно изменилось, по каким моделям, по каким статьям расходов.
"""

import os
import sys
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


def fmt(num, decimals=0):
    if num is None:
        return "0"
    if decimals == 0:
        return f"{num:,.0f}".replace(",", " ")
    return f"{num:,.{decimals}f}".replace(",", " ")


def run():
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
    cur = conn.cursor()

    # =========================================================================
    # ЧАСТЬ 1: Помесячная декомпозиция P&L (окт 2025 — фев 2026)
    # =========================================================================
    print("=" * 120)
    print("ЧАСТЬ 1: ПОМЕСЯЧНАЯ ДЕКОМПОЗИЦИЯ P&L OZON (окт 2025 — фев 2026)")
    print("=" * 120)

    cur.execute("""
    SELECT
        TO_CHAR(date, 'YYYY-MM') as month,
        SUM(price_end) as revenue,
        SUM(comission_end) as commission,
        SUM(logist_end) as logistics,
        SUM(storage_end) as storage,
        SUM(sebes_end) as cogs,
        SUM(reclama_end) as adv_int,
        SUM(adv_vn) as adv_ext,
        SUM(nds) as nds,
        SUM(spp) as spp,
        SUM(marga) as marga_raw,
        SUM(marga) - SUM(nds) as margin,
        SUM(count_end) as sales,
        SUM(service_end) as services,
        SUM(cross_end) as cross_dock,
        SUM(bank_end) as acquiring
    FROM abc_date
    WHERE date >= '2025-10-01' AND date < '2026-03-01'
    GROUP BY TO_CHAR(date, 'YYYY-MM')
    ORDER BY month;
    """)
    rows = cur.fetchall()

    print(f"\n{'Статья':<22}", end="")
    for r in rows:
        print(f" {r[0]:>14}", end="")
    print()
    print("-" * (22 + 15 * len(rows)))

    labels = [
        (1, "Выручка до СПП"),
        (12, "Продажи, шт"),
        (9, "СПП (скидка МП)"),
        (2, "Комиссия"),
        (3, "Логистика"),
        (4, "Хранение"),
        (5, "Себестоимость"),
        (6, "Реклама внутр."),
        (7, "Реклама внеш."),
        (8, "НДС"),
        (13, "Сервисы Ozon"),
        (14, "Кросс-докинг"),
        (15, "Эквайринг"),
        (11, "МАРЖА (marga-nds)"),
    ]

    for idx, label in labels:
        print(f"{label:<22}", end="")
        for r in rows:
            val = to_float(r[idx])
            print(f" {fmt(val):>14}", end="")
        print()

    # Доли от выручки
    print(f"\n{'--- % от выручки ---':<22}")
    pct_labels = [
        (2, "Комиссия %"),
        (3, "Логистика %"),
        (4, "Хранение %"),
        (5, "Себестоимость %"),
        (6, "Реклама внутр %"),
        (8, "НДС %"),
        (11, "МАРЖА %"),
    ]
    for idx, label in pct_labels:
        print(f"{label:<22}", end="")
        for r in rows:
            rev = to_float(r[1])
            val = to_float(r[idx])
            pct = (val / rev * 100) if rev > 0 else 0
            print(f" {pct:>13.1f}%", end="")
        print()

    # Стоимость на единицу продажи
    print(f"\n{'--- руб/ед продажи ---':<22}")
    unit_labels = [
        (1, "Выручка/ед"),
        (2, "Комиссия/ед"),
        (3, "Логистика/ед"),
        (4, "Хранение/ед"),
        (5, "Себестоимость/ед"),
        (11, "Маржа/ед"),
    ]
    for idx, label in unit_labels:
        print(f"{label:<22}", end="")
        for r in rows:
            sales = to_float(r[12])
            val = to_float(r[idx])
            per_unit = (val / sales) if sales > 0 else 0
            print(f" {fmt(per_unit):>14}", end="")
        print()

    # =========================================================================
    # ЧАСТЬ 2: Декомпозиция по моделям — январь 2026 vs ноябрь 2025
    # =========================================================================
    print("\n\n" + "=" * 120)
    print("ЧАСТЬ 2: ДЕКОМПОЗИЦИЯ ПО МОДЕЛЯМ — ЯНВАРЬ 2026 vs НОЯБРЬ 2025 (последний 'нормальный' месяц)")
    print("=" * 120)

    cur.execute("""
    SELECT
        LOWER(SPLIT_PART(article, '/', 1)) as model,
        TO_CHAR(date, 'YYYY-MM') as month,
        SUM(price_end) as revenue,
        SUM(comission_end) as commission,
        SUM(logist_end) as logistics,
        SUM(storage_end) as storage,
        SUM(sebes_end) as cogs,
        SUM(reclama_end + adv_vn) as adv_total,
        SUM(nds) as nds,
        SUM(marga) - SUM(nds) as margin,
        SUM(count_end) as sales,
        SUM(spp) as spp
    FROM abc_date
    WHERE date >= '2025-10-01' AND date < '2026-03-01'
    GROUP BY LOWER(SPLIT_PART(article, '/', 1)), TO_CHAR(date, 'YYYY-MM')
    HAVING SUM(price_end) > 1000 OR SUM(price_end) < -1000
    ORDER BY model, month;
    """)
    model_rows = cur.fetchall()

    # Группируем по модели
    by_model = {}
    for r in model_rows:
        model = r[0]
        if model not in by_model:
            by_model[model] = {}
        by_model[model][r[1]] = r

    # Таблица: для каждой модели сравнение nov 2025 vs jan 2026
    months_to_compare = ['2025-10', '2025-11', '2025-12', '2026-01', '2026-02']

    for model, months_data in sorted(by_model.items(), key=lambda x: -to_float(x[1].get('2026-01', [0]*12)[2]) if '2026-01' in x[1] else 0):
        if not any(m in months_data for m in ['2026-01', '2026-02']):
            continue

        print(f"\n{'─' * 100}")
        print(f"МОДЕЛЬ: {model.upper()}")
        print(f"{'Показатель':<20}", end="")
        for m in months_to_compare:
            print(f" {m:>14}", end="")
        print()
        print("-" * (20 + 15 * len(months_to_compare)))

        metrics = [
            (2, "Выручка"),
            (10, "Продажи шт"),
            (3, "Комиссия"),
            (4, "Логистика"),
            (5, "Хранение"),
            (6, "Себестоимость"),
            (7, "Реклама"),
            (8, "НДС"),
            (11, "СПП"),
            (9, "МАРЖА"),
        ]
        for idx, label in metrics:
            print(f"{label:<20}", end="")
            for m in months_to_compare:
                if m in months_data:
                    val = to_float(months_data[m][idx])
                    print(f" {fmt(val):>14}", end="")
                else:
                    print(f" {'—':>14}", end="")
            print()

        # Маржинальность %
        print(f"{'Маржин-ть %':<20}", end="")
        for m in months_to_compare:
            if m in months_data:
                rev = to_float(months_data[m][2])
                margin = to_float(months_data[m][9])
                pct = (margin / rev * 100) if rev > 0 else 0
                print(f" {pct:>13.1f}%", end="")
            else:
                print(f" {'—':>14}", end="")
        print()

        # Комиссия %
        print(f"{'Комиссия %':<20}", end="")
        for m in months_to_compare:
            if m in months_data:
                rev = to_float(months_data[m][2])
                com = to_float(months_data[m][3])
                pct = (com / rev * 100) if rev > 0 else 0
                print(f" {pct:>13.1f}%", end="")
            else:
                print(f" {'—':>14}", end="")
        print()

    # =========================================================================
    # ЧАСТЬ 3: Что именно убило маржу? Дельта расходов янв 2026 vs ноя 2025
    # =========================================================================
    print("\n\n" + "=" * 120)
    print("ЧАСТЬ 3: ЧТО УБИЛО МАРЖУ? Дельта расходов на единицу: янв 2026 vs ноя 2025")
    print("=" * 120)

    cur.execute("""
    WITH nov AS (
        SELECT
            LOWER(SPLIT_PART(article, '/', 1)) as model,
            SUM(price_end) as revenue,
            SUM(comission_end) as commission,
            SUM(logist_end) as logistics,
            SUM(storage_end) as storage,
            SUM(sebes_end) as cogs,
            SUM(reclama_end + adv_vn) as adv,
            SUM(nds) as nds,
            SUM(marga) - SUM(nds) as margin,
            SUM(count_end) as sales,
            SUM(spp) as spp
        FROM abc_date
        WHERE date >= '2025-11-01' AND date < '2025-12-01'
        GROUP BY LOWER(SPLIT_PART(article, '/', 1))
    ),
    jan AS (
        SELECT
            LOWER(SPLIT_PART(article, '/', 1)) as model,
            SUM(price_end) as revenue,
            SUM(comission_end) as commission,
            SUM(logist_end) as logistics,
            SUM(storage_end) as storage,
            SUM(sebes_end) as cogs,
            SUM(reclama_end + adv_vn) as adv,
            SUM(nds) as nds,
            SUM(marga) - SUM(nds) as margin,
            SUM(count_end) as sales,
            SUM(spp) as spp
        FROM abc_date
        WHERE date >= '2026-01-01' AND date < '2026-02-01'
        GROUP BY LOWER(SPLIT_PART(article, '/', 1))
    )
    SELECT
        COALESCE(j.model, n.model) as model,
        n.revenue as nov_rev, j.revenue as jan_rev,
        n.commission as nov_com, j.commission as jan_com,
        n.logistics as nov_log, j.logistics as jan_log,
        n.storage as nov_stor, j.storage as jan_stor,
        n.cogs as nov_cogs, j.cogs as jan_cogs,
        n.adv as nov_adv, j.adv as jan_adv,
        n.nds as nov_nds, j.nds as jan_nds,
        n.margin as nov_margin, j.margin as jan_margin,
        n.sales as nov_sales, j.sales as jan_sales,
        n.spp as nov_spp, j.spp as jan_spp
    FROM jan j
    FULL OUTER JOIN nov n ON j.model = n.model
    WHERE COALESCE(j.revenue, 0) > 5000 OR COALESCE(n.revenue, 0) > 5000
    ORDER BY COALESCE(j.revenue, 0) DESC;
    """)
    delta_rows = cur.fetchall()

    print(f"\n{'Модель':<20} {'Ноя выр':>10} {'Янв выр':>10} {'Ноя ком%':>8} {'Янв ком%':>8} {'Δ ком%':>7} {'Ноя лог/ед':>10} {'Янв лог/ед':>10} {'Ноя хр/ед':>9} {'Янв хр/ед':>9} {'Ноя марж%':>9} {'Янв марж%':>9}")
    print("-" * 130)

    total_nov_margin = 0
    total_jan_margin = 0
    total_nov_com = 0
    total_jan_com = 0
    total_nov_rev = 0
    total_jan_rev = 0

    for r in delta_rows:
        model = r[0]
        nov_rev = to_float(r[1])
        jan_rev = to_float(r[2])
        nov_com = to_float(r[3])
        jan_com = to_float(r[4])
        nov_log = to_float(r[5])
        jan_log = to_float(r[6])
        nov_stor = to_float(r[7])
        jan_stor = to_float(r[8])
        nov_margin = to_float(r[15])
        jan_margin = to_float(r[16])
        nov_sales = to_float(r[17])
        jan_sales = to_float(r[18])

        total_nov_margin += nov_margin
        total_jan_margin += jan_margin
        total_nov_com += nov_com
        total_jan_com += jan_com
        total_nov_rev += nov_rev
        total_jan_rev += jan_rev

        nov_com_pct = (nov_com / nov_rev * 100) if nov_rev > 0 else 0
        jan_com_pct = (jan_com / jan_rev * 100) if jan_rev > 0 else 0
        delta_com = jan_com_pct - nov_com_pct

        nov_log_pu = (nov_log / nov_sales) if nov_sales > 0 else 0
        jan_log_pu = (jan_log / jan_sales) if jan_sales > 0 else 0
        nov_stor_pu = (nov_stor / nov_sales) if nov_sales > 0 else 0
        jan_stor_pu = (jan_stor / jan_sales) if jan_sales > 0 else 0

        nov_mpct = (nov_margin / nov_rev * 100) if nov_rev > 0 else 0
        jan_mpct = (jan_margin / jan_rev * 100) if jan_rev > 0 else 0

        print(f"{model:<20} {fmt(nov_rev):>10} {fmt(jan_rev):>10} {nov_com_pct:>7.1f}% {jan_com_pct:>7.1f}% {delta_com:>+6.1f}% {fmt(nov_log_pu):>10} {fmt(jan_log_pu):>10} {fmt(nov_stor_pu):>9} {fmt(jan_stor_pu):>9} {nov_mpct:>8.1f}% {jan_mpct:>8.1f}%")

    print("-" * 130)
    nov_com_pct_t = (total_nov_com / total_nov_rev * 100) if total_nov_rev > 0 else 0
    jan_com_pct_t = (total_jan_com / total_jan_rev * 100) if total_jan_rev > 0 else 0
    nov_mpct_t = (total_nov_margin / total_nov_rev * 100) if total_nov_rev > 0 else 0
    jan_mpct_t = (total_jan_margin / total_jan_rev * 100) if total_jan_rev > 0 else 0
    print(f"{'ИТОГО':<20} {fmt(total_nov_rev):>10} {fmt(total_jan_rev):>10} {nov_com_pct_t:>7.1f}% {jan_com_pct_t:>7.1f}% {jan_com_pct_t - nov_com_pct_t:>+6.1f}% {'':>10} {'':>10} {'':>9} {'':>9} {nov_mpct_t:>8.1f}% {jan_mpct_t:>8.1f}%")

    # =========================================================================
    # ЧАСТЬ 4: Разбивка — сколько маржи "съела" каждая статья расходов
    # =========================================================================
    print("\n\n" + "=" * 120)
    print("ЧАСТЬ 4: СКОЛЬКО МАРЖИ 'СЪЕЛА' КАЖДАЯ СТАТЬЯ РАСХОДОВ (ноя 2025 → янв 2026)")
    print("=" * 120)

    cur.execute("""
    SELECT
        TO_CHAR(date, 'YYYY-MM') as month,
        SUM(price_end) as revenue,
        SUM(comission_end) as commission,
        SUM(logist_end) as logistics,
        SUM(storage_end) as storage,
        SUM(sebes_end) as cogs,
        SUM(reclama_end) as adv_int,
        SUM(adv_vn) as adv_ext,
        SUM(nds) as nds,
        SUM(marga) - SUM(nds) as margin,
        SUM(count_end) as sales,
        SUM(spp) as spp,
        SUM(service_end) as services
    FROM abc_date
    WHERE date >= '2025-11-01' AND date < '2026-02-01'
      AND TO_CHAR(date, 'YYYY-MM') IN ('2025-11', '2026-01')
    GROUP BY TO_CHAR(date, 'YYYY-MM')
    ORDER BY month;
    """)
    cmp = cur.fetchall()

    if len(cmp) == 2:
        nov = cmp[0]
        jan = cmp[1]

        nov_rev = to_float(nov[1])
        jan_rev = to_float(jan[1])

        items = [
            ("Выручка до СПП", 1),
            ("Комиссия", 2),
            ("Логистика", 3),
            ("Хранение", 4),
            ("Себестоимость", 5),
            ("Реклама внутр.", 6),
            ("Реклама внеш.", 7),
            ("НДС", 8),
            ("Сервисы Ozon", 12),
        ]

        print(f"\n{'Статья':<22} {'Ноя 2025':>14} {'% выр':>7} {'Янв 2026':>14} {'% выр':>7} {'Δ абсолют':>14} {'Δ доля в выр':>12}")
        print("-" * 100)

        for label, idx in items:
            nv = to_float(nov[idx])
            jv = to_float(jan[idx])
            npct = (nv / nov_rev * 100) if nov_rev > 0 else 0
            jpct = (jv / jan_rev * 100) if jan_rev > 0 else 0
            delta = jv - nv
            delta_pct = jpct - npct
            print(f"{label:<22} {fmt(nv):>14} {npct:>6.1f}% {fmt(jv):>14} {jpct:>6.1f}% {fmt(delta):>14} {delta_pct:>+11.1f}%")

        nov_margin = to_float(nov[9])
        jan_margin = to_float(jan[9])
        nov_mpct = (nov_margin / nov_rev * 100) if nov_rev > 0 else 0
        jan_mpct = (jan_margin / jan_rev * 100) if jan_rev > 0 else 0

        print("-" * 100)
        print(f"{'МАРЖА':<22} {fmt(nov_margin):>14} {nov_mpct:>6.1f}% {fmt(jan_margin):>14} {jan_mpct:>6.1f}% {fmt(jan_margin - nov_margin):>14} {jan_mpct - nov_mpct:>+11.1f}%")

        print(f"\n\nДЕКОМПОЗИЦИЯ ПАДЕНИЯ МАРЖИНАЛЬНОСТИ ({nov_mpct:.1f}% → {jan_mpct:.1f}% = {jan_mpct - nov_mpct:+.1f} п.п.):")
        print(f"  Падение маржинальности на {nov_mpct - jan_mpct:.1f} п.п. обусловлено:")

        expense_items = [
            ("Комиссия", 2),
            ("Логистика", 3),
            ("Хранение", 4),
            ("Себестоимость", 5),
            ("Реклама внутр.", 6),
            ("Реклама внеш.", 7),
            ("НДС", 8),
            ("Сервисы", 12),
        ]
        for label, idx in expense_items:
            nv = to_float(nov[idx])
            jv = to_float(jan[idx])
            npct = (nv / nov_rev * 100) if nov_rev > 0 else 0
            jpct = (jv / jan_rev * 100) if jan_rev > 0 else 0
            delta_pp = jpct - npct
            if abs(delta_pp) > 0.3:
                direction = "↑ рост" if delta_pp > 0 else "↓ снижение"
                print(f"    {label}: {delta_pp:+.1f} п.п. ({direction} доли в выручке: {npct:.1f}% → {jpct:.1f}%)")

    # =========================================================================
    # ЧАСТЬ 5: Понедельная динамика янв-фев 2026
    # =========================================================================
    print("\n\n" + "=" * 120)
    print("ЧАСТЬ 5: ПОНЕДЕЛЬНАЯ ДИНАМИКА OZON (дек 2025 — фев 2026)")
    print("=" * 120)

    cur.execute("""
    SELECT
        date_trunc('week', date)::date as week,
        SUM(price_end) as revenue,
        SUM(comission_end) as commission,
        SUM(logist_end) as logistics,
        SUM(storage_end) as storage,
        SUM(sebes_end) as cogs,
        SUM(reclama_end + adv_vn) as adv,
        SUM(nds) as nds,
        SUM(marga) - SUM(nds) as margin,
        SUM(count_end) as sales,
        ROUND((SUM(comission_end) / NULLIF(SUM(price_end), 0) * 100)::numeric, 1) as com_pct,
        ROUND(((SUM(marga) - SUM(nds)) / NULLIF(SUM(price_end), 0) * 100)::numeric, 1) as margin_pct
    FROM abc_date
    WHERE date >= '2025-12-01' AND date < '2026-03-01'
    GROUP BY date_trunc('week', date)
    ORDER BY week;
    """)
    weeks = cur.fetchall()

    print(f"\n{'Неделя':<12} {'Выручка':>12} {'Комиссия':>11} {'Ком%':>6} {'Логистика':>11} {'Хранение':>10} {'Себест':>10} {'Реклама':>10} {'НДС':>8} {'Маржа':>11} {'Марж%':>7} {'Прод':>6}")
    print("-" * 130)
    for w in weeks:
        print(f"{str(w[0]):<12} {fmt(to_float(w[1])):>12} {fmt(to_float(w[2])):>11} {to_float(w[10]):>5.1f}% {fmt(to_float(w[3])):>11} {fmt(to_float(w[4])):>10} {fmt(to_float(w[5])):>10} {fmt(to_float(w[6])):>10} {fmt(to_float(w[7])):>8} {fmt(to_float(w[8])):>11} {to_float(w[11]):>6.1f}% {fmt(to_float(w[9])):>6}")

    # =========================================================================
    # ЧАСТЬ 6: Расчёт перераспределения с фокусом на текущие данные
    # =========================================================================
    print("\n\n" + "=" * 120)
    print("ЧАСТЬ 6: РАСЧЁТ ПЕРЕРАСПРЕДЕЛЕНИЯ — НА ОСНОВЕ ДАННЫХ ЯНВ-ФЕВ 2026")
    print("=" * 120)

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
    WHERE date >= '2026-01-01' AND date < '2026-03-01'
    GROUP BY LOWER(SPLIT_PART(article, '/', 1))
    HAVING SUM(price_end) > 5000
    ORDER BY SUM(price_end) DESC;
    """)
    jan_feb = cur.fetchall()

    # Текущие остатки
    cur.execute("""
    SELECT
        LOWER(SPLIT_PART(offer_id, '/', 1)) as model,
        SUM(stockspresent) as total_stock
    FROM stocks
    WHERE dateupdate = (SELECT MAX(dateupdate) FROM stocks)
    GROUP BY LOWER(SPLIT_PART(offer_id, '/', 1));
    """)
    stocks = {r[0]: to_float(r[1]) for r in cur.fetchall()}

    REDUCTION = 0.40
    MOVE_COST = 45

    print(f"\nУсловия: снижение логистики+хранения на 40%, стоимость перемещения 45 руб/ед")
    print(f"Период: январь-февраль 2026 (фактические данные)")
    print(f"\n{'Модель':<20} {'Лог+Хран':>11} {'Логистика':>11} {'Хранение':>11} {'Экономия':>11} {'Остатки':>8} {'Переезд':>10} {'Выгода':>10} {'Окуп.':>7} {'Маржа сейч':>11} {'Маржа после':>12}")
    print("-" * 140)

    total_ls = 0
    total_savings = 0
    total_move = 0
    total_net = 0
    total_margin_now = 0
    total_margin_after = 0

    for r in jan_feb:
        model = r[0]
        logist = to_float(r[1])
        storage = to_float(r[2])
        ls = to_float(r[3])
        rev = to_float(r[4])
        sales = to_float(r[5])
        margin = to_float(r[6])

        units = stocks.get(model, 0)
        saving = ls * REDUCTION
        move = units * MOVE_COST
        net = saving - move

        # Маржа после перераспределения = текущая маржа + экономия (без учёта разового расхода на перемещение)
        margin_after = margin + saving

        # Окупаемость: перемещение / (месячная экономия)
        # Данные за ~1.3 месяца (янв + ~10 дней фев), приведём к месяцу
        months_in_period = 1.3  # примерно
        monthly_saving = saving / months_in_period
        payback = (move / monthly_saving) if monthly_saving > 0 else 99

        total_ls += ls
        total_savings += saving
        total_move += move
        total_net += net
        total_margin_now += margin
        total_margin_after += margin_after

        ok = "✓" if net > 0 else "✗"
        print(f"{model:<20} {fmt(ls):>11} {fmt(logist):>11} {fmt(storage):>11} {fmt(saving):>11} {fmt(units):>8} {fmt(move):>10} {fmt(net):>10} {payback:>5.1f}м {fmt(margin):>11} {fmt(margin_after):>12} {ok}")

    print("-" * 140)
    print(f"{'ИТОГО':<20} {fmt(total_ls):>11} {'':>11} {'':>11} {fmt(total_savings):>11} {'':>8} {fmt(total_move):>10} {fmt(total_net):>10} {'':>7} {fmt(total_margin_now):>11} {fmt(total_margin_after):>12}")

    total_mpct_now = (total_margin_now / sum(to_float(r[4]) for r in jan_feb) * 100) if sum(to_float(r[4]) for r in jan_feb) > 0 else 0
    total_mpct_after = (total_margin_after / sum(to_float(r[4]) for r in jan_feb) * 100) if sum(to_float(r[4]) for r in jan_feb) > 0 else 0

    print(f"\n--- ИТОГИ ПЕРЕРАСПРЕДЕЛЕНИЯ (янв-фев 2026) ---")
    print(f"Текущая маржа: {fmt(total_margin_now)} руб ({total_mpct_now:.1f}%)")
    print(f"Маржа после снижения лог+хран на 40%: {fmt(total_margin_after)} руб ({total_mpct_after:.1f}%)")
    print(f"Прирост маржи: +{fmt(total_savings)} руб/период (+{total_mpct_after - total_mpct_now:.1f} п.п.)")
    print(f"Разовый расход на перемещение: {fmt(total_move)} руб")
    print(f"Чистая выгода: {fmt(total_net)} руб")

    cur.close()
    conn.close()


if __name__ == '__main__':
    run()
