"""SKU-mapping queries: artikuly statuses, nm-to-article, model statuses.

All queries hit Supabase (artikuly / modeli / modeli_osnova / statusy).
"""

import os
from typing import Optional

import psycopg2
from dotenv import load_dotenv

from shared.config import SUPABASE_ENV_PATH
from shared.model_mapping import map_to_osnova, KNOWN_PHASING_OUT

__all__ = [
    "get_artikuly_statuses",
    "get_artikul_to_submodel_mapping",
    "get_nm_to_article_mapping",
    "get_model_statuses",
    "get_model_statuses_mapped",
    "get_artikuly_full_info",
]


def get_artikuly_statuses(cabinet_name: Optional[str] = None):
    """Получение статусов артикулов из Supabase.

    Args:
        cabinet_name: Фильтр по кабинету ("ИП" или "ООО"). None = без фильтра.
    """
    if os.path.exists(SUPABASE_ENV_PATH):
        load_dotenv(SUPABASE_ENV_PATH)

    supabase_config = {
        'host': os.getenv('POSTGRES_HOST', 'aws-0-eu-central-1.pooler.supabase.com'),
        'port': int(os.getenv('POSTGRES_PORT', 6543)),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    try:
        conn = psycopg2.connect(**supabase_config)
        cur = conn.cursor()

        query = """
        SELECT
            a.artikul,
            s.nazvanie as status,
            mo.kod as model_osnova
        FROM artikuly a
        LEFT JOIN statusy s ON a.status_id = s.id
        LEFT JOIN modeli m ON a.model_id = m.id
        LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
        """
        params: tuple = ()
        if cabinet_name:
            query += """
            JOIN importery i ON m.importer_id = i.id
            WHERE i.nazvanie LIKE %s
            """
            params = (f"%{cabinet_name}%",)
        cur.execute(query, params)
        results = cur.fetchall()

        cur.close()
        conn.close()

        statuses = {}
        for row in results:
            article = row[0]
            status = row[1]
            # Lowercase ключи — WB хранит "wendy/black", Supabase "Wendy/black"
            statuses[article.lower()] = status

        return statuses
    except Exception as e:
        print(f"Предупреждение: не удалось подключиться к Supabase: {e}")
        return {}


def get_artikul_to_submodel_mapping(cabinet_name: Optional[str] = None) -> dict:
    """Маппинг артикул → kod модели из Supabase (VukiN, VukiW, RubyP, ...).

    Returns: {"компбел-ж-бесшов/leo_brown": "VukiN", "vuki/washed_black": "VukiW", ...}
    Ключи lowercase.

    Args:
        cabinet_name: Фильтр по кабинету ("ИП" или "ООО"). None = без фильтра.
    """
    if os.path.exists(SUPABASE_ENV_PATH):
        load_dotenv(SUPABASE_ENV_PATH)

    supabase_config = {
        'host': os.getenv('POSTGRES_HOST', 'aws-0-eu-central-1.pooler.supabase.com'),
        'port': int(os.getenv('POSTGRES_PORT', 6543)),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    try:
        conn = psycopg2.connect(**supabase_config)
        cur = conn.cursor()
        query = """
            SELECT a.artikul, m.kod as model_kod, mo.kod as osnova_kod
            FROM artikuly a
            JOIN modeli m ON a.model_id = m.id
            JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
        """
        params: tuple = ()
        if cabinet_name:
            query += """
            JOIN importery i ON m.importer_id = i.id
            WHERE i.nazvanie LIKE %s
            """
            params = (f"%{cabinet_name}%",)
        cur.execute(query, params)
        result = {}
        for row in cur.fetchall():
            result[row[0].lower()] = {'model_kod': row[1], 'osnova_kod': row[2]}
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Предупреждение: не удалось получить маппинг подмоделей: {e}")
        return {}


def get_nm_to_article_mapping(cabinet_name: Optional[str] = None) -> dict:
    """Маппинг WB nm_id → artikul из Supabase.

    Returns: {123456: 'vuki/black', 789012: 'ruby/red', ...}
    nm_id ключи — int, artikul значения — lowercase.

    Args:
        cabinet_name: Фильтр по кабинету ("ИП" или "ООО"). None = без фильтра.
    """
    if os.path.exists(SUPABASE_ENV_PATH):
        load_dotenv(SUPABASE_ENV_PATH)

    supabase_config = {
        'host': os.getenv('POSTGRES_HOST', 'aws-0-eu-central-1.pooler.supabase.com'),
        'port': int(os.getenv('POSTGRES_PORT', 6543)),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    try:
        conn = psycopg2.connect(**supabase_config)
        cur = conn.cursor()
        query = """
            SELECT nomenklatura_wb, LOWER(artikul)
            FROM artikuly a
            WHERE nomenklatura_wb IS NOT NULL
        """
        params: tuple = ()
        if cabinet_name:
            query += """
            AND EXISTS (
                SELECT 1 FROM modeli m
                JOIN importery i ON m.importer_id = i.id
                WHERE m.id = a.model_id AND i.nazvanie LIKE %s
            )
            """
            params = (f"%{cabinet_name}%",)
        cur.execute(query, params)
        result = {}
        for row in cur.fetchall():
            if row[0]:
                result[int(row[0])] = row[1]
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Предупреждение: не удалось получить маппинг nm_id → artikul: {e}")
        return {}


def get_model_statuses() -> dict:
    """Статусы моделей-основ из Supabase.

    Returns:
        dict: {model_osnova_lower: status_name}
        Пример: {'wendy': 'Продается', 'luna': 'Выводим'}

    Если у модели-основы несколько моделей с разными статусами,
    берётся "худший" (Выводим > Архив > остальные).
    """
    if os.path.exists(SUPABASE_ENV_PATH):
        load_dotenv(SUPABASE_ENV_PATH)

    supabase_config = {
        'host': os.getenv('POSTGRES_HOST', 'aws-0-eu-central-1.pooler.supabase.com'),
        'port': int(os.getenv('POSTGRES_PORT', 6543)),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    try:
        conn = psycopg2.connect(**supabase_config)
        cur = conn.cursor()

        query = """
        SELECT
            LOWER(mo.kod) as model_osnova,
            s.nazvanie as status
        FROM modeli m
        LEFT JOIN statusy s ON m.status_id = s.id
        LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
        WHERE mo.kod IS NOT NULL AND s.nazvanie IS NOT NULL
        ORDER BY mo.kod
        """
        cur.execute(query)
        results = cur.fetchall()

        cur.close()
        conn.close()

        # Если у модели-основы несколько записей — приоритет: Выводим > Архив > остальные
        priority = {'Выводим': 0, 'Архив': 1}
        statuses = {}
        for row in results:
            model = row[0]
            status = row[1]
            if model not in statuses:
                statuses[model] = status
            else:
                cur_priority = priority.get(statuses[model], 99)
                new_priority = priority.get(status, 99)
                if new_priority < cur_priority:
                    statuses[model] = status

        return statuses
    except Exception as e:
        print(f"Предупреждение: не удалось получить статусы моделей: {e}")
        return {}


def get_model_statuses_mapped() -> dict:
    """Статусы моделей, приведённые к именам из отчёта (через MODEL_OSNOVA_MAPPING).

    Returns:
        dict: {mapped_model_name: status}
        Пример: {'Vuki': 'Продается', 'Other': 'Выводим', 'Olivia': 'Выводим'}

    Логика:
    1. get_model_statuses() → статусы по modeli_osnova.kod
    2. get_artikuly_statuses() → fallback для моделей без записи в modeli
    3. Перепроецировать ключи через map_to_osnova()
    4. Агрегировать: worst-status-wins (Выводим > Архив > остальные)
    5. Fallback: KNOWN_PHASING_OUT для моделей без записи нигде
    """

    # Best-status-wins: если хоть одна подмодель продаётся, группа активна.
    # Продается побеждает Выводим при агрегации в одну группу (напр. "Vuki").
    best_priority = {
        'Продается': 0, 'Запуск': 1, 'Новый': 2,
        'Подготовка': 3, 'Выводим': 4, 'Архив': 5,
    }

    # 1. Статусы из modeli → modeli_osnova
    raw_statuses = get_model_statuses()  # {"mia": "Выводим", "vuki": "Продается", ...}

    # 2. Artikuly-level fallback: извлекаем модель из артикула (до '/')
    artikuly_statuses = get_artikuly_statuses()  # {"olivia/black": "Выводим", ...}

    artikuly_model_statuses = {}
    for artikul, status in artikuly_statuses.items():
        if not status:
            continue
        raw_model = artikul.split('/')[0].strip().lower()
        if raw_model and raw_model not in raw_statuses:
            if raw_model not in artikuly_model_statuses:
                artikuly_model_statuses[raw_model] = status
            else:
                cur_p = best_priority.get(artikuly_model_statuses[raw_model], 99)
                new_p = best_priority.get(status, 99)
                if new_p < cur_p:
                    artikuly_model_statuses[raw_model] = status

    # 3. Объединяем: raw_statuses имеют приоритет над artikuly
    all_raw = {**artikuly_model_statuses, **raw_statuses}

    # 3.5. Бизнес-правило: переопределяем статус для подтверждённо выводимых моделей
    for raw_name in KNOWN_PHASING_OUT:
        all_raw[raw_name] = 'Выводим'

    # 4. Перепроецируем через MODEL_OSNOVA_MAPPING → ключи отчёта
    #    Best-status-wins: "Vuki" = Продается (vuki) + Выводим (компбел) → Продается
    mapped = {}
    for raw_key, status in all_raw.items():
        mapped_name = map_to_osnova(raw_key)
        if mapped_name not in mapped:
            mapped[mapped_name] = status
        else:
            cur_p = best_priority.get(mapped[mapped_name], 99)
            new_p = best_priority.get(status, 99)
            if new_p < cur_p:
                mapped[mapped_name] = status

    return mapped


def get_artikuly_full_info():
    """Расширенная информация об артикулах из Supabase: статус, цвет, склейка."""
    if os.path.exists(SUPABASE_ENV_PATH):
        load_dotenv(SUPABASE_ENV_PATH)

    supabase_config = {
        'host': os.getenv('POSTGRES_HOST', 'aws-0-eu-central-1.pooler.supabase.com'),
        'port': int(os.getenv('POSTGRES_PORT', 6543)),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    try:
        conn = psycopg2.connect(**supabase_config)
        cur = conn.cursor()

        query = """
        SELECT DISTINCT ON (a.artikul)
            a.artikul,
            s.nazvanie as status,
            m.kod as model_kod,
            mo.kod as model_osnova,
            c.color_code,
            c.cvet,
            c.color,
            sw.nazvanie as skleyka_wb,
            mo.tip_kollekcii
        FROM artikuly a
        LEFT JOIN statusy s ON a.status_id = s.id
        LEFT JOIN modeli m ON a.model_id = m.id
        LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
        LEFT JOIN cveta c ON a.cvet_id = c.id
        LEFT JOIN tovary t ON t.artikul_id = a.id
        LEFT JOIN tovary_skleyki_wb tsw ON tsw.tovar_id = t.id
        LEFT JOIN skleyki_wb sw ON tsw.skleyka_id = sw.id
        ORDER BY a.artikul, sw.nazvanie
        """
        cur.execute(query)
        rows = cur.fetchall()

        cur.close()
        conn.close()

        result = {}
        for r in rows:
            artikul = r[0]
            result[artikul.lower()] = {
                'status': r[1],
                'model_kod': r[2],
                'model_osnova': r[3],
                'color_code': r[4],
                'cvet': r[5],
                'color': r[6],
                'skleyka_wb': r[7],
                'tip_kollekcii': r[8],
            }
        return result
    except Exception as e:
        print(f"Предупреждение: не удалось подключиться к Supabase: {e}")
        return {}
