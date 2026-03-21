"""Telegram message formatters for conductor notifications."""
from agents.v3.conductor.schedule import ReportType


def format_data_ready(
    wb_info: dict,
    ozon_info: dict,
    pending: list,
    report_date: str,
) -> str:
    """Format 'data ready' notification."""
    def _channel_line(name, info):
        rev_pct = int(info["revenue_ratio"] * 100)
        warn = " ⚠️" if rev_pct < 75 else ""
        return (
            f"{name}: обновлено в {info['updated_at']} МСК | "
            f"Заказы: {info['orders']} | Выручка: {rev_pct}% от нормы{warn}"
        )

    report_names = ", ".join(r.human_name for r in pending)

    return (
        f"✅ Данные за {report_date} готовы\n\n"
        f"{_channel_line('WB', wb_info)}\n"
        f"{_channel_line('OZON', ozon_info)}\n\n"
        f"📊 Запускаю отчёты: {report_names}"
    )


def format_alert(
    report_type: ReportType,
    reason: str,
    attempt: int,
    max_attempts: int = 3,
    diagnostics: str = None,
    action: str = None,
) -> str:
    """Format error alert notification."""
    lines = [
        "⚠️ Проблема с формированием отчётов\n",
        f"Статус: {report_type.human_name} — ❌ не сформирован ({attempt}/{max_attempts} попытки)",
        f"Причина: {reason}",
    ]
    if diagnostics:
        lines.append(f"Диагностика: {diagnostics}")
    if action:
        lines.append(f"\nДействие: {action}")

    return "\n".join(lines)
