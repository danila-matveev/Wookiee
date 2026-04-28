# apps_script

Google Apps Script — кастомные кнопки и автоматизации, которые живут в Google Sheets и дёргают Wookiee API на App Server.

В отличие от `services/sheets_sync/` (Python ETL: Wookiee DB → Sheets), скрипты здесь работают **из браузера в Sheets**: пользователь жмёт кнопку в таблице → Apps Script делает HTTP-запрос на API → API запускает collector и обновляет данные.

## Содержимое

| Файл | Назначение | Подключается к |
|---|---|---|
| `promocodes_button.gs` | Кнопка «🔄 ОБНОВИТЬ» в Sheets `Промокоды_аналитика` — триггерит `services/wb_promocodes/` collector через HTTP API | `http://77.233.212.61:8092` (App Server, Promocodes API) |

## Как добавить новый скрипт

1. Создай `<feature>_button.gs` (или другой подходящий suffix).
2. В заголовке файла — install-инструкция: какой Sheet, какие Script Properties, какой триггер.
3. Если нужен новый API endpoint — добавь его в соответствующий сервис под `services/` и пропиши URL в Script Properties (никогда не хардкодь токены).

## Owner
danila-matveev
