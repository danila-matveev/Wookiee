"""Централизованные шаблоны сообщений для Telegram (русский язык).

Единый источник всех user-facing текстов. Все функции возвращают
готовые строки — вызывающий код передаёт их в _send_admin() / telegram_send().
"""
from __future__ import annotations


def data_ready(date: str, reports: list[str]) -> str:
    """Короткое уведомление о старте генерации."""
    reports_str = ", ".join(reports)
    return f"Данные готовы за {date}, запускаю: {reports_str}"


def report_error(
    date: str, report_type: str, error: str, attempt: int, max_attempts: int,
) -> str:
    """Ошибка генерации отчёта (при retry)."""
    return (
        f"Ошибка отчёта «{report_type}» за {date} "
        f"(попытка {attempt}/{max_attempts}):\n{str(error)[:200]}"
    )


def report_retries_exhausted(date: str, report_type: str) -> str:
    """Все попытки генерации исчерпаны."""
    return (
        f"Не удалось сгенерировать «{report_type}» за {date} "
        f"после всех попыток. Требуется ручной запуск."
    )


def report_exception(
    report_type: str, date_from: str, date_to: str, exc: Exception,
) -> str:
    """Исключение при генерации отчёта (exception handler)."""
    period = date_from if date_from == date_to else f"{date_from}–{date_to}"
    if not period:
        return f"Ошибка «{report_type}»:\n{str(exc)[:300]}"
    return f"Ошибка отчёта «{report_type}» за {period}:\n{str(exc)[:300]}"


def watchdog_alert(status: str, failed: list[str], passed: list[str]) -> str:
    """Результат проверки системы (watchdog heartbeat)."""
    check_names = {
        "llm": "LLM API (OpenRouter)",
        "db": "База данных WB",
        "last_run": "Последний запуск оркестратора",
    }
    level = "КРИТИЧНО" if status == "critical" else "ПРЕДУПРЕЖДЕНИЕ"
    lines = [f"Проверка системы — {level}"]
    for name in failed:
        lines.append(f"  ✗ {check_names.get(name, name)}")
    for name in passed:
        lines.append(f"  ✓ {check_names.get(name, name)}")
    return "\n".join(lines)


def anomaly_alert(
    metric: str, channel: str, value: float, avg: float, pct_change: float,
) -> str:
    """Обнаружена аномалия в метрике."""
    direction = "↓" if pct_change < 0 else "↑"
    return (
        f"Аномалия: {channel} {metric}\n"
        f"Значение: {value:,.0f} vs среднее {avg:,.0f} "
        f"({direction}{abs(pct_change):.1f}%)"
    )


def watchdog_repeated_failures(report_type: str, count: int) -> str:
    """Повторные сбои одного типа отчёта."""
    return (
        f"Повторные сбои отчёта «{report_type}»\n"
        f"Подряд неудач: {count}\n"
        "Требуется ручная проверка."
    )


def anomaly_report(artifact: dict) -> str:
    """Форматирование результата anomaly-detector агента для Telegram."""
    summary = artifact.get("summary", {})
    critical = summary.get("critical_count", 0)
    warning = summary.get("warning_count", 0)
    info = summary.get("info_count", 0)
    top = summary.get("top_priority_anomaly", "")
    summary_text = artifact.get("summary_text", "")

    lines = [
        "Обнаружены аномалии",
        f"Критических: {critical} | Предупреждений: {warning} | Инфо: {info}",
    ]
    if top:
        lines.append(f"Приоритет: {top}")
    if summary_text:
        lines.append("")
        lines.append(summary_text)

    anomalies = artifact.get("anomalies", [])
    critical_anomalies = [a for a in anomalies if a.get("severity") == "critical"]
    if critical_anomalies:
        lines.append("")
        lines.append("Критические аномалии:")
        for a in critical_anomalies[:3]:
            metric = a.get("metric", "")
            dev = a.get("deviation_pct", 0)
            channel = a.get("channel", "")
            lines.append(f"  • {metric} ({channel}): {dev:+.1f}%")

    return "\n".join(lines)
