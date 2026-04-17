"""Daily Brief — детектор паттернов и флагов.

Ищет:
- Multi-day streaks (модель в красной/зелёной зоне N дней подряд)
- Top movers (самые растущие / падающие по марже)
- Аномалии (выброс >2σ от среднего)
"""
from __future__ import annotations
from typing import Any


# Пороги
MARGINALITY_TARGET_MIN = 20.0  # %
MARGINALITY_CRITICAL = 10.0  # %
STREAK_MIN_DAYS = 2
TOP_N_MOVERS = 3


def detect_model_radar(
    models_day: list[dict],
    models_mtd: list[dict],
) -> dict:
    """Топ растущих / падающих моделей по марже (день + MTD).

    Args:
        models_day: wb_models_day или ozon_models_day за один день (current + previous rows)
        models_mtd: модели за MTD (current + previous rows — previous тут не используется)

    Returns:
        dict с growing / declining / critical.
    """
    # Group by model name; separate current (target day) and previous (day before)
    grouped: dict[str, dict] = {}
    for row in models_day:
        m = row["model"]
        if not m:
            continue
        grouped.setdefault(m, {})[row["period"]] = row

    # Compute margin deltas day-over-day (today vs yesterday)
    movers = []
    for model, periods in grouped.items():
        cur = periods.get("current", {})
        prev = periods.get("previous", {})
        margin_cur = float(cur.get("margin") or 0)
        margin_prev = float(prev.get("margin") or 0)
        if margin_cur == 0 and margin_prev == 0:
            continue
        delta_abs = margin_cur - margin_prev
        delta_pct = (delta_abs / abs(margin_prev) * 100) if margin_prev else None

        revenue_cur = float(cur.get("revenue_before_spp") or 0)
        marginality = (margin_cur / revenue_cur * 100) if revenue_cur else None

        movers.append({
            "model": model,
            "margin_today": round(margin_cur),
            "margin_yesterday": round(margin_prev),
            "delta_abs": round(delta_abs),
            "delta_pct": round(delta_pct, 1) if delta_pct is not None else None,
            "marginality_pct": round(marginality, 1) if marginality is not None else None,
            "revenue_today": round(revenue_cur),
        })

    growing = sorted(
        [m for m in movers if m["delta_abs"] > 0],
        key=lambda x: x["delta_abs"],
        reverse=True,
    )[:TOP_N_MOVERS]

    declining = sorted(
        [m for m in movers if m["delta_abs"] < 0],
        key=lambda x: x["delta_abs"],
    )[:TOP_N_MOVERS]

    # Critical: любая модель с маржинальностью < MARGINALITY_CRITICAL
    critical = [m for m in movers if m.get("marginality_pct") is not None
                and m["marginality_pct"] < MARGINALITY_CRITICAL]
    critical = sorted(critical, key=lambda x: (x["marginality_pct"] or 0))

    return {
        "growing": growing,
        "declining": declining,
        "critical_marginality": critical,
    }


def detect_marginality_flags(brand_metrics: dict) -> list[dict]:
    """Флаги по маржинальности бренда.

    Args:
        brand_metrics: dict с 'marginality_pct' (вчера) и 'marginality_target'

    Returns:
        list флагов.
    """
    flags = []
    marg = brand_metrics.get("marginality_pct")
    if marg is None:
        return flags
    if marg < MARGINALITY_CRITICAL:
        flags.append({
            "severity": "critical", "severity_ru": "критично",
            "type": "marginality_critical",
            "message": f"Маржинальность {marg:.1f}% — критическая зона (<{MARGINALITY_CRITICAL}%)",
        })
    elif marg < MARGINALITY_TARGET_MIN:
        flags.append({
            "severity": "warning", "severity_ru": "предупреждение",
            "type": "marginality_below_target",
            "message": f"Маржинальность {marg:.1f}% — ниже целевой ({MARGINALITY_TARGET_MIN}%)",
        })
    return flags


def detect_pace_flag(gap: dict) -> list[dict]:
    """Флаг по темпу выполнения плана.

    Если gap_pct <= -5% → warning, <= -10% → critical.
    """
    flags = []
    gap_pct = gap.get("gap_pct", 0)
    gap_abs = gap.get("gap_abs", 0)
    if gap_pct <= -10:
        flags.append({
            "severity": "critical", "severity_ru": "критично",
            "type": "pace_far_behind",
            "message": f"Прогноз отстаёт от плана на {abs(gap_pct):.1f}% ({int(gap_abs/1000):+}К ₽)",
        })
    elif gap_pct <= -5:
        flags.append({
            "severity": "warning", "severity_ru": "предупреждение",
            "type": "pace_behind",
            "message": f"Прогноз отстаёт от плана на {abs(gap_pct):.1f}% ({int(gap_abs/1000):+}К ₽)",
        })
    elif gap_pct >= 5:
        flags.append({
            "severity": "info", "severity_ru": "инфо",
            "type": "pace_ahead",
            "message": f"Прогноз опережает план на {gap_pct:.1f}% ({int(gap_abs/1000):+}К ₽)",
        })
    return flags


def detect_ad_anomaly(series: list[dict], target_date: str) -> list[dict]:
    """Аномалия в рекламных расходах за target_date.

    Если расход >+30% от средней за предыдущие 7 дней → флаг.
    """
    flags = []
    valid = [d for d in series if "error" not in d]
    target_day = next((d for d in valid if d["date"] == target_date), None)
    if not target_day:
        return flags

    # Предыдущие 7 дней (исключая target)
    idx = valid.index(target_day)
    prev_window = valid[max(0, idx - 7):idx]
    if not prev_window:
        return flags

    target_ad = float(target_day.get("wb_ad_internal", 0) or 0) + float(target_day.get("wb_ad_external", 0) or 0)
    avg_ad = sum(
        float(d.get("wb_ad_internal", 0) or 0) + float(d.get("wb_ad_external", 0) or 0)
        for d in prev_window
    ) / len(prev_window)
    if avg_ad == 0:
        return flags
    delta_pct = (target_ad - avg_ad) / avg_ad * 100

    if delta_pct >= 30:
        flags.append({
            "severity": "info", "severity_ru": "инфо",
            "type": "ad_spike",
            "message": f"Рекламный расход WB {round(target_ad):,}₽ (+{delta_pct:.0f}% к среднему 7 дней)",
            "delta_pct": round(delta_pct),
        })
    elif delta_pct <= -30:
        flags.append({
            "severity": "info", "severity_ru": "инфо",
            "type": "ad_drop",
            "message": f"Рекламный расход WB {round(target_ad):,}₽ ({delta_pct:+.0f}% к среднему 7 дней)",
            "delta_pct": round(delta_pct),
        })
    return flags


def compute_trends(series: list[dict]) -> dict:
    """Тренды последних N дней vs начало месяца."""
    valid = [d for d in series if "error" not in d]
    if len(valid) < 4:
        return {"margin_direction": "insufficient_data"}

    def _brand(d: dict, key: str) -> float:
        return float(d.get(f"wb_{key}", 0) or 0) + float(d.get(f"ozon_{key}", 0) or 0)

    # Последние 5 дней vs первые 5
    last5 = valid[-5:]
    first5 = valid[:5] if len(valid) >= 10 else valid[:len(valid) // 2 or 1]

    def _avg(lst: list[dict], key: str) -> float:
        return sum(_brand(d, key) for d in lst) / len(lst) if lst else 0

    margin_last = _avg(last5, "margin")
    margin_first = _avg(first5, "margin")
    margin_delta_pct = ((margin_last - margin_first) / margin_first * 100) if margin_first else 0

    orders_last = _avg(last5, "orders")
    orders_first = _avg(first5, "orders")
    orders_delta_pct = ((orders_last - orders_first) / orders_first * 100) if orders_first else 0

    def _direction(delta_pct: float) -> str:
        if delta_pct >= 5:
            return "up"
        if delta_pct <= -5:
            return "down"
        return "flat"

    return {
        "margin_direction": _direction(margin_delta_pct),
        "margin_delta_pct": round(margin_delta_pct, 1),
        "margin_last5_avg": round(margin_last),
        "margin_first5_avg": round(margin_first),
        "orders_direction": _direction(orders_delta_pct),
        "orders_delta_pct": round(orders_delta_pct, 1),
    }


# ==== Воронка ====

def detect_funnel_flags(funnel_series: list[dict]) -> list[dict]:
    """Флаги по дневной воронке.

    Сравнивает вчерашний день с средним за предыдущие 4 дня:
    - Просмотры карточки упали >= 20% → warning
    - Конверсия в корзину упала >= 1.5 пп → warning
    - Конверсия в заказ упала >= 3 пп → warning
    - Выкуп лагирующий (обычно 0 на вчера) — не флагуем
    """
    flags = []
    valid = [d for d in funnel_series if "error" not in d]
    if len(valid) < 2:
        return flags
    today = valid[-1]
    prev = valid[:-1]

    def _avg(key: str) -> float:
        nums = [d.get(key) for d in prev if d.get(key) is not None]
        return sum(nums) / len(nums) if nums else 0.0

    card_avg = _avg("card_opens")
    if card_avg and today.get("card_opens") is not None:
        delta_pct = (today["card_opens"] - card_avg) / card_avg * 100
        if delta_pct <= -20:
            flags.append({
                "severity": "warning", "severity_ru": "предупреждение",
                "type": "funnel_views_drop",
                "message": f"Просмотры карточки {today['card_opens']:,} — на {abs(delta_pct):.0f}% ниже среднего за 4 дня ({int(card_avg):,})",
            })

    cart_avg = _avg("cr_to_cart_pct")
    if cart_avg and today.get("cr_to_cart_pct") is not None:
        delta_pp = today["cr_to_cart_pct"] - cart_avg
        if delta_pp <= -1.5:
            flags.append({
                "severity": "warning", "severity_ru": "предупреждение",
                "type": "funnel_cart_drop",
                "message": f"Конверсия в корзину {today['cr_to_cart_pct']:.2f}% (−{abs(delta_pp):.2f} п.п. к среднему)",
            })

    order_avg = _avg("cr_to_order_pct")
    if order_avg and today.get("cr_to_order_pct") is not None:
        delta_pp = today["cr_to_order_pct"] - order_avg
        if delta_pp <= -3:
            flags.append({
                "severity": "warning", "severity_ru": "предупреждение",
                "type": "funnel_order_drop",
                "message": f"Конверсия в заказ {today['cr_to_order_pct']:.2f}% (−{abs(delta_pp):.2f} п.п. к среднему)",
            })
    return flags


# ==== Last-N-days summary ====

def build_last_days_table(daily_series: list[dict], days: int = 5) -> list[dict]:
    """Собирает таблицу последних N дней для дневного brief.

    Поля на строку:
    - date
    - margin, marginality_pct (от выручки), revenue
    - orders_count, orders_rub (сумма заказов в рублях)
    - ad_internal, ad_external, ad_total
    - ad_share_of_orders_pct (доля рекламы от СУММЫ ЗАКАЗОВ, не от выручки!
                              Реклама влияет на заказы, выручка формируется позже выкупами).
    """
    valid = [d for d in daily_series if "error" not in d]
    last = valid[-days:]
    rows = []
    for d in last:
        revenue = float(d.get("wb_revenue", 0) or 0) + float(d.get("ozon_revenue", 0) or 0)
        margin = float(d.get("wb_margin", 0) or 0) + float(d.get("ozon_margin", 0) or 0)
        orders_count = int(d.get("wb_orders", 0) or 0) + int(d.get("ozon_orders", 0) or 0)
        orders_rub = float(d.get("wb_orders_rub", 0) or 0) + float(d.get("ozon_orders_rub", 0) or 0)
        ad_internal = float(d.get("wb_ad_internal", 0) or 0) + float(d.get("ozon_ad_internal", 0) or 0)
        ad_external = float(d.get("wb_ad_external", 0) or 0)
        ad_total = ad_internal + ad_external
        marginality = (margin / revenue * 100) if revenue else None
        ad_share_orders = (ad_total / orders_rub * 100) if orders_rub else None
        rows.append({
            "date": d["date"],
            "margin": round(margin),
            "marginality_pct": round(marginality, 1) if marginality is not None else None,
            "revenue": round(revenue),
            "orders_count": orders_count,
            "orders_rub": round(orders_rub),
            "ad_internal": round(ad_internal),
            "ad_external": round(ad_external),
            "ad_total": round(ad_total),
            "ad_share_of_orders_pct": round(ad_share_orders, 2) if ad_share_orders is not None else None,
        })
    return rows


# ==== Прогноз по динамике заказов (опережающий индикатор) ====

def compute_orders_momentum(daily_series: list[dict]) -> dict:
    """Анализ тренда суммы заказов как опережающего индикатора для выручки и маржи.

    Логика: заказы сегодня → выручка через 3-21 день (после выкупа) → маржа следом.
    Если заказы растут сейчас — через 1-3 недели вырастут выручка и маржа.
    Если падают — соответственно.

    Сравниваем:
    - Последние 5 дней vs предыдущие 5 дней (последние 10 дней разбиваем на две половины)
    - Последние 3 дня vs предыдущие 3 дня (быстрый сигнал)
    """
    valid = [d for d in daily_series if "error" not in d]
    if len(valid) < 6:
        return {"status": "insufficient_data", "days": len(valid)}

    def _orders_rub(d: dict) -> float:
        return float(d.get("wb_orders_rub", 0) or 0) + float(d.get("ozon_orders_rub", 0) or 0)

    def _orders_count(d: dict) -> int:
        return int(d.get("wb_orders", 0) or 0) + int(d.get("ozon_orders", 0) or 0)

    # Последние 5 vs предыдущие 5
    last5 = valid[-5:]
    prev5 = valid[-10:-5] if len(valid) >= 10 else valid[:max(1, len(valid) - 5)]

    def _avg(lst, fn):
        return sum(fn(d) for d in lst) / len(lst) if lst else 0

    last5_orders_rub = _avg(last5, _orders_rub)
    prev5_orders_rub = _avg(prev5, _orders_rub)
    delta5_rub_pct = ((last5_orders_rub - prev5_orders_rub) / prev5_orders_rub * 100) if prev5_orders_rub else 0

    last5_orders_count = _avg(last5, _orders_count)
    prev5_orders_count = _avg(prev5, _orders_count)
    delta5_count_pct = ((last5_orders_count - prev5_orders_count) / prev5_orders_count * 100) if prev5_orders_count else 0

    # Последние 3 vs предыдущие 3 (более быстрый сигнал)
    last3 = valid[-3:]
    prev3 = valid[-6:-3] if len(valid) >= 6 else None

    if prev3:
        last3_orders_rub = _avg(last3, _orders_rub)
        prev3_orders_rub = _avg(prev3, _orders_rub)
        delta3_rub_pct = ((last3_orders_rub - prev3_orders_rub) / prev3_orders_rub * 100) if prev3_orders_rub else 0
    else:
        last3_orders_rub = prev3_orders_rub = delta3_rub_pct = 0

    def _direction(delta_pct: float) -> str:
        if delta_pct >= 5:
            return "растёт"
        if delta_pct <= -5:
            return "падает"
        return "стабильно"

    # Interpretation
    # Если последние 5 дней заказы растут — ожидаем рост маржи через 3-21 день
    # Если падают — ожидаем падение маржи
    direction_5d = _direction(delta5_rub_pct)
    direction_3d = _direction(delta3_rub_pct)

    # Сигнал для прогноза маржи
    if direction_5d == "растёт" and direction_3d == "растёт":
        forecast_signal = "положительный"
        forecast_note = "Заказы устойчиво растут — ожидаем рост выручки и маржи в ближайшие 3-21 день (по мере выкупа)."
    elif direction_5d == "падает" and direction_3d == "падает":
        forecast_signal = "отрицательный"
        forecast_note = "Заказы устойчиво падают — через 3-21 день жди снижения выручки и маржи. Действовать сейчас, чтобы переломить тренд."
    elif direction_5d == "растёт" and direction_3d == "падает":
        forecast_signal = "смешанный_разворот_вниз"
        forecast_note = "За 5 дней была положительная динамика, но в последние 3 дня заказы пошли вниз. Разворот — следить внимательно."
    elif direction_5d == "падает" and direction_3d == "растёт":
        forecast_signal = "смешанный_разворот_вверх"
        forecast_note = "За 5 дней был спад, но последние 3 дня тенденция к росту. Возможно, разворот к восстановлению."
    else:
        forecast_signal = "стабильный"
        forecast_note = "Заказы стабильны — маржа и выручка будут двигаться в плавном темпе без резких изменений."

    return {
        "last_5_days_orders_rub_avg": round(last5_orders_rub),
        "prev_5_days_orders_rub_avg": round(prev5_orders_rub),
        "delta_5d_rub_pct": round(delta5_rub_pct, 1),
        "last_5_days_orders_count_avg": round(last5_orders_count),
        "prev_5_days_orders_count_avg": round(prev5_orders_count),
        "delta_5d_count_pct": round(delta5_count_pct, 1),
        "last_3_days_orders_rub_avg": round(last3_orders_rub),
        "prev_3_days_orders_rub_avg": round(prev3_orders_rub),
        "delta_3d_rub_pct": round(delta3_rub_pct, 1),
        "direction_5d": direction_5d,
        "direction_3d": direction_3d,
        "forecast_signal": forecast_signal,
        "forecast_note": forecast_note,
    }


# ==== Маркетинговый контекст ====

def build_marketing_context(marketing_sheets: dict) -> dict:
    """Выжимка по маркетингу из Sheets: что было за 7 дней, что запланировано.

    Возвращает:
    - bloggers_recent_count / spend / orders
    - bloggers_upcoming_count / spend
    - vk_recent_count / spend
    - smm_summary
    - availability: какие листы работают
    """
    ctx = {
        "bloggers": {"available": False, "recent": {}, "upcoming": {}, "top_recent": []},
        "vk": {"available": False, "recent": {}},
        "smm": {"available": False},
    }
    if not marketing_sheets or "error" in marketing_sheets:
        return ctx

    bl = marketing_sheets.get("bloggers") or {}
    if "error" not in bl:
        ctx["bloggers"]["available"] = True
        ctx["bloggers"]["recent"] = bl.get("totals", {}).get("recent", {})
        ctx["bloggers"]["upcoming"] = bl.get("totals", {}).get("upcoming", {})
        # Топ-5 по расходу за период
        ctx["bloggers"]["top_recent"] = sorted(
            bl.get("recent", []),
            key=lambda x: x.get("spend", 0),
            reverse=True,
        )[:5]
        ctx["bloggers"]["upcoming_list"] = bl.get("upcoming", [])

    vk = marketing_sheets.get("vk") or {}
    if "error" not in vk:
        ctx["vk"]["available"] = True
        ctx["vk"]["recent"] = vk.get("totals", {})
        ctx["vk"]["items"] = vk.get("recent", [])[:5]

    smm = marketing_sheets.get("smm_week") or {}
    if "error" not in smm and smm.get("last_row_date"):
        ctx["smm"]["available"] = True
        ctx["smm"]["last_row_date"] = smm["last_row_date"]
        ctx["smm"]["numeric_values"] = smm.get("numeric_values", [])

    return ctx
