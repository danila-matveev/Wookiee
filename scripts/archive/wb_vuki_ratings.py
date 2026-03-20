"""
Рейтинг карточек WB по модели.

Два источника данных:
  1. feedbacks2.wb.ru — публичный API с РЕАЛЬНЫМ рейтингом WB и ВСЕМИ оценками
  2. basket-XX.wbbasket.ru — imt_id карточки для группировки вариантов

Выводит:
  - WB рейтинг карточки (valuation — видимый покупателю, с time-decay)
  - Среднее арифметическое по варианту (из nmValuationDistribution)
  - Всего оценок (feedbackCount, включая без текста)

Запуск:
    python scripts/wb_vuki_ratings.py
    python scripts/wb_vuki_ratings.py --model Moon
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import httpx
import psycopg2
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(message)s")

from shared.config import SUPABASE_ENV_PATH


# ---------------------------------------------------------------------------
# 1. Получить nmId из Supabase
# ---------------------------------------------------------------------------

def get_nmids_by_model(model_osnova: str = "Vuki") -> list[dict]:
    """Supabase: modeli_osnova → modeli → artikuly.nomenklatura_wb."""
    if os.path.exists(SUPABASE_ENV_PATH):
        load_dotenv(SUPABASE_ENV_PATH)

    cfg = {
        'host': os.getenv('POSTGRES_HOST', 'aws-0-eu-central-1.pooler.supabase.com'),
        'port': int(os.getenv('POSTGRES_PORT', 6543)),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', ''),
    }

    conn = psycopg2.connect(**cfg)
    cur = conn.cursor()
    cur.execute("""
        SELECT a.artikul,
               a.nomenklatura_wb,
               m.kod AS model_kod
        FROM artikuly a
        JOIN modeli m ON a.model_id = m.id
        JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
        WHERE LOWER(mo.kod) = %s
          AND a.nomenklatura_wb IS NOT NULL
        ORDER BY a.artikul
    """, (model_osnova.lower(),))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {'artikul': r[0], 'nmid': int(r[1]), 'model_kod': r[2]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 2. WB basket API → imt_id
# ---------------------------------------------------------------------------

def _basket_host(nm_id: int) -> str:
    """Определить хост basket-XX по nmId (актуально на 2026)."""
    vol = nm_id // 100000
    thresholds = [
        (143, "01"), (287, "02"), (431, "03"), (719, "04"),
        (1007, "05"), (1061, "06"), (1115, "07"), (1169, "08"),
        (1313, "09"), (1601, "10"), (1655, "11"), (1919, "12"),
        (2045, "13"), (2189, "14"), (2405, "15"), (2621, "16"),
        (2901, "17"), (3485, "18"), (3879, "19"), (4407, "20"),
        (4999, "21"), (5699, "22"), (6299, "23"),
    ]
    for limit, num in thresholds:
        if vol <= limit:
            return f"basket-{num}"
    return "basket-24"


def get_imt_id(nm_id: int, client: httpx.Client) -> int | None:
    """Получить imt_id карточки по nmId через basket API."""
    host = _basket_host(nm_id)
    vol = nm_id // 100000
    part = nm_id // 1000
    url = f"https://{host}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/info/ru/card.json"
    try:
        resp = client.get(url)
        if resp.status_code == 200:
            return resp.json().get("imt_id")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# 3. feedbacks2.wb.ru → реальный рейтинг WB
# ---------------------------------------------------------------------------

def fetch_card_data(imt_id: int, client: httpx.Client) -> dict | None:
    """Получить рейтинг и распределение оценок по imt_id."""
    url = f"https://feedbacks2.wb.ru/feedbacks/v2/{imt_id}"
    try:
        resp = client.get(url)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def calc_simple_avg(dist: dict) -> tuple[float, int]:
    """Среднее арифметическое из распределения {star: count}."""
    total = sum(int(v) for v in dist.values())
    if total == 0:
        return 0.0, 0
    avg = sum(int(k) * int(v) for k, v in dist.items()) / total
    return round(avg, 2), total


# ---------------------------------------------------------------------------
# 4. Основная логика: сбор рейтингов
# ---------------------------------------------------------------------------

def fetch_all_ratings(items: list[dict]) -> dict[int, dict]:
    """Для каждого nmId получить реальный рейтинг WB."""
    results: dict[int, dict] = {}

    with httpx.Client(timeout=30.0) as client:
        # Шаг 1: получить imt_id для каждого nmId
        nm_to_imt: dict[int, int] = {}
        imt_ids_seen: set[int] = set()

        print("  Определяю imt_id карточек…")
        for i, item in enumerate(items):
            nm = item['nmid']
            imt = get_imt_id(nm, client)
            if imt:
                nm_to_imt[nm] = imt
                imt_ids_seen.add(imt)
            if (i + 1) % 20 == 0:
                print(f"    …{i + 1}/{len(items)} nmId обработано")
            time.sleep(0.05)

        print(f"  Найдено {len(imt_ids_seen)} уникальных карточек (imt_id)")

        # Шаг 2: загрузить рейтинги по уникальным imt_id
        imt_data: dict[int, dict] = {}
        print("  Загружаю рейтинги с feedbacks2.wb.ru…")
        for imt_id in imt_ids_seen:
            data = fetch_card_data(imt_id, client)
            if data:
                imt_data[imt_id] = data
            time.sleep(0.1)

        # Шаг 3: сопоставить nmId → рейтинг варианта
        for item in items:
            nm = item['nmid']
            imt = nm_to_imt.get(nm)
            if not imt or imt not in imt_data:
                continue

            card = imt_data[imt]
            card_rating = card.get('valuation', 0)
            card_reviews = card.get('feedbackCount', 0)

            # Ищем рейтинг конкретного варианта (nm)
            variant_dist = None
            for v in card.get('nmValuationDistribution', []):
                if v.get('nm') == nm:
                    variant_dist = v.get('valuationDistribution')
                    break

            if variant_dist:
                variant_avg, variant_count = calc_simple_avg(variant_dist)
            else:
                variant_avg, variant_count = 0, 0

            results[nm] = {
                'card_rating': float(card_rating) if card_rating else 0.0,
                'card_reviews': int(card_reviews) if card_reviews else 0,
                'variant_avg': variant_avg,        # Простое среднее варианта
                'variant_count': variant_count,    # Оценок у варианта
                'imt_id': imt,
            }

    return results


# ---------------------------------------------------------------------------
# 5. Вывод
# ---------------------------------------------------------------------------

def display(items: list[dict], ratings: dict[int, dict], model: str):
    from datetime import date

    items_with = [it for it in items if it['nmid'] in ratings and ratings[it['nmid']]['variant_count'] > 0]
    items_without = [it for it in items if it not in items_with]

    items_sorted = sorted(
        items_with,
        key=lambda it: -(ratings[it['nmid']]['variant_count'])
    ) + items_without

    print(f"\n{model} — рейтинг карточек WB ({date.today().isoformat()})")
    print("Источник: feedbacks2.wb.ru (все оценки, вкл. без текста)")
    print("=" * 90)
    print(
        f"{'Артикул':<30} {'nmId':>12}  "
        f"{'WB карт':>7}  {'Ср.вар.':>7}  {'Оценки':>7}  {'imt_id':>12}"
    )
    print("-" * 90)

    total_variant_reviews = 0
    variant_weighted_sum = 0.0
    found = 0
    card_ratings_seen: dict[int, float] = {}

    for item in items_sorted:
        r = ratings.get(item['nmid'])
        art = item['artikul']
        nm = item['nmid']
        if r and r['variant_count'] > 0:
            print(
                f"{art:<30} {nm:>12}  "
                f"{r['card_rating']:>7.1f}  {r['variant_avg']:>7.2f}  "
                f"{r['variant_count']:>7}  {r['imt_id']:>12}"
            )
            total_variant_reviews += r['variant_count']
            variant_weighted_sum += r['variant_avg'] * r['variant_count']
            card_ratings_seen[r['imt_id']] = r['card_rating']
            found += 1
        else:
            print(f"{art:<30} {nm:>12}  {'—':>7}  {'—':>7}  {'—':>7}  {'—':>12}")

    print("-" * 90)
    if total_variant_reviews:
        avg_variant = variant_weighted_sum / total_variant_reviews
        # Средневзвешенный WB рейтинг по карточкам
        card_avg = sum(card_ratings_seen.values()) / len(card_ratings_seen) if card_ratings_seen else 0
        print(
            f"{'Итого':<30} {'':>12}  "
            f"{card_avg:>7.1f}  {avg_variant:>7.2f}  {total_variant_reviews:>7}"
        )
    print(f"\nВариантов с оценками: {found}/{len(items)}")
    print(f"WB карт. = рейтинг карточки на сайте (time-decay)")
    print(f"Ср.вар. = простое среднее по варианту (все оценки)\n")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Рейтинг карточек WB по модели")
    parser.add_argument("--model", default="Vuki", help="Модель (default: Vuki)")
    args = parser.parse_args()

    print(f"Ищу nmId для модели «{args.model}» в Supabase…")
    items = get_nmids_by_model(args.model)
    if not items:
        print("Карточки не найдены.")
        sys.exit(1)

    print(f"Найдено {len(items)} nmId")

    print("Запрашиваю рейтинги через публичный API WB…")
    ratings = fetch_all_ratings(items)
    print(f"Получены рейтинги для {len(ratings)}/{len(items)} карточек")

    display(items, ratings, args.model)


if __name__ == "__main__":
    main()
