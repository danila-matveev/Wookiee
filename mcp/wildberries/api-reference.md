# Wildberries MCP Server — API Reference

Полный справочник всех инструментов с параметрами.

---

## Products (20 tools)

### `wb_get_products`
Получить список товаров продавца с пагинацией и фильтрацией.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| limit | number | - | Кол-во записей (default: 100) |
| offset | number | - | Смещение (default: 0) |
| search | string | - | Поиск по названию/артикулу |
| brandID | number | - | Фильтр по бренду |
| updatedAtFrom | string | - | Дата начала обновления |
| updatedAtTo | string | - | Дата конца обновления |

### `wb_update_product_content`
Обновить контент товара: название, описание, характеристики.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| nmID | number | да | ID номенклатуры |
| title | string | - | Название |
| description | string | - | Описание |
| characteristics | array | - | Массив {id, name, value} |

### `wb_update_product_price`
Обновить цену товара и/или скидку.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| nmID | number | да | ID номенклатуры |
| price | number | да | Цена |
| discount | number | - | Скидка (%) |

### `wb_update_product_stock`
Обновить остатки товара на складе.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| nmID | number | да | ID номенклатуры |
| warehouseID | number | да | ID склада |
| quantity | number | да | Количество |

### `wb_get_parent_categories`
Справочник родительских категорий.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| locale | string | - | Локаль (default: "ru") |

### `wb_get_subjects`
Справочник предметов (подкатегорий).

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| name | string | - | Поиск по названию |
| locale | string | - | Локаль |

### `wb_get_subject_charcs`
Характеристики предмета по ID.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| subjectId | number | да | ID предмета |

### `wb_get_colors`
Справочник цветов. Параметр: `locale` (string, опц.)

### `wb_get_gender_kinds`
Справочник полов. Параметр: `locale` (string, опц.)

### `wb_get_countries`
Справочник стран. Параметр: `locale` (string, опц.)

### `wb_get_seasons`
Справочник сезонов. Параметр: `locale` (string, опц.)

### `wb_get_vat_rates`
Справочник ставок НДС. Без параметров.

### `wb_get_tnved`
Справочник кодов ТНВЭД.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| subjectId | number | - | Фильтр по предмету |

### `wb_get_brands`
Список брендов продавца.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| name | string | - | Поиск по названию |
| locale | string | - | Локаль |

### `wb_get_failed_cards`
Карточки товаров с ошибками. Параметр: `locale` (string, опц.)

### `wb_merge_cards`
Объединить карточки товаров.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| targetNmID | number | да | Целевая карточка |
| nmIDs | number[] | да | Карточки для объединения |

### `wb_delete_cards`
Удалить карточки (в корзину).

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| nmIDs | number[] | да | ID карточек |

### `wb_recover_cards`
Восстановить удалённые карточки.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| nmIDs | number[] | да | ID карточек |

### `wb_manage_tags`
CRUD операции с тегами.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| action | "list" \| "create" \| "update" \| "delete" | да | Действие |
| id | number | - | ID тега (для update/delete) |
| name | string | - | Название (для create/update) |
| color | string | - | Цвет (для create/update) |

### `wb_link_tag_to_product`
Привязать теги к номенклатуре.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| nmID | number | да | ID номенклатуры |
| tagsIDs | number[] | да | ID тегов |

---

## Prices (3 tools)

### `wb_get_goods_prices`
Список товаров с ценами и скидками.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| limit | number | - | Кол-во (default: 100) |
| offset | number | - | Смещение |
| filterNmID | number | - | Фильтр по nmID |

### `wb_upload_prices`
Загрузить цены и скидки.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| data | array | да | [{nmID, price, discount?}] |

### `wb_upload_size_prices`
Загрузить цены для размеров.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| data | array | да | [{nmID, sizeID, price}] |

---

## Orders FBS (25 tools)

### `wb_get_orders_fbs`
Список заказов FBS за период.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало периода |
| dateTo | string | да | Конец периода |
| status | string | - | new/confirm/complete/cancel/cancel_by_client |
| take | number | - | Кол-во (default: 100) |
| skip | number | - | Смещение |

### `wb_get_picking_tasks_fbs`
Сборочные задания FBS.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |
| status | string | - | Статус |

### `wb_update_order_status_fbs`
Обновить статус заказа.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| orderUID | string | да | UID заказа |
| status | string | да | new/confirm/complete/cancel/cancel_by_client |

### `wb_get_new_orders_fbs`
Новые сборочные задания. Без параметров.

### `wb_get_orders_statuses_fbs`
Статусы заказов по ID.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| orderIds | number[] | да | ID заказов |

### `wb_cancel_order_fbs`
Отменить сборочное задание.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| orderId | number | да | ID заказа |

### `wb_get_order_stickers`
Стикеры для заказов.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| orderIds | number[] | да | ID заказов |
| type | "svg" \| "png" | - | Формат |
| width | number | - | Ширина |
| height | number | - | Высота |

### `wb_get_crossborder_stickers`
Кроссбордер стикеры. Параметр: `orderIds` (number[], обяз.)

### `wb_get_status_history`
История статусов. Параметр: `orderIds` (number[], обяз.)

### `wb_get_orders_with_client`
Заказы с данными клиента (ФИО, адрес). Параметр: `orderIds` (number[], обяз.)

### `wb_get_reshipment_orders`
Заказы на повторную отправку. Без параметров.

### `wb_get_order_metadata`
Метаданные заказов (КиЗ, УИН, IMEI). Параметр: `orderIds` (number[], обяз.)

### `wb_delete_order_metadata`
Удалить метаданные. Параметр: `orderId` (number, обяз.)

### `wb_set_order_metadata`
Установить метаданные.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| orderId | number | да | ID заказа |
| metaType | "sgtin" \| "uin" \| "imei" \| "gtin" \| "expiration" | да | Тип |
| value | string | да | Значение |

### `wb_create_supply`
Создать поставку. Параметр: `name` (string, обяз.)

### `wb_get_supplies`
Список поставок.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| limit | number | - | Кол-во (default: 100) |
| next | number | - | Курсор пагинации |

### `wb_get_supply`
Информация о поставке. Параметр: `supplyId` (string, обяз.)

### `wb_delete_supply`
Удалить поставку (только неотправленные). Параметр: `supplyId` (string, обяз.)

### `wb_add_orders_to_supply`
Добавить заказы в поставку.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| supplyId | string | да | ID поставки |
| orderIds | number[] | да | ID заказов |

### `wb_deliver_supply`
Передать поставку в доставку. Параметр: `supplyId` (string, обяз.)

### `wb_get_supply_barcode`
Штрихкод/QR поставки.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| supplyId | string | да | ID поставки |
| type | "svg" \| "png" | - | Формат |

### `wb_get_supply_boxes`
Список коробок поставки. Параметр: `supplyId` (string, обяз.)

### `wb_manage_supply_boxes`
Управление коробками.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| supplyId | string | да | ID поставки |
| action | "add" \| "delete" | да | Действие |
| boxes | string[] | - | ID коробок |

### `wb_get_passes`
Список пропусков на склады. Без параметров.

### `wb_manage_pass`
Управление пропусками.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| action | "create" \| "update" \| "delete" | да | Действие |
| passId | number | - | ID пропуска |
| firstName | string | - | Имя |
| lastName | string | - | Фамилия |
| carModel | string | - | Модель авто |
| carNumber | string | - | Номер авто |
| officeId | number | - | ID склада |

---

## Orders DBW (12 tools)

### `wb_get_new_orders_dbw`
Новые заказы DBW. Без параметров.

### `wb_get_orders_dbw`
Список заказов DBW.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| limit | number | - | Кол-во |
| next | number | - | Курсор |

### `wb_get_delivery_date_dbw`
Даты доставки. Параметр: `orderIds` (number[], обяз.)

### `wb_get_client_info_dbw`
Информация о клиенте. Параметр: `orderIds` (number[], обяз.)

### `wb_get_orders_statuses_dbw`
Статусы заказов. Параметр: `orderIds` (number[], обяз.)

### `wb_confirm_order_dbw`
Подтвердить заказ. Параметр: `orderId` (number, обяз.)

### `wb_assemble_order_dbw`
В сборку. Параметр: `orderId` (number, обяз.)

### `wb_cancel_order_dbw`
Отменить. Параметр: `orderId` (number, обяз.)

### `wb_get_stickers_dbw`
Стикеры. Параметр: `orderIds` (number[], обяз.)

### `wb_get_courier_dbw`
Информация о курьере. Параметр: `orderIds` (number[], обяз.)

### `wb_get_metadata_dbw`
Метаданные (КиЗ, УИН, IMEI, GTIN). Параметр: `orderId` (number, обяз.)

### `wb_set_metadata_dbw`
Установить метаданные.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| orderId | number | да | ID заказа |
| metaType | "sgtin" \| "uin" \| "imei" \| "gtin" | да | Тип |
| value | string | да | Значение |

---

## Orders DBS (13 tools)

### `wb_get_new_orders_dbs`
Новые заказы DBS. Без параметров.

### `wb_get_orders_dbs`
Список заказов. Параметры: `limit` (number), `next` (number).

### `wb_get_groups_info_dbs`
Группы заказов. Параметр: `orderIds` (number[], обяз.)

### `wb_get_client_info_dbs`
Информация о клиенте. Параметр: `orderIds` (number[], обяз.)

### `wb_get_b2b_info_dbs`
B2B реквизиты. Параметр: `orderIds` (number[], обяз.)

### `wb_get_delivery_date_dbs`
Даты доставки. Параметр: `orderIds` (number[], обяз.)

### `wb_get_statuses_dbs`
Статусы. Параметр: `orderIds` (number[], обяз.)

### `wb_cancel_orders_dbs`
Отменить. Параметр: `orderIds` (number[], обяз.)

### `wb_confirm_orders_dbs`
Подтвердить. Параметр: `orderIds` (number[], обяз.)

### `wb_deliver_orders_dbs`
В доставку. Параметр: `orderIds` (number[], обяз.)

### `wb_receive_orders_dbs`
Подтвердить получение клиентом. Параметр: `orderIds` (number[], обяз.)

### `wb_reject_orders_dbs`
Отклонить (отказ клиента). Параметр: `orderIds` (number[], обяз.)

### `wb_get_stickers_dbs`
Стикеры. Параметр: `orderIds` (number[], обяз.)

---

## Analytics (15 tools)

### `wb_get_search_queries`
Поисковые запросы по товарам.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |
| nmID | number | - | Фильтр по товару |

### `wb_get_stock_history`
История остатков по складам.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |
| nmID | number | да | ID номенклатуры |

### `wb_get_sales_funnel`
Воронка продаж: просмотры → корзина → заказы → выкупы → отмены.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |
| nmID | number | - | Фильтр по товару |

### `wb_get_product_sales_stats`
Статистика продаж (воронка v3) с фильтрами.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |
| nmIDs | number[] | - | Фильтр по артикулам |
| brandNames | string[] | - | Фильтр по брендам |
| tagIDs | number[] | - | Фильтр по тегам |
| objectIDs | number[] | - | Фильтр по категориям |
| page | number | - | Страница |
| orderBy | object | - | Сортировка |

### `wb_get_product_stats_daily`
Ежедневная статистика по товарам.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |
| nmIDs | number[] | - | Артикулы |
| period | "day" \| "week" | - | Группировка |
| page | number | - | Страница |

### `wb_get_grouped_stats_daily`
Группированная статистика по категории/бренду/тегу.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |
| groupBy | "subject" \| "brand" \| "tag" | да | Группировка |
| period | "day" \| "week" | - | Период |
| page | number | - | Страница |

### `wb_get_search_report`
Сводный отчёт по поисковым запросам.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |

### `wb_get_search_report_groups`
Группы поискового отчёта. Параметры: `dateFrom`, `dateTo` (обяз.), `page` (опц.)

### `wb_get_search_report_details`
Детали группы.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |
| groupId | string | да | ID группы |
| page | number | - | Страница |

### `wb_get_product_search_texts`
Запросы, по которым находят товар.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| nmID | number | да | ID товара |
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |

### `wb_get_product_orders_by_query`
Заказы в разрезе поисковых запросов. Параметры аналогичны `wb_get_product_search_texts`.

### `wb_get_stocks_by_groups`
Остатки по группам. Параметры: `dateFrom`, `dateTo` (обяз.)

### `wb_get_stocks_by_products`
Остатки по товарам. Параметры: `dateFrom`, `dateTo` (обяз.), `groupId` (опц.)

### `wb_get_stocks_by_sizes`
Остатки по размерам.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |
| nmID | number | да | ID товара |

### `wb_get_stocks_by_warehouses`
Остатки по складам. Параметры: `dateFrom`, `dateTo` (обяз.)

---

## Feedback (18 tools)

### `wb_get_new_feedbacks_questions`
Количество неотвеченных отзывов и вопросов. Без параметров.

### `wb_get_questions_count`
Количество неотвеченных вопросов.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | - | Начало |
| dateTo | string | - | Конец |

### `wb_get_questions`
Список вопросов.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| isAnswered | boolean | - | Фильтр по ответу |
| take | number | - | Кол-во |
| skip | number | - | Смещение |
| dateFrom | string | - | Начало |
| dateTo | string | - | Конец |
| nmId | number | - | Фильтр по товару |

### `wb_get_question`
Вопрос по ID. Параметр: `id` (string, обяз.)

### `wb_answer_question`
Ответить на вопрос.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| id | string | да | ID вопроса |
| answer | string | да | Текст ответа |
| state | "wbRu" \| "none" | да | Площадка |

### `wb_get_feedbacks_count`
Количество неотвеченных отзывов. Параметры: `dateFrom`, `dateTo` (опц.)

### `wb_get_feedbacks`
Список отзывов.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| isAnswered | boolean | - | Фильтр по ответу |
| take | number | - | Кол-во |
| skip | number | - | Смещение |
| dateFrom | string | - | Начало |
| dateTo | string | - | Конец |
| nmId | number | - | Фильтр по товару |
| order | "dateAsc" \| "dateDesc" | - | Сортировка |

### `wb_get_feedback`
Отзыв по ID. Параметр: `id` (string, обяз.)

### `wb_answer_feedback`
Ответить на отзыв.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| id | string | да | ID отзыва |
| text | string | да | Текст ответа |

### `wb_edit_feedback_answer`
Редактировать ответ. Параметры: `id` (string, обяз.), `text` (string, обяз.)

### `wb_return_feedback_order`
Возврат по отзыву. Параметр: `id` (string, обяз.)

### `wb_get_archived_feedbacks`
Архивные отзывы. Параметры: `take`, `skip` (опц.)

### `wb_get_pinned_reviews`
Закреплённые отзывы. Параметр: `nmId` (number, обяз.)

### `wb_pin_reviews`
Закрепить отзывы. Параметр: `feedbackIds` (string[], обяз.)

### `wb_unpin_reviews`
Открепить отзывы. Параметр: `feedbackIds` (string[], обяз.)

### `wb_get_chats`
Список чатов. Параметры: `take`, `skip` (опц.)

### `wb_get_chat_events`
Сообщения чата. Параметр: `chatId` (string, обяз.)

### `wb_send_chat_message`
Отправить сообщение. Параметры: `chatId` (string, обяз.), `message` (string, обяз.)

---

## Reports (10 tools)

### `wb_get_warehouse_stocks_report`
Остатки на складах. Параметр: `dateFrom` (string, обяз.)

### `wb_get_orders_report`
Отчёт по заказам.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| flag | number | - | 0=все, 1=только изменённые |

### `wb_get_sales_report`
Отчёт по продажам. Параметры: `dateFrom` (обяз.), `flag` (опц.)

### `wb_create_warehouse_remains`
Остатки (асинхронный отчёт).

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| groupByBrand | boolean | - | По бренду |
| groupBySubject | boolean | - | По категории |
| groupBySa | boolean | - | По артикулу |

### `wb_get_excise_report`
Акцизные товары. Параметры: `dateFrom`, `dateTo` (обяз.)

### `wb_get_retention_reports`
Удержания (штрафы, антифрод, маркировка).

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| reportType | "measurement-penalties" \| "deductions" \| "antifraud-details" \| "goods-labeling" | да | Тип |
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |

### `wb_create_acceptance_report`
Приёмка (асинхронный). Параметры: `dateFrom`, `dateTo` (обяз.)

### `wb_create_paid_storage_report`
Платное хранение (асинхронный). Параметры: `dateFrom`, `dateTo` (обяз.)

### `wb_get_regional_sales`
Продажи по регионам.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |
| brandNames | string[] | - | Бренды |
| objectIDs | number[] | - | Категории |

### `wb_get_brand_share`
Доля бренда в продажах.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |
| brandId | number | - | ID бренда |

---

## Marketing (24 tools)

### `wb_get_campaigns_count`
Количество кампаний по статусам. Без параметров.

### `wb_get_campaigns`
Список кампаний.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| status | number | - | Статус |
| type | number | - | Тип |
| order | string | - | Сортировка |
| limit | number | - | Кол-во |
| offset | number | - | Смещение |

### `wb_create_campaign`
Создать кампанию.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| type | number | да | Тип кампании |
| name | string | да | Название |
| subjectId | number | да | ID предмета |
| nmIds | number[] | да | Товары |

### `wb_delete_campaign`
Удалить. Параметр: `id` (number, обяз.)

### `wb_rename_campaign`
Переименовать.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| advertId | number | да | ID кампании |
| name | string | да | Новое название |

### `wb_start_campaign`, `wb_pause_campaign`, `wb_stop_campaign`
Управление статусом. Параметр: `id` (number, обяз.)

### `wb_get_min_bids`
Минимальные ставки.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| type | number | да | Тип кампании |
| nmIds | number[] | да | Товары |

### `wb_set_bids`
Установить ставки.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| advertId | number | да | ID кампании |
| type | number | да | Тип |
| cpm | number | да | Ставка CPM |
| param | number | да | Параметр |
| instrument | number | - | Инструмент |

### `wb_get_bid_recommendations`
Рекомендации по ставкам. Параметр: `advertId` (number, обяз.)

### `wb_change_placements`
Площадки размещения.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| advertId | number | да | ID кампании |
| placementIds | number[] | да | Площадки |

### `wb_change_campaign_products`
Товары в кампании.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| advertId | number | да | ID кампании |
| nmIds | number[] | да | Товары |
| action | "add" \| "delete" | - | Действие |

### `wb_get_campaign_subjects`
Предметы для рекламы. Без параметров.

### `wb_get_campaign_products`
Товары для рекламы. Параметр: `nmIds` (number[], опц.)

### `wb_get_search_bids`
Ставки по поисковым запросам. Параметр: `advertId` (number, обяз.)

### `wb_set_search_bids`
Установить поисковые ставки.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| advertId | number | да | ID кампании |
| bids | array | да | [{query, cpm}] |

### `wb_delete_search_bids`
Удалить поисковые ставки.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| advertId | number | да | ID кампании |
| queries | string[] | да | Запросы |

### `wb_get_minus_phrases`
Минус-фразы. Параметр: `advertId` (number, обяз.)

### `wb_set_minus_phrases`
Установить минус-фразы.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| advertId | number | да | ID кампании |
| phrases | string[] | да | Минус-фразы |

### `wb_get_cluster_stats`
Статистика кластеров.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| advertId | number | да | ID кампании |
| dateFrom | string | - | Начало |
| dateTo | string | - | Конец |

### `wb_get_ad_balance`
Баланс рекламного кабинета. Без параметров.

### `wb_get_ad_budget`
Бюджет кампании. Параметр: `id` (number, обяз.)

### `wb_deposit_ad_budget`
Пополнить бюджет.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| id | number | да | ID кампании |
| sum | number | да | Сумма |

### `wb_get_ad_spending`
Расходы на рекламу. Параметры: `from`, `to` (string, опц.)

---

## Tariffs (5 tools)

### `wb_get_commission_tariffs`
Комиссии по категориям. Параметр: `locale` (string, опц.)

### `wb_get_box_tariffs`
Доставка коробами. Параметр: `date` (string, опц.)

### `wb_get_pallet_tariffs`
Доставка паллетами. Параметр: `date` (string, опц.)

### `wb_get_acceptance_tariffs`
Коэффициенты приёмки. Параметр: `warehouseId` (number, опц.)

### `wb_get_return_tariffs`
Тарифы возвратов. Параметр: `locale` (string, опц.)

---

## Supplies FBW (7 tools)

### `wb_get_acceptance_options`
Варианты приёмки (склады, даты, коэффициенты). Параметр: `nmIDs` (number[], обяз.)

### `wb_get_warehouses`
Список складов WB. Без параметров.

### `wb_get_transit_tariffs`
Тарифы транзита. Без параметров.

### `wb_get_fbw_supplies`
Список поставок FBW. Параметры: `limit`, `next` (опц.)

### `wb_get_fbw_supply`
Информация о поставке. Параметр: `id` (string, обяз.)

### `wb_get_fbw_supply_goods`
Товары в поставке. Параметр: `id` (string, обяз.)

### `wb_get_fbw_supply_package`
Упаковка поставки. Параметр: `id` (string, обяз.)

---

## Documents (6 tools)

### `wb_get_account_balance`
Баланс аккаунта продавца. Без параметров.

### `wb_get_sales_realization_report`
Детальный отчёт реализации. Пагинация через rrdid.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| dateFrom | string | да | Начало |
| dateTo | string | да | Конец |
| limit | number | - | Кол-во |
| rrdid | number | - | Курсор пагинации |

### `wb_get_document_categories`
Категории документов. Без параметров.

### `wb_get_documents`
Список документов. Параметры: `dateFrom`, `dateTo` (опц.)

### `wb_download_document`
Скачать документ. Параметр: `id` (string, обяз.)

### `wb_download_documents_bulk`
Массовое скачивание. Параметр: `ids` (string[], обяз.)
