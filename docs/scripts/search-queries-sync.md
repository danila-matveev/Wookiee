# Аналитика поисковых запросов WB — Документация

## Что делает скрипт

Еженедельно выгружает данные из WB API о том, по каким поисковым запросам покупатели находят наши товары. Записывает в Google Sheets.

**Таблица:** [Wookiee — Аналитика поисковых запросов](https://docs.google.com/spreadsheets/d/1I4UFVYkUELm5phk8MDv518kF6z5sQJFmRdaLYg_-CPY)

## Структура таблицы

### Лист "Аналитика по запросам" (основной)

| Колонка | Содержание |
|---------|-----------|
| A | Поисковые запросы (редактируемые вручную) |
| B | Номенклатура WB (nmId) для фильтрации переходов |
| C | Артикул продавца |
| D | Назначение (брендированный запрос / Яндекс / Таргет ВК / и т.д.) |
| E | Статус |
| F | Название кампании |
| G+ | Данные: каждая неделя = 4 колонки (Частота, Переходы, Добавления, Заказы) |

**Строка 1:** заголовки (Частота / Переходы / Добавления / Заказы)
**Строка 2:** даты периода (DD.MM.YYYY)
**Строки 3+:** данные по каждому запросу

### Лист "nmIds"

| Колонка | Содержание |
|---------|-----------|
| A | Номенклатура WB (nmId) |
| B | Кабинет ("ООО Вуки" или "ИП Медведева П.В.") |

### Лист "Аналитика по запросам (поартикульно)"

Детализация по каждому артикулу — только для наших отслеживаемых запросов. Перезаписывается каждую неделю (хранит только последний период).

## Как добавить новый запрос для отслеживания

1. Открой таблицу → лист "Аналитика по запросам"
2. Добавь запрос в колонку A (любая свободная строка после строки 3)
3. Если нужно фильтровать переходы по конкретному артикулу — укажи nmId в колонке B
4. При следующем запуске скрипт подхватит новый запрос автоматически

## Как добавить новый артикул

1. Открой лист "nmIds"
2. Добавь строку: nmId в колонку A, кабинет в колонку B
3. Кабинет должен быть точно: `ООО Вуки` или `ИП Медведева П.В.`

## Ручной запуск

```bash
# С рабочей машины (из корня проекта):

# Автоматически — прошлая неделя (Пн-Вс)
python scripts/run_search_queries_sync.py

# Конкретный период
python scripts/run_search_queries_sync.py 07.04.2026 13.04.2026
```

Время выполнения: ~8 минут (11 API-запросов × 21 сек rate limit × 2 кабинета).

## Автоматический запуск (cron)

Cron настроен в `deploy/docker-compose.yml` — каждый **понедельник в 10:00 МСК**.

```
0 10 * * 1 cd /app && python scripts/run_search_queries_sync.py
```

Логика: в понедельник выгружаем данные за прошлую полную неделю (Пн-Вс).

## Деплой на сервер

### Шаг 1: Убедиться, что файлы в git

```bash
git add services/sheets_sync/sync/sync_search_queries.py
git add scripts/run_search_queries_sync.py
git add deploy/docker-compose.yml
git commit -m "feat: search queries sync script with weekly cron"
git push
```

### Шаг 2: Подключиться к серверу и задеплоить

```bash
ssh timeweb
cd ~/wookiee          # или где лежит проект
git pull
docker compose -f deploy/docker-compose.yml up -d --build
```

Docker пересоберёт контейнер `wookiee_oleg` с обновлённым cron. Скрипт начнёт работать автоматически со следующего понедельника.

### Шаг 3: Проверить, что cron установился

```bash
ssh timeweb
docker exec wookiee_oleg crontab -l
```

Должен показать две строки:
```
*/30 7-18 * * * cd /app && python scripts/run_report.py --schedule >> /proc/1/fd/1 2>&1
0 10 * * 1 cd /app && python scripts/run_search_queries_sync.py >> /proc/1/fd/1 2>&1
```

### Шаг 4: Тестовый прогон на сервере

```bash
ssh timeweb
docker exec wookiee_oleg python scripts/run_search_queries_sync.py
```

## Зависимости

- **API-ключи** в `.env`: `WB_API_KEY_OOO` (oid 947388) и `WB_API_KEY_IP` (oid 105757)
- **Google SA** файл: `services/sheets_sync/credentials/google_sa.json`
- **Spreadsheet ID:** `1I4UFVYkUELm5phk8MDv518kF6z5sQJFmRdaLYg_-CPY` (захардкожен в run_search_queries_sync.py)
- **Python пакеты:** httpx, gspread, google-auth (уже в проекте)

## Файлы

| Файл | Назначение |
|------|-----------|
| `services/sheets_sync/sync/sync_search_queries.py` | Основная логика (API, агрегация, запись) |
| `scripts/run_search_queries_sync.py` | CLI-обёртка для cron |
| `deploy/docker-compose.yml` | Cron-расписание |
| `docs/scripts/search-queries-sync.md` | Эта документация |
| `docs/superpowers/specs/2026-04-11-search-query-analytics-design.md` | Спецификация дизайна |

## Ограничения WB API

- Max 50 nmId в одном запросе → пакетирование
- 3 запроса в минуту → пауза 21 сек между запросами
- Лимит ответа: ООО = 100 поисковых слов, ИП = 30
- При 403 (невалидный nmId) — автоматический retry с исключением плохого nmId

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| 403 на всех запросах ИП | Проверь `WB_API_KEY_IP` в `.env` — должен быть oid 105757 |
| Пустые данные | Проверь лист "nmIds" — есть ли артикулы для нужного кабинета |
| Данные не совпадают с GAS | Проверь, что все nmId в листе nmIds актуальны |
| Quota exceeded при создании таблицы | Google Drive SA переполнен — удалить лишние файлы |
