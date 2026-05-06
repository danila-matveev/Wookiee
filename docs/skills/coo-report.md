# /coo-report — Еженедельный отчёт COO

**Запуск:** `/coo-report`

## Что делает

Собирает данные из 5 независимых источников параллельно, проверяет на аномалии и создаёт заполненную страницу в Notion по шаблону операционного директора.

Автоматически заполняет разделы 1, 6, 7, 8, 9 (финансы, комплекты, реклама, логистика, сотрудники).
Разделы 2–5, 10–12 остаются для ручного заполнения.

## Параметры

Параметры не требуются. Период определяется автоматически: текущая неделя (пн–вс).

## Результат

Страница в Notion с 12 разделами:
- **Раздел 1** — P&L WB+OZON за 2 недели (заказы, выручка до/после СПП, себестоимость, логистика, комиссия, ДРР, маржа)
- **Раздел 6** — 16 моделей с выручкой, маржой, трендом, рекомендуемым действием
- **Раздел 7** — внешняя реклама по каналам (блогеры, ВК, создатели; Яндекс — ручной ввод)
- **Раздел 8** — логистика: индекс локализации, оборачиваемость по всем моделям
- **Раздел 9** — сотрудники: выполненные / активные / просроченные задачи Bitrix24

## Сборщики (модули)

| Файл | JSON | Источник |
|------|------|---------|
| `modules/coo_report/collectors/finance.py` | `/tmp/coo_finance.json` | PostgreSQL + WB API + OZON API |
| `modules/coo_report/collectors/models.py` | `/tmp/coo_models.json` | PostgreSQL (orders + ads) |
| `modules/coo_report/collectors/logistics.py` | `/tmp/coo_logistics.json` | МойСклад API + Excel (WB Localization) |
| `modules/coo_report/collectors/ads.py` | `/tmp/coo_ads.json` | PostgreSQL (crm.ad_expenses) |
| `modules/coo_report/collectors/team.py` | `/tmp/coo_team.json` | Bitrix24 REST API |

## Зависимости

- PostgreSQL (DB Server, read-only)
- WB API (`WB_API_KEY_OOO`, `WB_API_KEY_IP`)
- OZON API
- МойСклад API (`MOYSKLAD_TOKEN`)
- Bitrix24 REST API (`Bitrix_rest_api`)
- Notion API (`NOTION_TOKEN`)
- `shared/data_layer.py`, `shared/config.py`

## Notion шаблон

- Template ID: `35658a2bd5878028ad75f1773a0f8593`
- Parent folder ID: `35658a2bd587803b8ab5fc540e4318e7`
