"""
Сервис проверки актуальности данных.

Проверяет, обновились ли данные за предыдущий день в обеих БД (WB и OZON).
Таблица abc_date пересоздаётся полностью каждую ночь:
- WB: к ~06:18 МСК
- OZON: к ~07:03 МСК

Критерии готовности:
1. abc_date.dateupdate (или date_update) обновлена сегодня
2. Есть данные за вчера
3. Кол-во строк за вчера >= 80% от позавчера (защита от неполного обновления)
4. Финансовые данные заполнены:
   a. SUM(выручка) за вчера >= 50% от позавчера (защита от частичной загрузки)
   b. SUM(marga) != 0
   c. Количество строк с marga != 0 >= 50% от предыдущего дня
"""

import logging
from datetime import date, datetime
from typing import Optional

import psycopg2

logger = logging.getLogger(__name__)

# Колонка выручки: WB = revenue_spp, OZON = price_end
REVENUE_COL = {
    'pbi_wb_wookiee': 'revenue_spp',
    'pbi_ozon_wookiee': 'price_end',
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
        return self._notified_today == date.today()

    def mark_notified(self) -> None:
        self._notified_today = date.today()

    def check_freshness(self) -> dict:
        """Возвращает статус готовности по каждому МП.

        Returns:
            {
                'wb':   {'ready': bool, 'updated_at': str|None, 'rows_yesterday': int, 'rows_before': int, 'details': str},
                'ozon': {'ready': bool, 'updated_at': str|None, 'rows_yesterday': int, 'rows_before': int, 'details': str},
            }
        """
        wb = self._check_mp(self._db_wb, dateupdate_col='dateupdate')
        ozon = self._check_mp(self._db_ozon, dateupdate_col='date_update')
        return {'wb': wb, 'ozon': ozon}

    def is_all_ready(self, status: Optional[dict] = None) -> bool:
        if status is None:
            status = self.check_freshness()
        return status['wb']['ready'] and status['ozon']['ready']

    def format_notification(self, status: dict) -> str:
        from datetime import timedelta

        # Данные проверяются за ВЧЕРА (yesterday), а не сегодня!
        yesterday = (date.today() - timedelta(days=1)).strftime('%d.%m.%Y')
        lines = [f"✅ Данные за {yesterday} готовы\n"]

        for mp, label in [('wb', 'WB'), ('ozon', 'OZON')]:
            s = status[mp]
            if s['ready']:
                rev_info = f", выручка {s.get('rev_vs_before_pct', 0):.0f}% от пред. дня" if s.get('rev_vs_before_pct') else ""
                lines.append(f"{label}: {s['rows_yesterday']} артикулов (обновлено {s['updated_at']}{rev_info})")
            else:
                lines.append(f"{label}: НЕ готово — {s['details']}")

        lines.append(f"\n📊 Можно формировать отчёты за {yesterday} и ранее.")
        lines.append(f"⚠️ Данные за сегодня ({date.today().strftime('%d.%m.%Y')}) еще не готовы.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_mp(self, db_name: str, dateupdate_col: str) -> dict:
        result = {
            'ready': False,
            'updated_at': None,
            'rows_yesterday': 0,
            'rows_before': 0,
            'has_financial_data': False,
            'details': '',
        }

        # Определяем колонку выручки по имени БД
        rev_col = REVENUE_COL.get(db_name, 'revenue_spp')

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

            if update_date != date.today():
                result['details'] = f'abc_date не обновлялась сегодня (последнее: {update_date})'
                conn.close()
                return result

            # 2. Кол-во строк + финансовые суммы за вчера и позавчера
            query = f"""
                SELECT
                    COALESCE(SUM(CASE WHEN date = CURRENT_DATE - 1 THEN 1 ELSE 0 END), 0) as rows_yesterday,
                    COALESCE(SUM(CASE WHEN date = CURRENT_DATE - 2 THEN 1 ELSE 0 END), 0) as rows_before,
                    COALESCE(SUM(CASE WHEN date = CURRENT_DATE - 1 THEN {rev_col} ELSE 0 END), 0) as rev_yesterday,
                    COALESCE(SUM(CASE WHEN date = CURRENT_DATE - 2 THEN {rev_col} ELSE 0 END), 0) as rev_before,
                    COALESCE(SUM(CASE WHEN date = CURRENT_DATE - 1 THEN marga ELSE 0 END), 0) as marga_yesterday,
                    COALESCE(SUM(CASE WHEN date = CURRENT_DATE - 1 AND marga != 0 THEN 1 ELSE 0 END), 0) as rows_with_marga,
                    COALESCE(SUM(CASE WHEN date = CURRENT_DATE - 2 AND marga != 0 THEN 1 ELSE 0 END), 0) as rows_with_marga_before
                FROM abc_date
                WHERE date >= CURRENT_DATE - 2 AND date < CURRENT_DATE
            """
            cur.execute(query)
            row = cur.fetchone()
            rows_yesterday = row[0]
            rows_before = row[1]
            rev_yesterday = float(row[2])
            rev_before = float(row[3])
            marga_yesterday = float(row[4])
            rows_with_marga = row[5]
            rows_with_marga_before = row[6]

            result['rows_yesterday'] = rows_yesterday
            result['rows_before'] = rows_before

            conn.close()

            if rows_yesterday == 0:
                result['details'] = 'нет данных за вчера'
                return result

            if rows_before > 0 and rows_yesterday < rows_before * 0.8:
                result['details'] = (
                    f'мало данных за вчера: {rows_yesterday} строк '
                    f'(позавчера: {rows_before}, порог 80%)'
                )
                return result

            # 3. Проверка ПОЛНОТЫ финансовых данных
            rev_pct = (rev_yesterday / rev_before * 100) if rev_before > 0 else 0
            marga_fill_pct = (rows_with_marga / rows_with_marga_before * 100) if rows_with_marga_before > 0 else 0

            # 3a. SUM(выручка) за вчера >= 50% от позавчера
            if rev_before > 0 and rev_pct < 50:
                result['details'] = (
                    f'выручка за вчера подозрительно низкая: '
                    f'{rev_yesterday:,.0f}₽ vs позавчера {rev_before:,.0f}₽ ({rev_pct:.0f}%, порог 50%)'
                )
                return result

            # 3b. Строк с marga != 0 за вчера >= 50% от позавчера
            if rows_with_marga_before > 0 and marga_fill_pct < 50:
                result['details'] = (
                    f'маржа загружена частично: '
                    f'{rows_with_marga} строк с marga != 0 '
                    f'(позавчера: {rows_with_marga_before}, {marga_fill_pct:.0f}%, порог 50%)'
                )
                return result

            # 3c. Маржа не нулевая (SUM)
            if marga_yesterday == 0:
                result['details'] = (
                    f'строки есть ({rows_yesterday}), '
                    f'но SUM(marga) = 0 — данные ещё не полные'
                )
                return result

            result['has_financial_data'] = True
            result['rev_vs_before_pct'] = rev_pct
            result['marga_fill_pct'] = marga_fill_pct
            result['ready'] = True
            result['details'] = f'OK (выручка {rev_pct:.0f}% от пред. дня, маржа {marga_fill_pct:.0f}% строк)'
            return result

        except Exception as e:
            logger.error(f"Ошибка проверки {db_name}: {e}")
            result['details'] = f'ошибка подключения: {e}'
            return result
