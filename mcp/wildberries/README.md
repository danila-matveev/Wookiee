# Wildberries MCP Server

MCP-сервер для полной интеграции с Wildberries Marketplace API. Покрывает товары, заказы (FBS/DBW/DBS), аналитику, маркетинг, отзывы, отчёты, тарифы и документы.

**Репозиторий:** [github.com/danila-matveev/wildberries-mcp-server](https://github.com/danila-matveev/wildberries-mcp-server)

## Установка

```bash
git clone https://github.com/danila-matveev/wildberries-mcp-server.git
cd wildberries-mcp-server
npm install
npm run build
```

## Настройка

Создайте `.env` из шаблона:

```bash
cp env.example .env
```

```env
WB_API_TOKEN=<ваш API токен Wildberries>
MCP_TRANSPORT=stdio    # stdio (по умолчанию) или http
MCP_PORT=8080          # порт для HTTP транспорта
LOG_LEVEL=info         # debug, info, warn, error
```

## Подключение к Claude Code

В `.mcp.json` вашего проекта:

```json
{
  "mcpServers": {
    "wildberries": {
      "type": "stdio",
      "command": "node",
      "args": ["/path/to/wildberries-mcp-server/dist/index.js"],
      "env": {
        "WB_API_TOKEN": "<your-token>"
      }
    }
  }
}
```

Для работы с несколькими магазинами — добавьте несколько инстансов с разными токенами (`wildberries-ip`, `wildberries-ooo`).

## Категории инструментов

| Категория | Tools | Описание |
|-----------|-------|----------|
| [Products](#products) | 20 | Товары, карточки, характеристики, теги, справочники |
| [Prices](#prices) | 3 | Цены, скидки, размерные цены |
| [Orders FBS](#orders-fbs) | 25 | Заказы FBS, поставки, стикеры, пропуска |
| [Orders DBW](#orders-dbw) | 12 | Заказы с доставкой Wildberries |
| [Orders DBS](#orders-dbs) | 13 | Заказы с доставкой продавца |
| [Analytics](#analytics) | 15 | Воронка продаж, поисковые запросы, остатки |
| [Feedback](#feedback) | 18 | Отзывы, вопросы, чаты с покупателями |
| [Reports](#reports) | 10 | Склад, продажи, реализация, удержания |
| [Marketing](#marketing) | 24 | Рекламные кампании, ставки, минус-фразы |
| [Tariffs](#tariffs) | 5 | Комиссии, доставка, приёмка, возвраты |
| [Supplies FBW](#supplies-fbw) | 7 | Поставки на склады WB, тарифы транзита |
| [Documents](#documents) | 6 | Баланс, отчёт реализации, документы |
| **Итого** | **158** | |

## Products

Управление товарными карточками, контентом, справочниками.

- `wb_get_products` — Список товаров с фильтрацией и пагинацией
- `wb_update_product_content` — Обновление контента (название, описание, характеристики)
- `wb_update_product_price` — Обновление цены и скидки
- `wb_update_product_stock` — Обновление остатков на складе
- `wb_get_parent_categories` — Справочник родительских категорий
- `wb_get_subjects` — Справочник предметов (подкатегорий)
- `wb_get_subject_charcs` — Характеристики предмета по ID
- `wb_get_colors`, `wb_get_gender_kinds`, `wb_get_countries`, `wb_get_seasons` — Справочники
- `wb_get_vat_rates` — Ставки НДС
- `wb_get_tnved` — Коды ТНВЭД
- `wb_get_brands` — Бренды продавца
- `wb_get_failed_cards` — Карточки с ошибками
- `wb_merge_cards`, `wb_delete_cards`, `wb_recover_cards` — Управление карточками
- `wb_manage_tags` — CRUD тегов
- `wb_link_tag_to_product` — Привязка тегов к товарам

## Prices

- `wb_get_goods_prices` — Список товаров с ценами
- `wb_upload_prices` — Загрузка цен и скидок
- `wb_upload_size_prices` — Цены для конкретных размеров

## Orders FBS

Fulfillment by Seller — заказы, поставки, сборочные задания.

- `wb_get_orders_fbs` — Список заказов за период
- `wb_get_picking_tasks_fbs` — Сборочные задания
- `wb_update_order_status_fbs` — Обновление статуса
- `wb_get_new_orders_fbs` — Новые задания
- `wb_get_orders_statuses_fbs` — Статусы по ID
- `wb_cancel_order_fbs` — Отмена задания
- `wb_get_order_stickers` — Стикеры (SVG/PNG)
- `wb_get_crossborder_stickers` — Кроссбордер стикеры
- `wb_get_status_history` — История статусов
- `wb_get_orders_with_client` — Данные клиента (ФИО, адрес)
- `wb_get_reshipment_orders` — Повторная отправка
- `wb_get_order_metadata`, `wb_set_order_metadata`, `wb_delete_order_metadata` — Метаданные (КиЗ, УИН, IMEI)
- `wb_create_supply`, `wb_get_supplies`, `wb_get_supply`, `wb_delete_supply` — Управление поставками
- `wb_add_orders_to_supply`, `wb_deliver_supply` — Сборка и отправка
- `wb_get_supply_barcode` — Штрихкод поставки
- `wb_get_supply_boxes`, `wb_manage_supply_boxes` — Коробки
- `wb_get_passes`, `wb_manage_pass` — Пропуска на склады

## Orders DBW

Delivery by Wildberries — доставка силами WB.

- `wb_get_new_orders_dbw`, `wb_get_orders_dbw` — Получение заказов
- `wb_get_delivery_date_dbw` — Даты доставки
- `wb_get_client_info_dbw` — Информация о клиенте
- `wb_get_orders_statuses_dbw` — Статусы
- `wb_confirm_order_dbw`, `wb_assemble_order_dbw`, `wb_cancel_order_dbw` — Управление
- `wb_get_stickers_dbw` — Стикеры
- `wb_get_courier_dbw` — Информация о курьере
- `wb_get_metadata_dbw`, `wb_set_metadata_dbw` — Метаданные

## Orders DBS

Delivery by Seller — доставка продавцом.

- `wb_get_new_orders_dbs`, `wb_get_orders_dbs` — Получение заказов
- `wb_get_groups_info_dbs` — Группы заказов
- `wb_get_client_info_dbs` — Клиент
- `wb_get_b2b_info_dbs` — B2B реквизиты
- `wb_get_delivery_date_dbs` — Даты доставки
- `wb_get_statuses_dbs` — Статусы
- `wb_cancel_orders_dbs`, `wb_confirm_orders_dbs`, `wb_deliver_orders_dbs` — Управление
- `wb_receive_orders_dbs`, `wb_reject_orders_dbs` — Подтверждение/отклонение
- `wb_get_stickers_dbs` — Стикеры

## Analytics

Статистика продаж, поисковые запросы, остатки.

- `wb_get_search_queries` — Поисковые запросы по товарам
- `wb_get_stock_history` — История остатков
- `wb_get_sales_funnel` — Воронка: просмотры → корзина → заказы → выкупы
- `wb_get_product_sales_stats` — Статистика продаж (v3) с фильтрами
- `wb_get_product_stats_daily` — Ежедневная статистика
- `wb_get_grouped_stats_daily` — Группированная статистика (по категории/бренду/тегу)
- `wb_get_search_report`, `wb_get_search_report_groups`, `wb_get_search_report_details` — Поисковые отчёты
- `wb_get_product_search_texts` — Запросы, по которым находят товар
- `wb_get_product_orders_by_query` — Заказы по запросам
- `wb_get_stocks_by_groups`, `wb_get_stocks_by_products`, `wb_get_stocks_by_sizes`, `wb_get_stocks_by_warehouses` — Остатки в разрезах

## Feedback

Отзывы, вопросы, чаты.

- `wb_get_new_feedbacks_questions` — Количество неотвеченных
- `wb_get_questions_count`, `wb_get_questions`, `wb_get_question` — Вопросы
- `wb_answer_question` — Ответ на вопрос
- `wb_get_feedbacks_count`, `wb_get_feedbacks`, `wb_get_feedback` — Отзывы
- `wb_answer_feedback`, `wb_edit_feedback_answer` — Ответы на отзывы
- `wb_return_feedback_order` — Возврат по отзыву
- `wb_get_archived_feedbacks` — Архив
- `wb_get_pinned_reviews`, `wb_pin_reviews`, `wb_unpin_reviews` — Закреплённые отзывы
- `wb_get_chats`, `wb_get_chat_events`, `wb_send_chat_message` — Чаты

## Reports

Отчёты по складу, продажам, удержаниям.

- `wb_get_warehouse_stocks_report` — Остатки на складах
- `wb_get_orders_report` — Отчёт по заказам
- `wb_get_sales_report` — Отчёт по продажам
- `wb_create_warehouse_remains` — Остатки (асинхронный)
- `wb_get_excise_report` — Акцизные товары
- `wb_get_retention_reports` — Удержания (штрафы, антифрод, маркировка)
- `wb_create_acceptance_report` — Приёмка (асинхронный)
- `wb_create_paid_storage_report` — Платное хранение (асинхронный)
- `wb_get_regional_sales` — Продажи по регионам
- `wb_get_brand_share` — Доля бренда

## Marketing

Рекламные кампании, ставки, минус-фразы.

- `wb_get_campaigns_count`, `wb_get_campaigns` — Список кампаний
- `wb_create_campaign`, `wb_delete_campaign`, `wb_rename_campaign` — CRUD
- `wb_start_campaign`, `wb_pause_campaign`, `wb_stop_campaign` — Управление статусом
- `wb_get_min_bids`, `wb_set_bids`, `wb_get_bid_recommendations` — Ставки
- `wb_change_placements` — Площадки размещения
- `wb_change_campaign_products` — Товары в кампании
- `wb_get_campaign_subjects`, `wb_get_campaign_products` — Справочники
- `wb_get_search_bids`, `wb_set_search_bids`, `wb_delete_search_bids` — Поисковые ставки
- `wb_get_minus_phrases`, `wb_set_minus_phrases` — Минус-фразы
- `wb_get_cluster_stats` — Статистика кластеров
- `wb_get_ad_balance`, `wb_get_ad_budget`, `wb_deposit_ad_budget` — Бюджет
- `wb_get_ad_spending` — Расходы на рекламу

## Tariffs

- `wb_get_commission_tariffs` — Комиссии WB по категориям
- `wb_get_box_tariffs` — Доставка коробами
- `wb_get_pallet_tariffs` — Доставка паллетами
- `wb_get_acceptance_tariffs` — Коэффициенты приёмки
- `wb_get_return_tariffs` — Тарифы на возвраты

## Supplies FBW

Поставки на склады Wildberries.

- `wb_get_acceptance_options` — Варианты приёмки (склады, даты, коэффициенты)
- `wb_get_warehouses` — Список складов WB
- `wb_get_transit_tariffs` — Тарифы транзита
- `wb_get_fbw_supplies`, `wb_get_fbw_supply` — Поставки FBW
- `wb_get_fbw_supply_goods` — Товары в поставке
- `wb_get_fbw_supply_package` — Упаковка поставки

## Documents

- `wb_get_account_balance` — Баланс аккаунта
- `wb_get_sales_realization_report` — Детальный отчёт реализации
- `wb_get_document_categories` — Категории документов
- `wb_get_documents` — Список документов
- `wb_download_document`, `wb_download_documents_bulk` — Скачивание

## Техническая информация

- **Runtime:** Node.js 18+
- **Язык:** TypeScript 5.7+
- **MCP SDK:** @modelcontextprotocol/sdk ^1.0.4
- **HTTP клиент:** axios
- **Валидация:** Zod
- **Логирование:** Winston

**API endpoints:**
- `suppliers-api.wildberries.ru` — основной
- `statistics-api.wildberries.ru` — статистика
- `content-api.wildberries.ru` — контент
- `marketplace-api.wildberries.ru` — маркетплейс
- `advert-api.wildberries.ru` — реклама
- `feedbacks-api.wildberries.ru` — отзывы
- `seller-analytics-api.wildberries.ru` — новая аналитика
- `documents-api.wildberries.ru` — документы
- `discounts-prices-api.wildberries.ru` — цены/скидки

**Rate limiting:** 100 запросов/мин, retry с exponential backoff (макс. 3 попытки).
