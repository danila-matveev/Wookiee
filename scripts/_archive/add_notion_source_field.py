"""
Добавить поле "Источник" в Notion базу данных
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.config import NOTION_TOKEN, NOTION_DATABASE_ID
import urllib.request
import json

API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

def add_source_field():
    """
    Добавляет поле "Источник" с опциями "Скрипт" и "Telegram Bot"
    """
    url = f"{API_BASE}/databases/{NOTION_DATABASE_ID}"

    # Payload для обновления схемы базы данных
    payload = {
        "properties": {
            "Источник": {
                "select": {
                    "options": [
                        {
                            "name": "Скрипт",
                            "color": "blue"
                        },
                        {
                            "name": "Telegram Bot",
                            "color": "green"
                        }
                    ]
                }
            }
        }
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="PATCH")
    req.add_header("Authorization", f"Bearer {NOTION_TOKEN}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")

    try:
        print("🔄 Добавляю поле 'Источник' в базу данных...")
        print(f"Database ID: {NOTION_DATABASE_ID}")
        print()

        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())

        print("=" * 80)
        print("✅ ПОЛЕ 'ИСТОЧНИК' УСПЕШНО ДОБАВЛЕНО!")
        print("=" * 80)
        print()
        print("Настройки поля:")
        print("  Название: Источник")
        print("  Тип: Select (выпадающий список)")
        print("  Опции:")
        print("    1. Скрипт (синий)")
        print("    2. Telegram Bot (зеленый)")
        print()
        print("=" * 80)
        print()
        print("Что это значит:")
        print("  - Все отчеты из скриптов будут помечены как 'Скрипт'")
        print("  - Все отчеты из Telegram бота будут помечены как 'Telegram Bot'")
        print()
        print("Теперь можно фильтровать отчеты по источнику в Notion! 🎉")
        print("=" * 80)

        return True

    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ ERROR: {e.code}")
        print(body)

        # Проверяем если поле уже существует
        if "already exists" in body.lower() or "property already exists" in body.lower():
            print()
            print("ℹ️  Похоже поле уже существует. Запустите check_notion_db.py для проверки.")

        return False

if __name__ == "__main__":
    success = add_source_field()

    if success:
        print()
        print("🔍 Проверка: запустите 'python3 scripts/check_notion_db.py' чтобы увидеть новое поле")
        sys.exit(0)
    else:
        sys.exit(1)
