"""
Быстрая проверка готовности данных за сегодня/вчера.

Запуск:
    python3 scripts/check_data_ready.py
    python3 scripts/check_data_ready.py --date 2026-02-12
"""
import sys
import os
import argparse
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.config import DB_CONFIG, DB_WB, DB_OZON

try:
    import psycopg2
except ImportError:
    print("pip install psycopg2-binary")
    sys.exit(1)


REVENUE_COL = {
    'pbi_wb_wookiee': 'revenue_spp',
    'pbi_ozon_wookiee': 'price_end',
}

SALES_COL = {
    'pbi_wb_wookiee': 'full_counts',
    'pbi_ozon_wookiee': 'count_end',
}


def check_db(db_name: str, label: str, target_date: str, dateupdate_col: str):
    """Проверяет готовность данных в одной БД."""
    print(f"\n{'='*50}")
    print(f"  {label} ({db_name})")
    print(f"{'='*50}")

    rev_col = REVENUE_COL.get(db_name, 'revenue_spp')
    sales_col = SALES_COL.get(db_name, 'full_counts')

    try:
        conn = psycopg2.connect(**DB_CONFIG, database=db_name)
        cur = conn.cursor()

        # 1. Когда обновлено
        cur.execute(f"SELECT MAX({dateupdate_col}) FROM abc_date")
        max_update = cur.fetchone()[0]
        print(f"  Последнее обновление: {max_update}")

        # 2. Строки за целевую дату
        cur.execute(f"""
            SELECT
                COUNT(*) as total_rows,
                SUM(CASE WHEN {rev_col} > 0 THEN 1 ELSE 0 END) as rows_with_revenue,
                SUM(CASE WHEN marga != 0 THEN 1 ELSE 0 END) as rows_with_marga,
                COALESCE(SUM({rev_col}), 0) as sum_revenue,
                COALESCE(SUM(marga), 0) as sum_marga,
                COALESCE(SUM({sales_col}), 0) as sum_sales
            FROM abc_date
            WHERE date = %s
        """, (target_date,))
        row = cur.fetchone()
        total = row[0]
        with_rev = row[1] or 0
        with_marga = row[2] or 0
        sum_rev = float(row[3])
        sum_marga = float(row[4])
        sum_sales = int(row[5])

        print(f"\n  Дата: {target_date}")
        print(f"  Строк всего: {total}")
        print(f"  С {rev_col} > 0: {with_rev}")
        print(f"  С marga != 0: {with_marga}")
        print(f"  SUM({rev_col}): {sum_rev:,.0f} ₽")
        print(f"  SUM(marga): {sum_marga:,.0f} ₽")
        print(f"  SUM(full_counts): {sum_sales} шт")

        # 3. Сравнение с предыдущим днём
        cur.execute(f"""
            SELECT
                COUNT(*) as total_rows,
                SUM(CASE WHEN marga != 0 THEN 1 ELSE 0 END) as rows_with_marga,
                COALESCE(SUM({rev_col}), 0) as sum_revenue,
                COALESCE(SUM(marga), 0) as sum_marga,
                COALESCE(SUM({sales_col}), 0) as sum_sales
            FROM abc_date
            WHERE date = %s::date - 1
        """, (target_date,))
        prev = cur.fetchone()
        prev_total = prev[0]
        prev_with_marga = prev[1] or 0
        prev_rev = float(prev[2])
        prev_marga = float(prev[3])
        prev_sales = int(prev[4])

        if prev_total > 0:
            print(f"\n  Предыдущий день ({target_date} - 1):")
            print(f"  Строк: {prev_total}")
            print(f"  С marga != 0: {prev_with_marga}")
            print(f"  SUM({rev_col}): {prev_rev:,.0f} ₽")
            print(f"  SUM(marga): {prev_marga:,.0f} ₽")
            print(f"  SUM(full_counts): {prev_sales} шт")

            if prev_rev > 0:
                rev_ratio = sum_rev / prev_rev * 100
                print(f"\n  Выручка vs предыдущий: {rev_ratio:.0f}%")
            rows_ratio = total / prev_total * 100
            print(f"  Строки vs предыдущий: {rows_ratio:.0f}%")
            if prev_with_marga > 0:
                marga_ratio = with_marga / prev_with_marga * 100
                print(f"  Строк с маржой vs предыдущий: {marga_ratio:.0f}%")

        # Доп. метрики
        marga_abs_fill_pct = (with_marga / total * 100) if total > 0 else 0
        marga_rev_ratio = (abs(sum_marga) / sum_rev * 100) if sum_rev > 0 else 0
        print(f"\n  Маржа заполнение (абс.): {marga_abs_fill_pct:.0f}% ({with_marga}/{total})")
        print(f"  Маржа/выручка ratio: {marga_rev_ratio:.1f}%")

        # Вердикт (те же критерии что в DataFreshnessService)
        print(f"\n  --- ВЕРДИКТ ---")
        issues = []
        if total == 0:
            issues.append("НЕТ ДАННЫХ")
        if prev_total > 0 and total < prev_total * 0.8:
            issues.append(f"строк {total} < 80% от {prev_total}")
        if prev_rev > 0 and sum_rev / prev_rev < 0.7:
            issues.append(f"выручка {sum_rev:,.0f} < 70% от {prev_rev:,.0f}")
        if prev_with_marga > 0 and with_marga / prev_with_marga < 0.9:
            issues.append(f"строк с маржой {with_marga} < 90% от {prev_with_marga}")
        if marga_abs_fill_pct < 80:
            issues.append(f"маржа заполнена {marga_abs_fill_pct:.0f}% < 80% от общего")
        if sum_marga == 0:
            issues.append("SUM(marga) = 0")
        if sum_rev > 0 and marga_rev_ratio < 5:
            issues.append(f"маржа/выручка {marga_rev_ratio:.1f}% < 5%")

        if issues:
            print(f"  ❌ НЕ ГОТОВО: {'; '.join(issues)}")
        else:
            print(f"  ✅ ДАННЫЕ ГОТОВЫ")

        conn.close()

    except Exception as e:
        print(f"  ❌ ОШИБКА: {e}")


def main():
    parser = argparse.ArgumentParser(description="Check data readiness")
    parser.add_argument("--date", default=None, help="Date YYYY-MM-DD (default: yesterday)")
    args = parser.parse_args()

    if args.date:
        target_date = args.date
    else:
        from datetime import timedelta
        target_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"\nПроверка готовности данных за {target_date}")
    import pytz
    msk_tz = pytz.timezone("Europe/Moscow")
    now_msk = datetime.now(msk_tz)
    print(f"Время запуска: {now_msk.strftime('%Y-%m-%d %H:%M:%S')} MSK")

    check_db(DB_WB, "WB", target_date, "dateupdate")
    check_db(DB_OZON, "OZON", target_date, "date_update")

    print(f"\n{'='*50}")
    print(f"  Готово!")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
