"""Коллектор товарной иерархии из Supabase: модели, цвета, коллекции, статусы."""
from __future__ import annotations

from collections import defaultdict

from shared.data_layer.sku_mapping import get_artikuly_full_info

# Статусы, участвующие в активном анализе
_ACTIVE_STATUSES = {"Продается", "Выводим", "Новый", "Запуск"}


def collect_hierarchy() -> dict:
    """Собирает полную товарную иерархию из Supabase.

    Returns:
        {"hierarchy": {
            "articles": {article: {status, model_osnova, color_code, tip_kollekcii, active}},
            "color_code_groups": {(tip_kollekcii, color_code): {articles, models, statuses}},
            "status_counts": {status: count},
        }}
    """
    raw = get_artikuly_full_info()

    articles: dict[str, dict] = {}
    color_groups: dict[tuple, dict] = defaultdict(
        lambda: {"articles": [], "models": set(), "statuses": set()}
    )
    status_counts: dict[str, int] = defaultdict(int)

    for article, info in raw.items():
        status = info.get("status", "")
        model_osnova = info.get("model_osnova", "")
        color_code = info.get("color_code", "")
        tip_kol = info.get("tip_kollekcii", "")
        active = status in _ACTIVE_STATUSES

        articles[article] = {
            "status": status,
            "model_kod": info.get("model_kod", ""),
            "model_osnova": model_osnova,
            "color_code": color_code,
            "cvet": info.get("cvet", ""),
            "color": info.get("color", ""),
            "tip_kollekcii": tip_kol,
            "active": active,
        }

        status_counts[status] += 1

        if color_code and tip_kol:
            key = (tip_kol, color_code)
            color_groups[key]["articles"].append(article)
            color_groups[key]["models"].add(model_osnova)
            color_groups[key]["statuses"].add(status)

    # Конвертируем set → list, tuple-ключи → string для JSON-сериализации
    serializable_groups = {}
    for key, group in color_groups.items():
        str_key = f"{key[0]}|{key[1]}"
        serializable_groups[str_key] = {
            "tip_kollekcii": key[0],
            "color_code": key[1],
            "articles": group["articles"],
            "models": sorted(group["models"]),
            "statuses": sorted(group["statuses"]),
        }

    return {
        "hierarchy": {
            "articles": articles,
            "color_code_groups": serializable_groups,
            "status_counts": dict(status_counts),
        }
    }
