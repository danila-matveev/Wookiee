"""Детерминистический MD-форматировщик для Notion-отчёта по логистическим расходам."""
from __future__ import annotations

from datetime import datetime, timedelta

_CABINET_LABELS = {"ip": "ИП", "ooo": "ООО", "ип": "ИП", "ооо": "ООО"}


def _cab(name: str) -> str:
    return _CABINET_LABELS.get(name.lower(), name)


def _fmt_rub(value: float) -> str:
    """Format ruble amount: 45200 → '45 200'."""
    return f"{value:,.0f}".replace(",", " ")


def _sign(value: float) -> str:
    return f"+{value}" if value > 0 else str(value)


def format_localization_weekly_md(results: list[dict], period_days: int) -> str:
    """Render weekly localization report as Markdown for Notion."""
    now = datetime.now()
    idx_from = (now - timedelta(days=period_days)).strftime("%d.%m")
    idx_to = now.strftime("%d.%m.%Y")
    week_from = (now - timedelta(days=7)).strftime("%d.%m")
    week_to = (now - timedelta(days=1)).strftime("%d.%m")

    lines: list[str] = []
    lines.append("# Анализ логистических расходов WB")
    lines.append("")
    lines.append(f"> Период индексов: {period_days} дн ({idx_from} — {idx_to}). Динамика: неделя {week_from} — {week_to}.")
    lines.append("")

    # --- Сводка ---
    lines.append("## Сводка по кабинетам")
    lines.append("")
    lines.append("| Кабинет | ИЛ | ИРП | Индекс лок. | SKU в ИРП-зоне | Переплата ₽/мес |")
    lines.append("|---------|-----|------|------------|----------------|-----------------|")
    for r in results:
        s = r.get("summary", {})
        cab = _cab(r.get("cabinet", ""))
        lines.append(
            f"| {cab} | {s.get('il_current', 1.0):.2f} | {s.get('irp_current', 0.0):.2f}% "
            f"| {s.get('overall_index', 0):.1f}% | {s.get('irp_zone_sku', 0)} "
            f"| {_fmt_rub(s.get('irp_impact_rub_month', 0))} |"
        )
    lines.append("")

    # --- Динамика ---
    lines.append("## Динамика за неделю")
    lines.append("")
    for r in results:
        cab = _cab(r.get("cabinet", ""))
        comp = r.get("comparison")
        lines.append(f"### {cab}")
        if not comp:
            lines.append("_Нет данных за предыдущую неделю._")
            lines.append("")
            continue
        s = r.get("summary", {})
        lines.append(f"- Индекс локализации: {comp.get('prev_index', 0):.1f}% → {s.get('overall_index', 0):.1f}% ({_sign(comp.get('index_change', 0))} п.п.)")
        lines.append(f"- ИЛ: {comp.get('prev_il_current', 1.0):.2f} → {s.get('il_current', 1.0):.2f} ({_sign(comp.get('il_current_change', 0))})")
        lines.append(f"- ИРП: {comp.get('prev_irp_current', 0):.2f}% → {s.get('irp_current', 0):.2f}% ({_sign(comp.get('irp_current_change', 0))} п.п.)")

        impact_change = comp.get("irp_impact_change", 0)
        label = "экономия" if impact_change < 0 else "рост"
        lines.append(
            f"- Переплата: {_fmt_rub(comp.get('prev_irp_impact', 0))} → "
            f"{_fmt_rub(s.get('irp_impact_rub_month', 0))} ₽/мес "
            f"({label} {_fmt_rub(abs(impact_change))} ₽/мес)"
        )

        zone_change = comp.get("irp_zone_sku_change", 0)
        lines.append(f"- SKU в ИРП-зоне: {comp.get('prev_irp_zone_sku', 0)} → {s.get('irp_zone_sku', 0)} ({_sign(zone_change)})")

        improved = comp.get("regions_improved", [])
        worsened = comp.get("regions_worsened", [])
        lines.append(f"- Улучшенные регионы: {', '.join(improved) if improved else '—'}")
        lines.append(f"- Ухудшенные регионы: {', '.join(worsened) if worsened else '—'}")
        lines.append("")

    # --- Зоны ---
    lines.append("## Зональная разбивка")
    lines.append("")
    header = "| Зона | Описание |"
    sep = "|------|----------|"
    for r in results:
        header += f" SKU {_cab(r.get('cabinet', ''))} |"
        sep += "------|"
    header += " Доля заказов |"
    sep += "-------------|"
    lines.append(header)
    lines.append(sep)

    # Compute order shares per zone across all cabinets
    total_orders_all = sum(r.get("summary", {}).get("sku_with_orders", 0) for r in results)

    zones = [
        ("ИРП-зона", "<60%, КРП > 0", "irp_zone_sku"),
        ("ИЛ-зона", "60-74%, КТР > 1", "il_zone_sku"),
    ]
    for zone_name, desc, key in zones:
        row = f"| {zone_name} | {desc} |"
        zone_total = 0
        for r in results:
            count = r.get("summary", {}).get(key, 0)
            row += f" {count} |"
            zone_total += count
        share = round(zone_total / max(total_orders_all, 1) * 100, 0)
        row += f" {share:.0f}% |"
        lines.append(row)

    ok_row = "| OK | ≥75% |"
    ok_total = 0
    for r in results:
        s = r.get("summary", {})
        ok_count = s.get("sku_with_orders", 0) - s.get("irp_zone_sku", 0) - s.get("il_zone_sku", 0)
        ok_count = max(ok_count, 0)
        ok_row += f" {ok_count} |"
        ok_total += ok_count
    ok_share = round(ok_total / max(total_orders_all, 1) * 100, 0)
    ok_row += f" {ok_share:.0f}% |"
    lines.append(ok_row)
    lines.append("")

    # --- Топ моделей ---
    lines.append("## Топ моделей по переплате")
    lines.append("")
    lines.append("| # | Модель | Кабинет | Лок% | КТР | КРП% | Заказов/мес | Логистика ₽/мес | Переплата ₽/мес | Экономия при оптимизации |")
    lines.append("|---|--------|---------|------|-----|------|-------------|-----------------|-----------------|--------------------------|")
    rank = 1
    all_problems = []
    for r in results:
        cab = _cab(r.get("cabinet", ""))
        # Support both key conventions (_avg_base_logistics from scheduler, avg_base_logistics from manual)
        avg_base = r.get("avg_base_logistics", 0) or r.get("_avg_base_logistics", 0)
        for p in r.get("top_problems", []):
            p_copy = dict(p)
            p_copy["_avg_base"] = avg_base
            all_problems.append((p_copy, cab))
    all_problems.sort(key=lambda x: x[0].get("irp_rub_month", x[0].get("impact", 0)), reverse=True)
    for p, cab in all_problems[:15]:
        ktr = p.get("ktr", 1.0)
        orders = p.get("orders", 0)
        avg_base = p.get("_avg_base", 0)
        logistics = round(ktr * avg_base * orders)
        irp_rub = p.get("irp_rub_month", p.get("impact", 0))
        zone = p.get("zone", "")
        if zone == "ИРП-зона":
            savings_hint = f"{_fmt_rub(irp_rub)} (при 60%: КРП→0)"
        elif zone == "ИЛ-зона":
            savings_hint = f"{_fmt_rub(round((ktr - 0.9) * avg_base * orders))} (при 75%: КТР→0.9)"
        else:
            savings_hint = "—"
        lines.append(
            f"| {rank} | {p.get('article', '')} | {cab} | {p.get('index', 0):.0f}% "
            f"| {ktr:.2f} | {p.get('krp_pct', 0):.2f}% "
            f"| {orders} | {_fmt_rub(logistics)} | {_fmt_rub(irp_rub)} | {savings_hint} |"
        )
        rank += 1
    lines.append("")

    # --- Регионы ---
    lines.append("## Регионы")
    lines.append("")
    header = "| Регион |"
    sep = "|--------|"
    for r in results:
        cab = _cab(r.get("cabinet", ""))
        header += f" Лок% {cab} |"
        sep += "----------|"
    header += " Доля заказов | Рекомендация |"
    sep += "-------------|-------------|"
    lines.append(header)
    lines.append(sep)

    all_regions: dict[str, dict] = {}
    for r in results:
        cab = _cab(r.get("cabinet", ""))
        for reg in r.get("regions", []):
            name = reg.get("region", "")
            if name not in all_regions:
                all_regions[name] = {"recommendation": reg.get("recommendation", ""), "order_shares": []}
            all_regions[name][cab] = reg.get("index", 0)
            all_regions[name]["order_shares"].append(reg.get("order_share", 0))

    for name, data in sorted(all_regions.items(), key=lambda x: min(v for k, v in x[1].items() if isinstance(v, (int, float)) and k not in ("order_shares",)), reverse=False):
        row = f"| {name} |"
        for r in results:
            cab = _cab(r.get("cabinet", ""))
            val = data.get(cab, "—")
            row += f" {val:.1f}% |" if isinstance(val, (int, float)) else f" {val} |"
        avg_share = sum(data.get("order_shares", [])) / max(len(data.get("order_shares", [])), 1)
        row += f" {avg_share:.1f}% | {data.get('recommendation', '')} |"
        lines.append(row)
    lines.append("")

    # --- Рекомендации ---
    lines.append("## Рекомендации")
    lines.append("")
    for r in results:
        cab = _cab(r.get("cabinet", ""))
        s = r.get("summary", {})
        if s.get("irp_zone_sku", 0) > 0:
            lines.append(f"- **{cab}**: {s['irp_zone_sku']} артикулов в ИРП-зоне — переплата {_fmt_rub(s.get('irp_impact_rub_month', 0))} ₽/мес. Приоритет перестановок.")
        if s.get("il_zone_sku", 0) > 0:
            lines.append(f"- **{cab}**: {s['il_zone_sku']} артикулов в ИЛ-зоне (60-74%) — наценка на логистику через КТР.")

    total_impact = sum(r.get("summary", {}).get("irp_impact_rub_month", 0) for r in results)
    if total_impact > 0:
        lines.append(f"- Общая ИРП-переплата по всем кабинетам: **{_fmt_rub(total_impact)} ₽/мес**")

    return "\n".join(lines)


def format_localization_tg_summary(results: list[dict]) -> str:
    """Short BBCode summary for Telegram (3-5 lines)."""
    now = datetime.now()
    week_from = (now - timedelta(days=7)).strftime("%d.%m")
    week_to = (now - timedelta(days=1)).strftime("%d.%m")

    lines = [f"<b>Логистические расходы WB</b> (неделя {week_from}—{week_to})"]
    for r in results:
        cab = _cab(r.get("cabinet", ""))
        s = r.get("summary", {})
        impact_k = s.get("irp_impact_rub_month", 0) / 1000
        lines.append(
            f"{cab}: ИЛ {s.get('il_current', 1.0):.2f} / ИРП {s.get('irp_current', 0):.2f}% "
            f"/ переплата {impact_k:.1f}K₽"
        )
    total_change = sum(
        (r.get("comparison") or {}).get("irp_impact_change", 0) for r in results
    )
    if total_change != 0:
        label = "экономия" if total_change < 0 else "рост"
        lines.append(f"Динамика: {label} {abs(total_change)/1000:.1f}K₽ vs прошлая неделя")

    return "\n".join(lines)
