"""
Funnel Report Builder — generates the full funnel report in Markdown
from pre-fetched data bundle. No LLM needed for formatting.

Matches the V3 reference format:
- Brand overview table
- Per-model toggle sections with funnel/economics/articles/hypotheses
- Conclusions with ФАКТ→ГИПОТЕЗА→ДЕЙСТВИЕ→ЭФФЕКТ
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _fmt_num(val, suffix: str = "") -> str:
    """Format number with thousands separator."""
    if val is None:
        return "—"
    if isinstance(val, float):
        if abs(val) >= 1000:
            return f"{val:,.0f}{suffix}".replace(",", " ")
        return f"{val:.1f}{suffix}"
    return f"{val:,}{suffix}".replace(",", " ")


def _fmt_pct(val, suffix: str = "%") -> str:
    if val is None or val == 0:
        return "—"
    return f"{val:.1f}{suffix}"


def _fmt_delta_pct(val) -> str:
    if val is None or val == 0:
        return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.1f}%"


def _fmt_delta_pp(val) -> str:
    if val is None or val == 0:
        return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}pp"


def _model_headline(model_data: dict) -> str:
    """Generate model headline like 'Wendy — падение заказов -16.2%'."""
    name = model_data["model"].title()
    changes = model_data["funnel_totals"].get("changes", {})
    orders_delta = changes.get("заказы_delta_pct", 0)

    if orders_delta > 20:
        return f"{name} — рост заказов {_fmt_delta_pct(orders_delta)}"
    elif orders_delta < -15:
        return f"{name} — падение заказов {_fmt_delta_pct(orders_delta)}"
    elif orders_delta > 5:
        return f"{name} — рост заказов {_fmt_delta_pct(orders_delta)}"
    elif orders_delta < -5:
        return f"{name} — снижение заказов {_fmt_delta_pct(orders_delta)}"

    opens_delta = changes.get("переходы_delta_pct", 0)
    if opens_delta > 30:
        return f"{name} — рост переходов {_fmt_delta_pct(opens_delta)}"
    elif opens_delta < -20:
        return f"{name} — падение переходов {_fmt_delta_pct(opens_delta)}"

    return f"{name} — заказы стабильны"


def _calc_cr(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator * 100, 2)


def _build_model_section(m: dict) -> str:
    """Build markdown section for one model."""
    curr = m["funnel_totals"]["current"]
    prev = m["funnel_totals"]["previous"]
    changes = m["funnel_totals"]["changes"]
    econ = m["economics"]
    organic = m["organic"]
    sig_articles = m.get("significant_articles", [])

    headline = _model_headline(m)

    # --- Funnel table ---
    c_opens = curr.get("переходы", 0)
    c_cart = curr.get("корзина", 0)
    c_orders = curr.get("заказы", 0)
    c_buyouts = curr.get("выкупы", 0)

    p_opens = prev.get("переходы", 0)
    p_cart = prev.get("корзина", 0)
    p_orders = prev.get("заказы", 0)
    p_buyouts = prev.get("выкупы", 0)

    # CR current
    cr_open_cart_c = _calc_cr(c_cart, c_opens)
    cr_cart_order_c = _calc_cr(c_orders, c_cart)
    cro_c = _calc_cr(c_orders, c_opens)
    crp_c = _calc_cr(c_buyouts, c_opens)

    # CR previous
    cr_open_cart_p = _calc_cr(p_cart, p_opens)
    cr_cart_order_p = _calc_cr(p_orders, p_cart)
    cro_p = _calc_cr(p_orders, p_opens)
    crp_p = _calc_cr(p_buyouts, p_opens)

    lines = []
    lines.append(f"## \u25b6 Модель: {headline}")
    lines.append("\t### Воронка")
    lines.append("\t| Метрика | Текущая | Предыдущая | Изменение |")
    lines.append("\t|---------|---------|-----------|-----------|")
    lines.append(f"\t| Переходы | {_fmt_num(c_opens)} | {_fmt_num(p_opens)} | {_fmt_delta_pct(changes.get('переходы_delta_pct', 0))} |")
    lines.append(f"\t| Корзина | {_fmt_num(c_cart)} | {_fmt_num(p_cart)} | {_fmt_delta_pct(_safe_pct(c_cart, p_cart))} |")
    lines.append(f"\t| Заказы | {_fmt_num(c_orders)} | {_fmt_num(p_orders)} | {_fmt_delta_pct(changes.get('заказы_delta_pct', 0))} |")
    lines.append(f"\t| Выкупы* | {_fmt_num(c_buyouts)} | {_fmt_num(p_buyouts)} | {_fmt_delta_pct(changes.get('выкупы_delta_pct', 0))} |")
    lines.append(f"\t| Конверсия переход→корзина | {_fmt_pct(cr_open_cart_c)} | {_fmt_pct(cr_open_cart_p)} | {_fmt_delta_pp(cr_open_cart_c - cr_open_cart_p)} |")
    lines.append(f"\t| Конверсия корзина→заказ | {_fmt_pct(cr_cart_order_c)} | {_fmt_pct(cr_cart_order_p)} | {_fmt_delta_pp(cr_cart_order_c - cr_cart_order_p)} |")
    lines.append(f"\t| CRO (переход→заказ) | {_fmt_pct(cro_c)} | {_fmt_pct(cro_p)} | {_fmt_delta_pp(cro_c - cro_p)} |")
    lines.append(f"\t| CRP (переход→выкуп)* | {_fmt_pct(crp_c)} | {_fmt_pct(crp_p)} | {_fmt_delta_pp(crp_c - crp_p)} |")

    # --- Economics table ---
    lines.append("\t### Экономика")
    lines.append("\t| Метрика | Значение |")
    lines.append("\t|---------|----------|")
    lines.append(f"\t| Выручка | {_fmt_num(econ.get('выручка', 0))} ₽ |")
    lines.append(f"\t| Маржа | {_fmt_num(econ.get('маржа', 0))} ₽ |")
    lines.append(f"\t| ДРР | {_fmt_pct(econ.get('дрр_pct', 0))} |")
    lines.append(f"\t| ROMI | {_fmt_pct(econ.get('romi_pct', 0))} |")
    lines.append(f"\t| Доля органики (переходы) | {_fmt_pct(organic.get('доля_органики_переходы_pct', 0))} |")
    lines.append(f"\t| Доля органики (заказы) | {_fmt_pct(organic.get('доля_органики_заказы_pct', 0))} |")

    # --- Significant articles ---
    if sig_articles:
        lines.append("\t### Значимые артикулы")
        lines.append("\t| Артикул | Переходы | Заказы | Флаги |")
        lines.append("\t|---------|----------|--------|-------|")
        for a in sig_articles:
            flags_str = ", ".join(a.get("flags", []))
            lines.append(f"\t| {a['artikul']} | {_fmt_num(a.get('переходы', 0))} | {_fmt_num(a.get('заказы', 0))} | {flags_str} |")

    # --- Hypotheses ---
    hypotheses = _generate_hypotheses(m)
    if hypotheses:
        lines.append("\t**Гипотезы:**")
        for h in hypotheses:
            lines.append(f"\t- {h}")

    lines.append("\t---")
    return "\n".join(lines)


def _generate_hypotheses(m: dict) -> list[str]:
    """Generate data-driven hypotheses for a model."""
    hypotheses = []
    sig = m.get("significant_articles", [])

    # Group by growth/decline
    growers = []
    decliners = []
    mixed = []

    for a in sig:
        flags = a.get("flags", [])
        has_growth = any("+" in f for f in flags)
        has_decline = any("-" in f for f in flags)
        if has_growth and has_decline:
            mixed.append(a)
        elif has_growth:
            growers.append(a)
        elif has_decline:
            decliners.append(a)

    # Mixed signals (traffic up, orders down) → likely poor conversion
    for a in mixed:
        flags_str = ", ".join(a["flags"])
        hypotheses.append(
            f"**{a['artikul']}**: {flags_str}. "
            f"Возможно, привлечён нецелевой трафик по новым ключевым словам "
            f"или изменилась позиция по нерелевантным запросам."
        )

    # Strong growers
    if growers:
        names = [a["artikul"] for a in growers[:3]]
        flags_parts = []
        for a in growers[:3]:
            flags_parts.append(f"{a['artikul']}: {', '.join(a['flags'])}")
        hypotheses.append(
            f"**{', '.join(names)}**: {'; '.join(flags_parts)}. "
            f"Возможно, улучшились позиции по ключевым словам."
        )

    # Decliners
    if decliners:
        names = [a["artikul"] for a in decliners[:4]]
        decline_info = []
        for a in decliners[:4]:
            decline_info.append(f"{a['artikul']}: {', '.join(a['flags'])}")
        hypotheses.append(
            f"**{', '.join(names)}**: {'; '.join(decline_info)}. "
            f"Возможно, ухудшились позиции по ключевым словам, "
            f"нехватка размеров или выросла конкуренция."
        )

    return hypotheses


def _build_recommendations(models: list[dict], brand: dict) -> str:
    """Build conclusions section from data patterns."""
    lines = ["## Выводы и рекомендации"]
    rec_num = 0

    # Find biggest CRO drops
    cro_drops = []
    for m in models:
        changes = m["funnel_totals"]["changes"]
        curr = m["funnel_totals"]["current"]
        prev = m["funnel_totals"]["previous"]
        c_opens = curr.get("переходы", 0)
        p_opens = prev.get("переходы", 0)
        c_orders = curr.get("заказы", 0)
        p_orders = prev.get("заказы", 0)
        cro_c = _calc_cr(c_orders, c_opens)
        cro_p = _calc_cr(p_orders, p_opens)
        delta = cro_c - cro_p
        if delta < -0.3 and c_opens > 5000:
            cro_drops.append((m["model"], cro_c, cro_p, delta, c_opens, c_orders, p_orders))

    if cro_drops:
        cro_drops.sort(key=lambda x: x[3])
        top = cro_drops[0]
        model_name, cro_c, cro_p, delta, opens, orders_c, orders_p = top
        lost_orders = orders_p - orders_c
        rec_num += 1
        avg_check = brand.get("выручка", 0) / max(brand.get("заказы", 1), 1)
        lost_revenue = lost_orders * avg_check

        lines.append(f"### {rec_num}. Восстановить CRO модели {model_name.title()} (упал с {cro_p:.2f}% до {cro_c:.2f}%)")
        lines.append(f"**ФАКТ:** CRO {model_name.title()} упал на {abs(delta):.2f}pp, что привело к потере ~{lost_orders} заказов в неделю при динамике переходов.")
        lines.append(f"**ГИПОТЕЗА:** Возможно, привлечён нецелевой трафик по новым ключевым словам, изменились позиции по нерелевантным запросам, или проблемы с контентом карточек (фото, описания, размерная сетка).")
        target_cro = cro_p * 0.9  # realistic target
        extra_orders = int(opens * (target_cro - cro_c) / 100)
        lines.append(f"**ДЕЙСТВИЕ:** Проверить ключевые слова на релевантность. Аудит карточек с падающим CRO. Проверить наличие размеров у проблемных артикулов. Проверить отзывы на негатив.")
        lines.append(f"**ЭФФЕКТ:** Если довести CRO с {cro_c:.2f}% до {target_cro:.2f}%: +{extra_orders} заказов/нед × {avg_check:,.0f} ₽ ≈ +{extra_orders * avg_check:,.0f} ₽ выручки")
        lines.append("")

    # Find biggest traffic drops
    traffic_drops = []
    for m in models:
        changes = m["funnel_totals"]["changes"]
        delta = changes.get("переходы_delta_pct", 0)
        curr_opens = m["funnel_totals"]["current"].get("переходы", 0)
        prev_opens = m["funnel_totals"]["previous"].get("переходы", 0)
        if delta < -10 and prev_opens > 5000:
            lost = prev_opens - curr_opens
            traffic_drops.append((m["model"], delta, lost, curr_opens, prev_opens))

    if traffic_drops:
        traffic_drops.sort(key=lambda x: x[2], reverse=True)
        top = traffic_drops[0]
        model_name, delta, lost, curr, prev = top
        rec_num += 1
        lines.append(f"### {rec_num}. Восстановить трафик {model_name.title()} ({_fmt_delta_pct(delta)} переходов WoW)")
        lines.append(f"**ФАКТ:** {model_name.title()} потеряла {_fmt_num(lost)} переходов (с {_fmt_num(prev)} до {_fmt_num(curr)}).")
        lines.append(f"**ГИПОТЕЗА:** Снижение позиций в поиске по ключевым словам, сезонный спад, или снижение рекламной активности.")
        lines.append(f"**ДЕЙСТВИЕ:** Проверить позиции по топ-ключевым словам. Обновить заголовки и описания карточек. Рассмотреть увеличение рекламы на артикулы с высоким CR.")
        lines.append(f"**ЭФФЕКТ:** Восстановление трафика до уровня прошлой недели (+{_fmt_num(lost)} переходов)")
        lines.append("")

    # Find growth opportunities
    growers = []
    for m in models:
        sig = m.get("significant_articles", [])
        for a in sig:
            flags = a.get("flags", [])
            has_big_growth = any("+" in f and float(f.split("+")[1].split("%")[0]) > 50 for f in flags if "+" in f)
            if has_big_growth and a.get("заказы", 0) > 20:
                growers.append((m["model"], a))

    if growers:
        rec_num += 1
        lines.append(f"### {rec_num}. Масштабировать успешные артикулы с ростом")
        fact_parts = []
        for model_name, a in growers[:4]:
            fact_parts.append(f"{a['artikul']} ({', '.join(a['flags'])})")
        lines.append(f"**ФАКТ:** Артикулы с ростом: {'; '.join(fact_parts)}.")
        lines.append(f"**ГИПОТЕЗА:** Эти артикулы попали в ТОП по высокочастотным запросам или получили вирусный эффект.")
        lines.append(f"**ДЕЙСТВИЕ:** Проверить ключевые слова, по которым эти артикулы находятся. Рассмотреть запуск/усиление рекламы.")
        lines.append(f"**ЭФФЕКТ:** Увеличение переходов на 20% через рекламу → дополнительные заказы и выручка.")
        lines.append("")

    # Find problem articles
    problem_articles = []
    for m in models:
        sig = m.get("significant_articles", [])
        for a in sig:
            flags = a.get("flags", [])
            has_big_decline = any("-" in f and abs(float(f.split("-")[1].split("%")[0])) > 40 for f in flags if "-" in f and "%" in f)
            if has_big_decline:
                problem_articles.append((m["model"], a))

    if problem_articles and rec_num < 4:
        rec_num += 1
        lines.append(f"### {rec_num}. Работа с проблемными артикулами")
        fact_parts = []
        for model_name, a in problem_articles[:5]:
            fact_parts.append(f"{a['artikul']} ({', '.join(a['flags'])})")
        lines.append(f"**ФАКТ:** {'; '.join(fact_parts)}.")
        lines.append(f"**ГИПОТЕЗА:** Проблемы с контентом, нехватка размеров, негативные отзывы, или проблемы с поставками (нет в наличии на FBO).")
        lines.append(f"**ДЕЙСТВИЕ:** Проверить наличие на складах по проблемным артикулам. Полный аудит контента: фото, видео, описание, отзывы. Отключить рекламу на артикулы без остатков.")
        lines.append(f"**ЭФФЕКТ:** Снижение потерь, восстановление заказов по проблемным артикулам.")
        lines.append("")

    if rec_num == 0:
        lines.append("Значимых отклонений не обнаружено. Показатели стабильны.")

    return "\n".join(lines)


def _safe_pct(curr, prev):
    if prev and prev > 0:
        return round((curr - prev) / prev * 100, 1)
    return 0


def build_funnel_report(bundle: dict, start_date: str, end_date: str) -> dict:
    """Build the complete funnel report from data bundle.

    Returns dict with telegram_summary, brief_summary, detailed_report.
    """
    models = bundle.get("models", [])
    brand = bundle.get("brand_totals", {})

    if not models:
        return {
            "telegram_summary": f"📊 Воронка WB {start_date} — {end_date}\nНет данных за период.",
            "brief_summary": "Нет данных за период.",
            "detailed_report": "# Воронка WB\nНет данных за период.",
        }

    # --- Brand totals ---
    brand_changes = brand.get("changes", {})
    total_orders = brand.get("заказы", 0)
    total_opens = brand.get("переходы", 0)
    total_buyouts = brand.get("выкупы", 0)
    total_revenue = brand.get("выручка", 0)
    total_margin = brand.get("маржа", 0)
    total_drr = brand.get("дрр_pct", 0)

    # Previous period totals (calculate from model data)
    prev_opens = sum(m["funnel_totals"]["previous"].get("переходы", 0) for m in models)
    prev_orders = sum(m["funnel_totals"]["previous"].get("заказы", 0) for m in models)
    prev_buyouts = sum(m["funnel_totals"]["previous"].get("выкупы", 0) for m in models)

    # --- DETAILED REPORT ---
    report_lines = []
    report_lines.append(f"# Воронка WB за {start_date} — {end_date}")

    # Brand overview
    report_lines.append("## ОБЩИЙ ОБЗОР БРЕНДА")
    report_lines.append("| Метрика | Текущая неделя | Предыдущая неделя | Изменение |")
    report_lines.append("|---------|---------------|-------------------|-----------|")
    report_lines.append(f"| Переходы | {_fmt_num(total_opens)} | {_fmt_num(prev_opens)} | {_fmt_delta_pct(brand_changes.get('переходы_delta_pct', 0))} |")
    report_lines.append(f"| Заказы | {_fmt_num(total_orders)} | {_fmt_num(prev_orders)} | {_fmt_delta_pct(brand_changes.get('заказы_delta_pct', 0))} |")
    report_lines.append(f"| Выкупы* | {_fmt_num(total_buyouts)} | {_fmt_num(prev_buyouts)} | {_fmt_delta_pct(brand_changes.get('выкупы_delta_pct', 0))} |")
    report_lines.append(f"| Выручка | {_fmt_num(total_revenue)} ₽ | — | — |")
    report_lines.append(f"| Маржа | {_fmt_num(total_margin)} ₽ | — | — |")
    report_lines.append(f"| ДРР | {_fmt_pct(total_drr)} | — | — |")
    report_lines.append("")
    report_lines.append("\\* *Выкупы имеют временной лаг 3-21 день, данные неполные*")
    report_lines.append("---")

    # Per-model sections
    for m in models:
        report_lines.append(_build_model_section(m))

    # Recommendations
    report_lines.append("")
    report_lines.append(_build_recommendations(models, brand))

    detailed_report = "\n".join(report_lines)

    # --- TELEGRAM SUMMARY ---
    orders_delta = brand_changes.get("заказы_delta_pct", 0)
    opens_delta = brand_changes.get("переходы_delta_pct", 0)
    tg_lines = [
        f"📊 Воронка WB {start_date} — {end_date}",
        f"Переходы: {_fmt_num(total_opens)} (WoW {_fmt_delta_pct(opens_delta)})",
        f"Заказы: {_fmt_num(total_orders)} (WoW {_fmt_delta_pct(orders_delta)})",
        f"Выкупы*: {_fmt_num(total_buyouts)}",
        f"Выручка: {_fmt_num(total_revenue)} ₽ | Маржа: {_fmt_num(total_margin)} ₽",
        f"ДРР: {_fmt_pct(total_drr)}",
    ]

    # Find top alert
    worst_model = None
    worst_delta = 0
    for m in models:
        d = m["funnel_totals"]["changes"].get("заказы_delta_pct", 0)
        if d < worst_delta and m["funnel_totals"]["current"].get("заказы", 0) > 50:
            worst_delta = d
            worst_model = m["model"]

    if worst_model and worst_delta < -10:
        tg_lines.append(f"⚠️ {worst_model.capitalize()}: заказы {_fmt_delta_pct(worst_delta)}")

    tg_lines.append("*выкупы с лагом 3-21 день")
    telegram_summary = "\n".join(tg_lines)

    # --- BRIEF SUMMARY ---
    brief_lines = [
        f"📊 Воронка WB: {start_date} — {end_date}",
        f"Переходы: {_fmt_num(total_opens)} (WoW {_fmt_delta_pct(opens_delta)})",
        f"Заказы: {_fmt_num(total_orders)} (WoW {_fmt_delta_pct(orders_delta)})",
        f"Выкупы*: {_fmt_num(total_buyouts)}",
        f"Выручка: {_fmt_num(total_revenue)} ₽ | Маржа: {_fmt_num(total_margin)} ₽ | ДРР: {_fmt_pct(total_drr)}",
        "",
        "По моделям:",
    ]
    for m in models[:5]:
        name = m["model"].capitalize()
        rev = m["economics"]["выручка"]
        od = m["funnel_totals"]["changes"].get("заказы_delta_pct", 0)
        brief_lines.append(f"  {name}: выручка {_fmt_num(rev)} ₽, заказы {_fmt_delta_pct(od)}")

    if len(models) > 5:
        brief_lines.append(f"  ... и ещё {len(models) - 5} моделей")

    brief_lines.append("")
    brief_lines.append("*выкупы с лагом 3-21 день")
    brief_summary = "\n".join(brief_lines)

    return {
        "telegram_summary": telegram_summary,
        "brief_summary": brief_summary,
        "detailed_report": detailed_report,
    }
