"""
Сервис проверки актуальности данных.

Проверяет, обновились ли данные за предыдущий день в обеих БД (WB и OZON).
Таблица abc_date пересоздаётся полностью каждую ночь:
- WB: к ~06:18 МСК
- OZON: к ~07:03 МСК

Критерии готовности (6 ортогональных гейтов):
1. abc_date.dateupdate обновлена сегодня (ETL прошёл)
2. MAX(date) = вчера (данные за вчера присутствуют)
3. Orders cross-check: abc_date vs orders (≤ 5% расхождение)
4. Logistics check: abc_date.logist > 0
5. Revenue ≥ 70% от 7-day rolling average
6. Строк с marga ≠ 0 ≥ 80% от total (маржа рассчитана)
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional, Any
from agents.oleg.services.time_utils import get_today_msk

import psycopg2

logger = logging.getLogger(__name__)

# Колонка выручки: WB = revenue_spp, OZON = price_end
REVENUE_COL = {
    'pbi_wb_wookiee': 'revenue_spp',
    'pbi_ozon_wookiee': 'price_end',
}

# Колонка логистики: WB = logist, OZON = logist_end
LOGISTICS_COL = {
    'pbi_wb_wookiee': 'logist',
    'pbi_ozon_wookiee': 'logist_end',
}

# Колонка даты в таблице orders: WB = date, OZON = in_process_at
ORDERS_DATE_COL = {
    'pbi_wb_wookiee': 'date',
    'pbi_ozon_wookiee': 'in_process_at',
}

# Колонка кол-ва заказов в abc_date: WB = count_orders, OZON = count_end
ORDERS_COUNT_COL = {
    'pbi_wb_wookiee': 'count_orders',
    'pbi_ozon_wookiee': 'count_end',
}


class DataFreshnessService:
    """Проверка готовности данных WB и OZON."""

    def __init__(self, db_host: str, db_port: int, db_user: str, db_password: str,
                 db_name_wb: str, db_name_ozon: str):
        self._db_config = {
            'host': db_host,
            'port': db_port,
            'user': db_user,
            'password': db_password,
        }
        self._db_wb = db_name_wb
        self._db_ozon = db_name_ozon
        self._notified_today: Optional[date] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def already_notified_today(self) -> bool:
        return self._notified_today == get_today_msk()

    def mark_notified(self) -> None:
        self._notified_today = get_today_msk()

    def check_freshness(self) -> dict[str, Any]:
        """Возвращает статус готовности по каждому МП.

        Returns:
            {
                'wb':   {'ready': bool, 'updated_at': str|None, 'rows_yesterday': int, 'details': str},
                'ozon': {'ready': bool, 'updated_at': str|None, 'rows_yesterday': int, 'details': str},
            }
        """
        wb = self._check_mp(self._db_wb, dateupdate_col='dateupdate')
        ozon = self._check_mp(self._db_ozon, dateupdate_col='date_update')
        return {'wb': wb, 'ozon': ozon}

    def is_all_ready(self, status: Optional[dict[str, Any]] = None) -> bool:
        if status is None:
            status = self.check_freshness()
        return status['wb']['ready'] and status['ozon']['ready']

    def get_latest_data_date(self) -> Optional[date]:
        """Последняя дата, за которую есть данные в ОБЕИХ БД (WB и OZON)."""
        wb_date = self._get_max_date(self._db_wb)
        ozon_date = self._get_max_date(self._db_ozon)
        if wb_date and ozon_date:
            return min(wb_date, ozon_date)
        return wb_date or ozon_date

    def adjust_dates(self, start_date: str, end_date: str) -> tuple[str, str, Optional[str]]:
        """Скорректировать период по доступности данных.

        Returns:
            (adjusted_start, adjusted_end, note_or_None)
        """
        try:
            latest = self.get_latest_data_date()
        except Exception as e:
            logger.warning(f"get_latest_data_date failed: {e}")
            return start_date, end_date, None

        if latest is None:
            return start_date, end_date, "Не удалось определить доступность данных."

        req_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        req_start = datetime.strptime(start_date, "%Y-%m-%d").date()

        if req_end <= latest:
            return start_date, end_date, None

        adjusted_end = latest.strftime("%Y-%m-%d")
        missing_days = (req_end - latest).days

        if latest < req_start:
            return start_date, end_date, (
                f"Данные доступны только до {latest.strftime('%d.%m.%Y')}. "
                f"Запрошенный период ({req_start.strftime('%d.%m')}–{req_end.strftime('%d.%m')}) "
                f"не покрыт данными."
            )

        note = (
            f"Данные доступны до {latest.strftime('%d.%m.%Y')} включительно. "
            f"Нет данных за последние {missing_days} дн. "
            f"Период скорректирован: {req_start.strftime('%d.%m')}–{latest.strftime('%d.%m.%Y')}."
        )
        return start_date, adjusted_end, note

    def format_notification(self, status: dict[str, Any]) -> str:
        # Данные проверяются за ВЧЕРА (yesterday), а не сегодня!
        yesterday = (get_today_msk() - timedelta(days=1)).strftime('%d.%m.%Y')
        lines = [f"✅ Данные за {yesterday} готовы\n"]

        for mp, label in [('wb', 'WB'), ('ozon', 'OZON')]:
            s = status[mp]
            if s['ready']:
                rev_info = f", выручка {s.get('rev_vs_avg_pct', 0):.0f}% от avg" if s.get('rev_vs_avg_pct') else ""
                marga_info = f", маржа {s.get('marga_fill_pct', 0):.0f}%" if s.get('marga_fill_pct') else ""
                lines.append(f"{label}: {s['rows_yesterday']} артикулов (обновлено {s['updated_at']}{rev_info}{marga_info})")
            else:
                lines.append(f"{label}: НЕ готово — {s['details']}")

        lines.append(f"\n📊 Можно формировать отчёты за {yesterday} и ранее.")
        lines.append(f"⚠️ Данные за сегодня ({get_today_msk().strftime('%d.%m.%Y')}) еще не готовы.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_max_date(self, db_name: str) -> Optional[date]:
        """MAX(date) из abc_date для конкретной БД."""
        try:
            conn = psycopg2.connect(**self._db_config, database=db_name)
            cur = conn.cursor()
            cur.execute("SELECT MAX(date) FROM abc_date")
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                d = row[0]
                return d.date() if isinstance(d, datetime) else d
            return None
        except Exception as e:
            logger.error(f"_get_max_date({db_name}): {e}")
            return None

    def _get_source_orders_count(self, db_name: str, target_date: date) -> int:
        """Получить кол-во заказов из первоисточника (таблица orders) за дату.
        
        WB: дата в колонке `date` (timestamp).
        OZON: дата в колонке `in_process_at` (timestamp).
        """
        date_col = ORDERS_DATE_COL.get(db_name, 'date')
        try:
            conn = psycopg2.connect(**self._db_config, database=db_name)
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM orders WHERE {date_col}::date = %s",
                (target_date,)
            )
            count = cur.fetchone()[0]
            conn.close()
            return count or 0
        except Exception as e:
            logger.error(f"[{db_name}] _get_source_orders_count error: {e}")
            return 0

    def _get_avg_revenue_last_7_days(self, db_name: str, rev_col: str, target_date: date) -> float:
        """Средняя выручка за последние 7 дней (исключая target_date)."""
        try:
            conn = psycopg2.connect(**self._db_config, database=db_name)
            cur = conn.cursor()
            start_date = target_date - timedelta(days=7)
            cur.execute(
                f"SELECT AVG(daily_rev) FROM (SELECT SUM({rev_col}) as daily_rev FROM abc_date "
                f"WHERE date >= %s AND date < %s GROUP BY date) sub",
                (start_date, target_date)
            )
            avg_rev = cur.fetchone()[0]
            conn.close()
            return float(avg_rev) if avg_rev else 0.0
        except Exception as e:
            logger.error(f"[{db_name}] _get_avg_revenue error: {e}")
            return 0.0

    def _check_mp(self, db_name: str, dateupdate_col: str) -> dict[str, Any]:
        """Проверка готовности данных маркетплейса.

        6 ортогональных гейтов, каждый ловит свой класс сбоя:
        1. dateupdate = сегодня          → ETL не запускался
        2. MAX(date) = вчера             → данных за вчера нет
        3. orders cross-check ≤ 5%       → частичная загрузка abc_date
        4. revenue ≥ 70% от 7-day avg    → пустые/обнулённые строки
        5. logistics != 0                → данные о расходах отсутствуют
        6. rows с marga ≠ 0 ≥ 80% total  → маржа не рассчитана
        """
        result: dict[str, Any] = {
            'ready': False,
            'updated_at': None,
            'rows_yesterday': 0,
            'details': '',
        }

        rev_col = REVENUE_COL.get(db_name, 'revenue_spp')
        orders_col = ORDERS_COUNT_COL.get(db_name, 'count_orders')
        log_col = LOGISTICS_COL.get(db_name, 'logist')
        yesterday = get_today_msk() - timedelta(days=1)

        try:
            conn = psycopg2.connect(**self._db_config, database=db_name)
            cur = conn.cursor()

            # ── Gate 1: ETL обновил abc_date сегодня? ──
            cur.execute(f"SELECT MAX({dateupdate_col}) FROM abc_date")
            max_update = cur.fetchone()[0]

            if max_update is None:
                conn.close()
                result['details'] = 'abc_date пуста'
                return result

            update_date = max_update.date() if isinstance(max_update, datetime) else max_update
            result['updated_at'] = max_update.strftime('%H:%M') if isinstance(max_update, datetime) else str(max_update)

            if update_date != get_today_msk():
                conn.close()
                result['details'] = f'abc_date не обновлялась сегодня (последнее: {update_date})'
                return result

            # ── Gate 2: MAX(date) = вчера? ──
            cur.execute("SELECT MAX(date) FROM abc_date")
            max_date_row = cur.fetchone()[0]
            if max_date_row is not None:
                actual_max = max_date_row.date() if isinstance(max_date_row, datetime) else max_date_row
            else:
                actual_max = None

            if actual_max is None or actual_max < yesterday:
                conn.close()
                result['details'] = (
                    f'MAX(date)={actual_max}, ожидается {yesterday}. '
                    f'Данные за вчера ещё не загружены.'
                )
                return result

            # ── Собираем метрики за вчера одним запросом ──
            cur.execute(f"""
                SELECT
                    COUNT(*) as rows_total,
                    COALESCE(SUM({rev_col}), 0) as revenue,
                    COUNT(CASE WHEN marga != 0 THEN 1 END) as rows_with_marga,
                    COALESCE(SUM({orders_col}), 0) as abc_orders,
                    COALESCE(SUM({log_col}), 0) as logist_sum
                FROM abc_date
                WHERE date = %s
            """, (yesterday,))
            row = cur.fetchone()
            rows_total = row[0]
            rev_yesterday = float(row[1])
            rows_with_marga = row[2]
            abc_orders_count = float(row[3])
            logist_sum = float(row[4])

            result['rows_yesterday'] = rows_total

            if rows_total == 0:
                conn.close()
                result['details'] = 'нет данных за вчера'
                return result

            # ── Gate 3: Logistics Check (обязательно) ──
            if logist_sum == 0:
                conn.close()
                result['details'] = 'сумма логистики = 0 (данные неполные)'
                return result

            # ── Gate 3: Orders cross-check (abc_date vs orders table, ≤ 5%) ──
            conn.close()
            source_orders = self._get_source_orders_count(db_name, yesterday)

            diff_pct = 0.0
            if source_orders == 0:
                result['details'] = '0 заказов в таблице orders за вчера — сбой импорта?'
                return result
            diff_pct = abs(source_orders - abc_orders_count) / source_orders * 100
            if diff_pct > 5.0:
                result['details'] = (
                    f'рассинхрон: orders={source_orders}, '
                    f'abc_date={abc_orders_count:.0f} (diff {diff_pct:.1f}% > 5%)'
                )
                return result

            # ── Gate 4: Revenue ≥ 70% от 7-day avg ──
            avg_rev = self._get_avg_revenue_last_7_days(db_name, rev_col, yesterday)
            rev_vs_avg = (rev_yesterday / avg_rev * 100) if avg_rev > 0 else 100.0

            if avg_rev > 0 and rev_vs_avg < 70:
                result['details'] = (
                    f'выручка {rev_yesterday:,.0f}₽ = {rev_vs_avg:.0f}% '
                    f'от средней {avg_rev:,.0f}₽ (порог 70%)'
                )
                return result

            # ── Gate 5: Margin fill ≥ 80% total rows ──
            marga_fill = (rows_with_marga / rows_total * 100) if rows_total > 0 else 0

            if marga_fill < 80:
                result['details'] = (
                    f'маржа: {rows_with_marga}/{rows_total} строк '
                    f'({marga_fill:.0f}%, порог 80%)'
                )
                return result

            # ── Всё ок ──
            result['ready'] = True
            result['rev_vs_avg_pct'] = rev_vs_avg
            result['marga_fill_pct'] = marga_fill
            result['details'] = (
                f'OK (выручка {rev_vs_avg:.0f}% от avg, '
                f'маржа {marga_fill:.0f}%, '
                f'orders diff {diff_pct:.1f}%)'
            )
            return result

        except Exception as e:
            logger.error(f"Ошибка проверки {db_name}: {e}")
            result['details'] = f'ошибка: {e}'
            return result

