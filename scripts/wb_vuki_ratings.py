"""
Рейтинг карточек WB по модели (через Feedbacks API).

Запуск:
    python scripts/wb_vuki_ratings.py
    python scripts/wb_vuki_ratings.py --model Moon
"""

import argparse
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(message)s")

from shared.clients.wb_client import WBClient
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
# 2. Feedbacks API → агрегация рейтингов
# ---------------------------------------------------------------------------

def fetch_ratings_via_feedbacks(target_nmids: set[int]) -> dict[int, dict]:
    """Загрузить отзывы через WB Feedbacks API, агрегировать по nmId."""
    load_dotenv(PROJECT_ROOT / '.env')

    cabinets = [
        ("ИП", os.getenv("WB_API_KEY_IP", "")),
        ("ООО", os.getenv("WB_API_KEY_OOO", "")),
    ]

    # nmid → list of ratings
    by_nm: dict[int, list[int]] = defaultdict(list)

    for name, api_key in cabinets:
        if not api_key:
            print(f"  Пропускаю {name}: нет API-ключа")
            continue

        print(f"  Загружаю отзывы из кабинета {name}…")
        client = WBClient(api_key=api_key, cabinet_name=name)
        try:
            feedbacks = client.get_all_feedbacks()
            print(f"  {name}: {len(feedbacks)} отзывов всего")

            for fb in feedbacks:
                nm_id = fb.get("nmId") or fb.get("productDetails", {}).get("nmId")
                rating = fb.get("productValuation", 0)
                if nm_id and rating and nm_id in target_nmids:
                    by_nm[nm_id].append(rating)
        finally:
            client.close()

    # Агрегация
    results: dict[int, dict] = {}
    for nm_id, ratings in by_nm.items():
        counts = {s: 0 for s in range(1, 6)}
        for r in ratings:
            if r in counts:
                counts[r] += 1
        results[nm_id] = {
            "rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
            "reviews": len(ratings),
            "stars": counts,
        }

    return results


# ---------------------------------------------------------------------------
# 3. Вывод
# ---------------------------------------------------------------------------

def display(items: list[dict], ratings: dict[int, dict], model: str):
    from datetime import date

    # Сортируем: сначала карточки с отзывами (по убыванию кол-ва), потом без
    items_sorted = sorted(
        items,
        key=lambda it: -(ratings.get(it['nmid'], {}).get('reviews', 0))
    )

    print(f"\n{model} — рейтинг карточек WB ({date.today().isoformat()})")
    print("=" * 68)
    print(f"{'Артикул':<30} {'nmId':>12}  {'Рейтинг':>7}  {'Отзывы':>7}")
    print("-" * 68)

    total_reviews = 0
    weighted_sum = 0.0
    found = 0

    for item in items_sorted:
        r = ratings.get(item['nmid'])
        art = item['artikul']
        nm = item['nmid']
        if r and r['reviews'] > 0:
            print(f"{art:<30} {nm:>12}  {r['rating']:>7.2f}  {r['reviews']:>7}")
            total_reviews += r['reviews']
            weighted_sum += r['rating'] * r['reviews']
            found += 1
        else:
            print(f"{art:<30} {nm:>12}  {'—':>7}  {'—':>7}")

    print("-" * 68)
    if total_reviews:
        avg = weighted_sum / total_reviews
        print(f"{'Средневзвешенный':<30} {'':>12}  {avg:>7.2f}  {total_reviews:>7}")
    print(f"\nКарточек с отзывами: {found}/{len(items)}\n")


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

    nmids = set(it['nmid'] for it in items)
    print(f"Найдено {len(nmids)} nmId")

    print("Запрашиваю рейтинги через WB Feedbacks API…")
    ratings = fetch_ratings_via_feedbacks(nmids)
    print(f"Получены рейтинги для {len(ratings)}/{len(nmids)} карточек")

    display(items, ratings, args.model)


if __name__ == "__main__":
    main()
