"""
Тестовая отправка отчета в Notion с пометкой "Telegram Bot"
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.notion_sync import sync_report_to_notion

# Создаем тестовый отчет
test_report = """
# 📊 Тестовый отчет из Telegram Bot

## Период
2026-02-08 — 2026-02-09

## Основные метрики

| Метрика | Значение | Изменение |
|---------|----------|-----------|
| Маржа | 235 007₽ | +3.1% |
| Маржинальность | 18.4% | -0.8 п.п. |
| ДРР | 2.1% | -2.8 п.п. |

## Выводы

- ✅ Маржа растёт (+3.1%)
- ⚠️ Маржинальность снижается
- ✅ ДРР улучшается

---

**Это тестовый отчет для проверки интеграции Telegram Bot → Notion**

🤖 Создано через: **Telegram Bot**
"""

# Даты для теста
yesterday = datetime.now() - timedelta(days=1)
today = datetime.now()

start_date = yesterday.strftime("%Y-%m-%d")
end_date = today.strftime("%Y-%m-%d")

print("=" * 80)
print("ТЕСТОВАЯ ОТПРАВКА ОТЧЕТА В NOTION")
print("=" * 80)
print()
print(f"Период: {start_date} — {end_date}")
print(f"Источник: Telegram Bot (должен быть зелёным)")
print()
print("🔄 Отправляю отчет...")
print()

try:
    # Отправляем с источником "Telegram Bot"
    url = sync_report_to_notion(start_date, end_date, test_report, source="Telegram Bot")

    print()
    print("=" * 80)
    print("✅ ОТЧЕТ УСПЕШНО ОТПРАВЛЕН В NOTION!")
    print("=" * 80)
    print()
    print(f"URL: {url}")
    print()
    print("Проверьте в Notion:")
    print("  1. Откройте базу 'Фин аналитика'")
    print("  2. Найдите отчет за", start_date, "—", end_date)
    print("  3. Проверьте что в колонке 'Источник' стоит 'Telegram Bot' (зелёный)")
    print()
    print("=" * 80)
    print()
    print("Теперь можно:")
    print("  - Фильтровать отчеты: Источник = 'Telegram Bot'")
    print("  - Отличать отчеты бота от отчетов скриптов")
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
