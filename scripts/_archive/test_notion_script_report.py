"""
Тестовая отправка отчета в Notion с пометкой "Скрипт"
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.notion_sync import sync_report_to_notion

# Создаем тестовый отчет
test_report = """
# 📊 Тестовый отчет из CLI скрипта

## Период
2026-02-07 — 2026-02-08

## Основные метрики

| Метрика | Значение | Изменение |
|---------|----------|-----------|
| Маржа | 228 450₽ | +1.5% |
| Маржинальность | 19.2% | +0.3 п.п. |
| ДРР | 3.8% | -1.2 п.п. |

## Выводы

- ✅ Все показатели в норме
- ✅ Позитивная динамика

---

**Это тестовый отчет для проверки интеграции CLI Script → Notion**

⚙️ Создано через: **Скрипт** (daily_analytics.py)
"""

# Даты для теста (другой период чем у бота)
start_date = "2026-02-07"
end_date = "2026-02-08"

print("=" * 80)
print("ТЕСТОВАЯ ОТПРАВКА ОТЧЕТА ИЗ СКРИПТА В NOTION")
print("=" * 80)
print()
print(f"Период: {start_date} — {end_date}")
print(f"Источник: Скрипт (должен быть синим)")
print()
print("🔄 Отправляю отчет...")
print()

try:
    # Отправляем с источником "Скрипт" (по умолчанию)
    url = sync_report_to_notion(start_date, end_date, test_report, source="Скрипт")

    print()
    print("=" * 80)
    print("✅ ОТЧЕТ УСПЕШНО ОТПРАВЛЕН В NOTION!")
    print("=" * 80)
    print()
    print(f"URL: {url}")
    print()
    print("Теперь в Notion у вас есть два отчета:")
    print()
    print("  1️⃣  2026-02-07 — 2026-02-08 | Источник: Скрипт (синий)")
    print("  2️⃣  2026-02-08 — 2026-02-09 | Источник: Telegram Bot (зелёный)")
    print()
    print("=" * 80)
    print()
    print("Фильтрация в Notion:")
    print("  • Источник = 'Telegram Bot' → показать только отчеты из бота")
    print("  • Источник = 'Скрипт' → показать только отчеты из скриптов")
    print()

except Exception as e:
    print()
    print("=" * 80)
    print("❌ ОШИБКА ПРИ ОТПРАВКЕ")
    print("=" * 80)
    print()
    print(str(e))
    print()
    sys.exit(1)
