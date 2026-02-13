"""
Проверка структуры Notion базы данных
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.config import NOTION_TOKEN, NOTION_DATABASE_ID
import urllib.request
import json

API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

def get_database_schema():
    """Получить схему базы данных (список всех свойств)"""
    url = f"{API_BASE}/databases/{NOTION_DATABASE_ID}"

    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {NOTION_TOKEN}")
    req.add_header("Notion-Version", NOTION_VERSION)

    try:
        with urllib.request.urlopen(req) as resp:
            db_info = json.loads(resp.read().decode())

        print("=" * 80)
        print("NOTION DATABASE SCHEMA")
        print("=" * 80)
        print(f"\nDatabase ID: {NOTION_DATABASE_ID}")
        print(f"Title: {db_info.get('title', [{}])[0].get('plain_text', 'N/A')}")
        print("\n" + "=" * 80)
        print("PROPERTIES (СВОЙСТВА):")
        print("=" * 80)

        properties = db_info.get("properties", {})

        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get("type", "unknown")
            print(f"\n✓ {prop_name}")
            print(f"  Type: {prop_type}")

            # Если это Select, показываем доступные опции
            if prop_type == "select":
                options = prop_info.get("select", {}).get("options", [])
                if options:
                    print(f"  Options:")
                    for opt in options:
                        color = opt.get("color", "default")
                        name = opt.get("name", "")
                        print(f"    - {name} ({color})")

        print("\n" + "=" * 80)

        # Проверяем наличие поля "Источник"
        if "Источник" in properties:
            print("✅ ПОЛЕ 'Источник' УЖЕ СУЩЕСТВУЕТ!")
            source_prop = properties["Источник"]
            if source_prop.get("type") == "select":
                options = source_prop.get("select", {}).get("options", [])
                print(f"\nТекущие опции:")
                for opt in options:
                    print(f"  - {opt.get('name')}")

                # Проверяем наличие нужных опций
                option_names = [opt.get("name") for opt in options]
                if "Telegram Bot" in option_names and "Скрипт" in option_names:
                    print("\n✅ ВСЕ НЕОБХОДИМЫЕ ОПЦИИ УЖЕ НАСТРОЕНЫ!")
                else:
                    print("\n⚠️  НУЖНО ДОБАВИТЬ ОПЦИИ:")
                    if "Telegram Bot" not in option_names:
                        print("  - Telegram Bot")
                    if "Скрипт" not in option_names:
                        print("  - Скрипт")
        else:
            print("❌ ПОЛЕ 'Источник' НЕ НАЙДЕНО!")
            print("\nНУЖНО ДОБАВИТЬ ПОЛЕ В NOTION:")
            print("1. Открыть базу данных в Notion")
            print("2. Нажать '+' справа от столбцов")
            print("3. Назвать поле: Источник")
            print("4. Выбрать тип: Select")
            print("5. Добавить опции: 'Скрипт' и 'Telegram Bot'")

        print("=" * 80)

        return properties

    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ ERROR: {e.code}")
        print(body)
        return None

if __name__ == "__main__":
    get_database_schema()
