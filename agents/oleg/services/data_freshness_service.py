"""
Сервис проверки актуальности данных.

Проверяет, обновились ли данные за предыдущий день в обеих БД (WB и OZON).
Таблица abc_date пересоздаётся полностью каждую ночь:
- WB: к ~06:18 МСК
- OZON: к ~07:03 МСК

Критерии готовности:
1. abc_date.dateupdate (или date_update) обновлена сегодня
2. MAX(date) = вчера (данные за вчера присутствуют в таблице)
3. Есть данные за вчера
4. Финансовые данные заполнены:
   a. SUM(выручка) за вчера >= 50% от среднего за неделю (защита от частичной загрузки)
   b. SUM(marga) != 0
   c. SUM(logistics) > 0
   d. Кол-во заказов в abc_date соответствует таблице orders (расхождение < 5%)
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
                rev_info = f", выручка {s.get('rev_vs_avg_pct', 0):.0f}% от средней" if s.get('rev_vs_avg_pct') else ""
                lines.append(f"{label}: {s['rows_yesterday']} артикулов (обновлено {s['updated_at']}{rev_info})")
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
        result: dict[str, Any] = {
            'ready': False,
            'updated_at': None,
            'rows_yesterday': 0,
            'has_financial_data': False,
            'details': '',
        }

        # Определяем колонки по имени БД
        rev_col = REVENUE_COL.get(db_name, 'revenue_spp')
        log_col = LOGISTICS_COL.get(db_name, 'logist')

        try:
            conn = psycopg2.connect(**self._db_config, database=db_name)
            cur = conn.cursor()

            # 1. Когда abc_date была пересоздана?
            cur.execute(f"SELECT MAX({dateupdate_col}) FROM abc_date")
            max_update = cur.fetchone()[0]

            if max_update is None:
                result['details'] = 'abc_date пуста'
                conn.close()
                return result

            update_date = max_update.date() if isinstance(max_update, datetime) else max_update
            result['updated_at'] = max_update.strftime('%H:%M') if isinstance(max_update, datetime) else str(max_update)

            if update_date != get_today_msk():
                result['details'] = f'abc_date не обновлялась сегодня (последнее: {update_date})'
                conn.close()
                return result

            # 1b. MAX(date) должна быть = вчера
            yesterday = get_today_msk() - timedelta(days=1)
            actual_max = self._get_max_date(db_name)
            
            if actual_max is None or actual_max < yesterday:
                result['details'] = (
                    f'MAX(date) в abc_date ({actual_max}) меньше ожидаемого ({yesterday}). '
                    f'Данные за вчера еще не загружены.'
                )
                conn.close()
                return result

            # 2. Кол-во строк + финансовые суммы за вчера
            query = f"""
                SELECT
                    COALESCE(SUM(CASE WHEN date = %s THEN 1 ELSE 0 END), 0) as rows_yesterday,
                    COALESCE(SUM(CASE WHEN date = %s THEN {rev_col} ELSE 0 END), 0) as rev_yesterday,
                    COALESCE(SUM(CASE WHEN date = %s THEN marga ELSE 0 END), 0) as marga_yesterday,
                    COALESCE(SUM(CASE WHEN date = %s THEN {log_col} ELSE 0 END), 0) as logist_yesterday,
                    COALESCE(SUM(CASE WHEN date = %s AND marga != 0 THEN 1 ELSE 0 END), 0) as rows_with_marga
                FROM abc_date
                WHERE date = %s
            """
            cur.execute(query, (
                yesterday,
                yesterday,
                yesterday,
                yesterday,
                yesterday,
                yesterday
            ))
            row = cur.fetchone()
            rows_yesterday = row[0]
            rev_yesterday = float(row[1])
            marga_yesterday = float(row[2])
            logist_yesterday = float(row[3])
            rows_with_marga = row[4]

            result['rows_yesterday'] = rows_yesterday
            conn.close()

            if rows_yesterday == 0:
                result['details'] = 'нет данных за вчера'
                return result

            # 🛡️ HARDENING 1: Cross-Check with Source Orders
            conn = psycopg2.connect(**self._db_config, database=db_name)
            cur = conn.cursor()
            cur.execute("SELECT SUM(count_orders) FROM abc_date WHERE date = %s", (yesterday,))
            abc_orders_count = cur.fetchone()[0] or 0
            conn.close()

            source_orders_count = self._get_source_orders_count(db_name, yesterday)
            
            if source_orders_count == 0:
                 result['details'] = f'0 заказов в таблице orders (source) за вчера. Сбой импорта?'
                 return result

            diff_pct = 0.0
            if source_orders_count > 0:
                diff_pct = abs(source_orders_count - abc_orders_count) / source_orders_count * 100
                if diff_pct > 5.0:  # Порог 5%
                    result['details'] = (
                        f'рассинхрон данных: orders={source_orders_count}, '
                        f'abc_date={abc_orders_count} (diff {diff_pct:.1f}% > 5%). '
                        f'ETL не завершен.'
                    )
                    return result

            # 🛡️ HARDENING 2: Strict Revenue Check (vs 7-day Average)
            avg_rev_7d = self._get_avg_revenue_last_7_days(db_name, rev_col, yesterday)
            rev_pct_vs_avg = (rev_yesterday / avg_rev_7d * 100) if avg_rev_7d > 0 else 0
            
            if avg_rev_7d > 0 and rev_pct_vs_avg < 50:
                result['details'] = (
                    f'выручка подозрительно низкая: '
                    f'{rev_yesterday:,.0f}₽ vs средняя {avg_rev_7d:,.0f}₽ '
                    f'({rev_pct_vs_avg:.0f}%, порог 50%)'
                )
                return result

            # 3. Финальные проверки маржи и логистики
            if rows_with_marga == 0:
                 result['details'] = 'есть строки, но нет маржи (0 строк с marga != 0)'
                 return result
            
            if logist_yesterday == 0:
                 result['details'] = 'есть строки, но сумма логистики = 0. Возможно, данные неполные.'
                 return result

            if marga_yesterday == 0:
                 result['details'] = 'есть строки, но SUM(marga) = 0'
                 return result

            result['has_financial_data'] = True
            result['rev_vs_avg_pct'] = rev_pct_vs_avg
            result['ready'] = True
            result['details'] = f'OK (выручка {rev_pct_vs_avg:.0f}% от средней, source/abc расхождение {diff_pct:.1f}%)'
            return result

        except Exception as e:
            logger.error(f"Ошибка проверки {db_name}: {e}")
            result['details'] = f'ошибка подключения/проверки: {e}'
            return result
