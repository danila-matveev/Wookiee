"""Централизованные шаблоны сообщений для Telegram (русский язык).

Единый источник всех user-facing текстов. Все функции возвращают
готовые строки — вызывающий код передаёт их в _send_admin() / telegram_send().

Правило: все сообщения пишутся человеческим языком, понятным владельцу
бизнеса, а НЕ разработчику. Никакого технического жаргона.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Генерация отчётов
# ---------------------------------------------------------------------------

def data_ready(date: str, reports: list[str]) -> str:
    """Данные загружены, запускаем генерацию."""
    reports_str = ", ".join(reports)
    return (
        f"✅ Данные за {date} готовы, запускаю: {reports_str}"
    )


def channel_data_ready(
    date: str,
    marketplace: str,
    gate_info: dict,
    report_time: str | None = None,
) -> str:
    """Per-channel data readiness notification with details.

    gate_info keys: updated_at, orders, orders_normal, revenue_ratio, margin_pct.
    """
    mp = marketplace.upper()
    lines = [f"✅ Данные за {date} готовы ({mp})"]
    lines.append("")

    if gate_info.get("updated_at") and gate_info["updated_at"] != "—":
        lines.append(f"Обновлено в {gate_info['updated_at']} МСК")

    orders = gate_info.get("orders", 0)
    orders_normal = gate_info.get("orders_normal", True)
    if orders_normal:
        lines.append(f"Заказов: {orders} (норма)")
    else:
        lines.append(f"⚠️ Заказов: {orders} (ниже нормы)")

    rev = gate_info.get("revenue_ratio")
    if rev is not None:
        lines.append(f"Выручка: {rev:.0f}% от нормы")

    margin = gate_info.get("margin_pct")
    if margin is not None:
        lines.append(f"Маржа: у {margin:.0f}% артикулов")

    if report_time:
        lines.append("")
        lines.append(f"📊 Ежедневный отчёт запланирован на {report_time} МСК")

    return "\n".join(lines)


def data_ready_combined(
    date: str,
    channels: list[dict],
    reports: list[str],
) -> str:
    """Combined data-ready notification: all channels + report list in one message.

    Each channel dict has: marketplace, gate_info (with keys: updated_at, orders,
    orders_normal, revenue_ratio, margin_pct).
    """
    lines = [f"✅ Данные за {date} готовы"]
    lines.append("")

    for ch in channels:
        mp = ch["marketplace"].upper()
        gi = ch["gate_info"]
        parts = [f"  {mp}:"]

        orders = gi.get("orders", 0)
        if gi.get("orders_normal", True):
            parts.append(f"заказов {orders}")
        else:
            parts.append(f"⚠️ заказов {orders} (ниже нормы)")

        rev = gi.get("revenue_ratio")
        if rev is not None:
            parts.append(f"выручка {rev:.0f}%")

        margin = gi.get("margin_pct")
        if margin is not None:
            parts.append(f"маржа {margin:.0f}%")

        lines.append(" | ".join(parts))

    if reports:
        lines.append("")
        reports_str = ", ".join(reports)
        lines.append(f"📊 Запускаю: {reports_str}")

    return "\n".join(lines)


def report_error(
    date: str, report_type: str, error: str, attempt: int, max_attempts: int,
) -> str:
    """Ошибка генерации отчёта (при retry)."""
    reason = _humanize_error(error)
    if attempt >= max_attempts:
        return (
            f"❌ Не удалось сформировать «{report_type}» за {date}\n\n"
            f"Причина: {reason}\n"
            f"Попытки: {attempt}/{max_attempts} — все исчерпаны.\n\n"
            "Отчёт можно запустить вручную командой в боте."
        )
    return (
        f"⏳ Отчёт «{report_type}» за {date} — попытка {attempt}/{max_attempts} не удалась.\n"
        f"Причина: {reason}\n"
        f"Следующая попытка автоматически."
    )


def report_retries_exhausted(date: str, report_type: str) -> str:
    """Все попытки генерации исчерпаны."""
    return (
        f"❌ Не удалось сформировать «{report_type}» за {date} "
        f"после всех попыток.\n\n"
        "Отчёт можно запустить вручную командой в боте."
    )


def report_exception(
    report_type: str, date_from: str, date_to: str, exc: Exception,
) -> str:
    """Исключение при генерации отчёта (exception handler)."""
    period = date_from if date_from == date_to else f"{date_from}–{date_to}"
    reason = _humanize_exception(exc)
    if not period:
        return f"❌ Ошибка «{report_type}»:\n{reason}"
    return f"❌ Ошибка отчёта «{report_type}» за {period}:\n{reason}"


# ---------------------------------------------------------------------------
# Watchdog (проверка системы)
# ---------------------------------------------------------------------------

def watchdog_alert(status: str, failed: list[str], passed: list[str]) -> str:
    """Результат проверки системы (watchdog heartbeat).

    Пишем понятным языком — что сломалось и что делать.
    """
    check_descriptions = {
        "llm": ("Нейросеть (OpenRouter)", "Сервис генерации отчётов недоступен. Отчёты не будут формироваться до восстановления."),
        "db": ("База данных аналитики", "Сервер данных WB/OZON не отвечает. Это внешний сервер — обычно восстанавливается сам."),
        "last_run": ("Последний запуск", "Предыдущая генерация отчёта завершилась с ошибкой."),
    }

    lines = []
    if status == "critical":
        lines.append("🔴 Система недоступна")
        lines.append("")
        lines.append("Все компоненты не работают. Отчёты не формируются.")
    else:
        lines.append("🟡 Проблемы в системе")

    lines.append("")
    for name in failed:
        desc = check_descriptions.get(name)
        if desc:
            lines.append(f"✗ {desc[0]}")
            lines.append(f"  → {desc[1]}")
        else:
            lines.append(f"✗ {name}")
    if passed:
        lines.append("")
        for name in passed:
            desc = check_descriptions.get(name)
            label = desc[0] if desc else name
            lines.append(f"✓ {label}")

    return "\n".join(lines)


def watchdog_repeated_failures(report_type: str, count: int) -> str:
    """Повторные сбои одного типа отчёта."""
    return (
        f"⚠️ Отчёт «{report_type}» не формируется уже {count} раз подряд.\n\n"
        "Возможные причины: проблемы с данными или сервисом нейросети.\n"
        "Отчёт можно запустить вручную командой в боте."
    )


# ---------------------------------------------------------------------------
# Дедлайн и качество данных
# ---------------------------------------------------------------------------

def deadline_missed(missing_names: str, diagnostics: str) -> str:
    """Отчёты не сформированы к дедлайну."""
    return (
        f"⚠️ К 12:00 не все отчёты готовы\n\n"
        f"Не готовы: {missing_names}\n"
        f"Причина: {diagnostics}\n\n"
        "Система проверит повторно в 15:00."
    )


def data_quality_issue(date: str) -> str:
    """Обнаружены проблемы качества данных."""
    return (
        f"⚠️ Обнаружены проблемы с качеством данных за {date}.\n"
        "Это может повлиять на точность отчётов."
    )


# ---------------------------------------------------------------------------
# Аномалии
# ---------------------------------------------------------------------------

def anomaly_alert(
    metric: str, channel: str, value: float, avg: float, pct_change: float,
) -> str:
    """Обнаружена аномалия в метрике."""
    direction = "снижение" if pct_change < 0 else "рост"
    return (
        f"📊 Аномалия: {channel} — {metric}\n"
        f"Значение: {value:,.0f} (среднее {avg:,.0f}, {direction} {abs(pct_change):.1f}%)"
    )


def anomaly_report(artifact: dict) -> str:
    """Форматирование результата anomaly-detector агента для Telegram.

    Выводим краткую сводку на русском, без технического жаргона.
    """
    summary = artifact.get("summary", {})
    critical = summary.get("critical_count", 0)
    warning = summary.get("warning_count", 0)

    lines = ["📊 Мониторинг аномалий"]
    lines.append("")

    if critical > 0:
        lines.append(f"🔴 Критических отклонений: {critical}")
    if warning > 0:
        lines.append(f"🟡 Предупреждений: {warning}")

    # Показываем до 3 самых важных аномалий в читаемом формате
    anomalies = artifact.get("anomalies", [])
    critical_anomalies = [a for a in anomalies if a.get("severity") == "critical"]
    warning_anomalies = [a for a in anomalies if a.get("severity") == "warning"]

    top_anomalies = (critical_anomalies + warning_anomalies)[:3]
    if top_anomalies:
        lines.append("")
        for a in top_anomalies:
            metric = _humanize_metric(a.get("metric", ""))
            channel = a.get("channel", "")
            dev = a.get("deviation_pct", 0)
            direction = "снижение" if dev < 0 else "рост"
            severity_icon = "🔴" if a.get("severity") == "critical" else "🟡"
            lines.append(f"{severity_icon} {metric} ({channel}): {direction} {abs(dev):.0f}%")

    # Краткий вывод — берём summary_text, но ограничиваем и переводим если нужно
    summary_text = artifact.get("summary_text", "")
    if summary_text:
        # Ограничиваем 300 символами
        if len(summary_text) > 300:
            summary_text = summary_text[:297] + "..."
        lines.append("")
        lines.append(summary_text)

    # Рекомендация
    dq = artifact.get("data_quality_status", {})
    if dq.get("ok") is False:
        lines.append("")
        lines.append("ℹ️ Возможно, это проблема данных, а не реальное изменение.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers — перевод технических ошибок в человеческий язык
# ---------------------------------------------------------------------------

_ERROR_MAP = {
    "Подробный отчёт пуст (detailed_report)": (
        "Агенты анализа не смогли собрать достаточно данных для отчёта."
    ),
    "Telegram-саммари пуст (telegram_summary)": (
        "Агенты подготовили данные, но не смогли сформировать краткую сводку."
    ),
    "Статус отчёта: failed или report=None": (
        "Все агенты анализа завершились с ошибкой — данные не получены."
    ),
}


def _humanize_error(error: str) -> str:
    """Перевод технической ошибки в читаемое объяснение."""
    # Точное совпадение
    if error in _ERROR_MAP:
        return _ERROR_MAP[error]

    # Паттерны
    lower = error.lower()
    if "timed out" in lower or "timeout" in lower:
        return "Агенты анализа не успели обработать данные за отведённое время."
    if "nonetype" in lower:
        return "Один из компонентов вернул пустой результат. Возможно, проблема с источником данных."
    if "connection" in lower or "connect" in lower:
        return "Не удалось подключиться к серверу данных."
    if "слишком короткий" in lower:
        return "Агенты вернули слишком мало данных для полноценного отчёта."
    if "фраза ошибки" in lower:
        return "Агенты сообщили об ошибке при анализе данных."

    # Если ничего не подошло — обрезаем и показываем как есть
    return error[:200] if len(error) > 200 else error


def _humanize_exception(exc: Exception) -> str:
    """Перевод Python exception в читаемый текст."""
    msg = str(exc)
    lower = msg.lower()

    if "nonetype" in lower and "attribute" in lower:
        return "Один из компонентов вернул пустой результат вместо данных."
    if "timeout" in lower or "timed out" in lower:
        return "Превышено время ожидания ответа от сервиса."
    if "connection refused" in lower:
        return "Сервер данных отклонил подключение."
    if "connection" in lower:
        return "Проблема с подключением к серверу данных."
    if "rate limit" in lower:
        return "Превышен лимит запросов к сервису нейросети."

    return msg[:300] if len(msg) > 300 else msg


_METRIC_NAMES = {
    "revenue_before_spp": "Выручка (до СПП)",
    "revenue_after_spp": "Выручка (после СПП)",
    "margin": "Маржа",
    "margin_pct": "Маржинальность",
    "orders_count": "Заказы",
    "sales_count": "Продажи",
    "drr": "ДРР",
    "ad_spend": "Расходы на рекламу",
    "cpo": "CPO (стоимость заказа)",
    "avg_check": "Средний чек",
}


def _humanize_metric(metric: str) -> str:
    """Перевод технического имени метрики в читаемое."""
    return _METRIC_NAMES.get(metric, metric)
