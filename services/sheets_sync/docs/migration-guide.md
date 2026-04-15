# Гайд по миграции в новый проект

Пошаговая инструкция для переноса `sheets_sync` в другой проект или разворачивания с нуля.

---

## Шаги

### 1. Скопировать папку

Скопируй весь каталог `services/sheets_sync/` целиком в целевой проект, сохранив структуру:

```
services/sheets_sync/
├── clients/
├── data_layer/
├── docs/
├── sync/
├── apps_script/
├── credentials/       # только папка, не сам JSON ключ
├── config.py
├── shared_config.py
├── runner.py
├── control_panel.py
├── model_mapping.py
├── status.py
├── requirements.txt
└── __init__.py
```

### 2. Установить зависимости

```bash
pip install httpx>=0.27.0 gspread>=6.0.0 google-auth>=2.20.0 python-dotenv>=1.0.0 pytz>=2024.1 psycopg2-binary>=2.9.0
```

Или установить из `requirements.txt` сервиса:

```bash
pip install -r services/sheets_sync/requirements.txt
```

### 3. Создать .env

Скопировать шаблон и заполнить реальными значениями:

```bash
cp services/sheets_sync/.env.example .env
```

Открыть `.env` и заполнить все переменные. Подробное описание каждой переменной — в [config-and-secrets.md](config-and-secrets.md).

### 4. Настроить Google Service Account

1. Создать Service Account в Google Cloud Console (инструкция в [config-and-secrets.md](config-and-secrets.md))
2. Скачать JSON ключ и разместить его по пути `credentials/google_sa.json`
3. Открыть целевую Google Таблицу и поделиться ею с email сервисного аккаунта (доступ **Редактор**)
4. Скопировать ID таблицы из URL и вставить в `.env` как `SPREADSHEET_ID`

### 5. Настроить Google Apps Script (если нужны кнопки в таблице)

Этот шаг нужен только если требуется ручной запуск синков прямо из Google Таблицы.

1. В Google Таблице открыть **Расширения → Apps Script**
2. Скопировать содержимое файлов из `apps_script/` в соответствующие файлы Apps Script проекта
3. Добавить ключи API в **Script Properties** (⚙️ Настройки проекта → Свойства скрипта):
   - `WB_API_KEY_IP`, `WB_API_KEY_OOO`
   - `OZON_CLIENT_ID_IP`, `OZON_API_KEY_IP`
   - `OZON_CLIENT_ID_OOO`, `OZON_API_KEY_OOO`
   - `MOYSKLAD_TOKEN`
4. Сохранить и проверить работу триггеров

### 6. Проверить тестовый режим

Убедиться, что в `.env` стоит `SYNC_TEST_MODE=true`, затем:

```bash
# Показать список всех доступных синков
python -m services.sheets_sync.runner --list

# Запустить один синк в тестовом режиме
python -m services.sheets_sync.runner wb_prices --test
```

Тестовый режим пишет данные в листы с суффиксом `_TEST` — можно проверить результат в таблице без риска затронуть продакшен данные.

### 7. Запустить в продакшене

После успешной проверки:

1. Установить в `.env`:
   ```
   SYNC_TEST_MODE=false
   ```

2. Запустить фоновый демон с расписанием:
   ```bash
   python -m services.sheets_sync.control_panel
   ```

3. Или запускать отдельные синки вручную через CLI:
   ```bash
   python -m services.sheets_sync.runner wb_prices
   python -m services.sheets_sync.runner ozon_prices
   ```

---

## Чек-лист

- [ ] `.env` заполнен (все обязательные переменные без пустых значений)
- [ ] `credentials/google_sa.json` на месте
- [ ] Таблица расшарена на email сервисного аккаунта с правами Редактор
- [ ] `python -m services.sheets_sync.runner --list` показывает 10 синков без ошибок
- [ ] Тестовый синк прошёл без ошибок, данные появились в листе `*_TEST`
- [ ] Script Properties заполнены (если используются GAS кнопки)
- [ ] `SYNC_TEST_MODE=false` установлен перед продакшен запуском

---

## Обновление импортов

Если `sheets_sync` переносится в проект с другой структурой пакетов, нужно обновить импорты во всех `.py` файлах сервиса.

Найти все вхождения и заменить префикс пакета:

| Старый импорт | Новый импорт |
|---|---|
| `from services.sheets_sync.clients.` | `from <your_package>.sheets_sync.clients.` |
| `from services.sheets_sync.data_layer.` | `from <your_package>.sheets_sync.data_layer.` |
| `from services.sheets_sync.config` | `from <your_package>.sheets_sync.config` |
| `from services.sheets_sync.shared_config` | `from <your_package>.sheets_sync.shared_config` |

Быстрый способ найти все места для замены:

```bash
grep -r "from services.sheets_sync" services/sheets_sync/ --include="*.py"
```

Если структура проекта плоская (не используется `services/` как пакет), убедиться, что в корне проекта есть `__init__.py` или настроен `PYTHONPATH`.
