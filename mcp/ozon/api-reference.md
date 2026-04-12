# Ozon MCP Server — API Reference

**Всего: 250 инструментов в 32 категориях**

## product (24 tools)

Uploading, updating, and managing products

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_product_import` | `/v3/product/import` | Создать или обновить товар |
| `ozon_product_import_info` | `/v1/product/import/info` | Получить статус импорта товаров |
| `ozon_product_import_by_sku` | `/v1/product/import-by-sku` | Создать товар по Ozon SKU |
| `ozon_product_attributes_update` | `/v1/product/attributes/update` | Обновить характеристики товара |
| `ozon_product_list` | `/v3/product/list` | Получить список товаров с пагинацией |
| `ozon_product_info_list` | `/v3/product/info/list` | Получить детальную информацию о товарах |
| `ozon_product_info_attributes` | `/v4/product/info/attributes` | Получить описание характеристик товара |
| `ozon_product_info_description` | `/v1/product/info/description` | Получить описание товара для создания аналогичного |
| `ozon_product_info_discounted` | `/v1/product/info/discounted` | Получить информацию об уценённом и основном товаре |
| `ozon_product_info_subscription` | `/v1/product/info/subscription` | Получить информацию о подписке на товар |
| `ozon_product_info_limit` | `/v4/product/info/limit` | Получить лимиты на создание и обновление товаров |
| `ozon_product_pictures_import` | `/v1/product/pictures/import` | Загрузить или обновить изображения товара |
| `ozon_product_pictures_info` | `/v2/product/pictures/info` | Проверить статус загрузки изображений |
| `ozon_product_archive` | `/v1/product/archive` | Переместить товар в архив |
| `ozon_product_unarchive` | `/v1/product/unarchive` | Вернуть товар из архива |
| `ozon_products_delete` | `/v2/products/delete` | Удалить товар (только без SKU, из архива) |
| `ozon_product_upload_digital_codes` | `/v1/product/upload_digital_codes` | Загрузить коды активации для сервисов и цифровых товаров |
| `ozon_product_update_offer_id` | `/v1/product/update/offer-id` | Обновить артикул (offer_id) товара |
| `ozon_product_rating_by_sku` | `/v1/product/rating-by-sku` | Получить рейтинг товара по SKU |
| `ozon_product_related_sku_get` | `/v1/product/related-sku/get` | Получить связанные SKU товара |
| `ozon_product_info_wrong_volume` | `/v1/product/info/wrong-volume` | Получить список товаров с некорректными габаритами |
| `ozon_product_update_discount` | `/v1/product/update/discount` | Обновить скидку на товар |
| `ozon_product_action_timer_status` | `/v1/product/action/timer/status` | Получить статус таймера акции товара |
| `ozon_product_action_timer_update` | `/v1/product/action/timer/update` | Обновить таймер акции товара |

## fbs (26 tools)

FBS and rFBS order processing

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_fbs_unfulfilled_list` | `/v3/posting/fbs/unfulfilled/list` | Список необработанных отправлений FBS |
| `ozon_fbs_posting_list` | `/v3/posting/fbs/list` | Список отправлений FBS |
| `ozon_fbs_posting_get` | `/v3/posting/fbs/get` | Получить детали отправления FBS по ID |
| `ozon_fbs_posting_get_by_barcode` | `/v2/posting/fbs/get-by-barcode` | Получить данные отправления по штрих-коду |
| `ozon_fbs_multiboxqty_set` | `/v3/posting/multiboxqty/set` | Указать кол-во коробок для мультикоробочного отправления |
| `ozon_fbs_posting_ship` | `/v4/posting/fbs/ship` | Подтвердить отгрузку FBS отправления |
| `ozon_fbs_posting_ship_package` | `/v4/posting/fbs/ship/package` | Подтвердить отгрузку FBS с упаковкой |
| `ozon_fbs_posting_cancel` | `/v2/posting/fbs/cancel` | Отменить отправление FBS |
| `ozon_fbs_cancel_reason_list` | `/v2/posting/fbs/cancel-reason/list` | Список причин отмены FBS |
| `ozon_fbs_posting_cancel_reason` | `/v1/posting/fbs/cancel-reason` | Получить причину отмены отправления |
| `ozon_fbs_product_cancel` | `/v2/posting/fbs/product/cancel` | Отменить товар в отправлении FBS |
| `ozon_fbs_product_change` | `/v2/posting/fbs/product/change` | Изменить товар в отправлении FBS |
| `ozon_fbs_posting_awaiting_delivery` | `/v2/posting/fbs/awaiting-delivery` | Перевести отправления в статус ожидания доставки |
| `ozon_fbs_posting_arbitration` | `/v2/posting/fbs/arbitration` | Открыть спор по отправлению FBS |
| `ozon_fbs_posting_cutoff_set` | `/v1/posting/cutoff/set` | Установить дату отгрузки |
| `ozon_fbs_posting_restrictions` | `/v1/posting/fbs/restrictions` | Получить ограничения для FBS отправления |
| `ozon_fbs_posting_etgb` | `/v1/posting/global/etgb` | Получить ЭТГБ для международных отправлений |
| `ozon_fbs_package_label_create` | `/v1/posting/fbs/package-label/create` | Создать маркировку упаковки |
| `ozon_fbs_package_label_get` | `/v1/posting/fbs/package-label/get` | Получить маркировку упаковки |
| `ozon_fbs_package_label_v2` | `/v2/posting/fbs/package-label` | Получить маркировки для отправлений |
| `ozon_fbs_package_label_create_v2` | `/v2/posting/fbs/package-label/create` | Создать маркировку упаковки (v2) |
| `ozon_fbs_product_country_list` | `/v2/posting/fbs/product/country/list` | Список стран для товара в отправлении |
| `ozon_fbs_product_country_set` | `/v2/posting/fbs/product/country/set` | Установить страну для товара в отправлении |
| `ozon_fbs_posting_split` | `/v1/posting/fbs/split` | Разделить отправление FBS |
| `ozon_fbs_pick_up_code_verify` | `/v1/posting/fbs/pick-up-code/verify` | Проверить код получения курьера |
| `ozon_fbs_unpaid_legal_product_list` | `/v1/posting/unpaid-legal/product/list` | Список неоплаченных юрлицами товаров |

## fbo (3 tools)

FBO order management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_fbo_posting_list` | `/v2/posting/fbo/list` | Список отправлений FBO |
| `ozon_fbo_posting_get` | `/v2/posting/fbo/get` | Получить детали отправления FBO |
| `ozon_fbo_cancel_reason_list` | `/v1/posting/fbo/cancel-reason/list` | Список причин отмены по схеме FBO |

## supply_order (13 tools)

FBO supply request management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_supply_order_list` | `/v2/supply-order/list` | Список заявок на поставку FBO |
| `ozon_supply_order_list_v3` | `/v3/supply-order/list` | Список заявок на поставку FBO (v3) |
| `ozon_supply_order_get` | `/v2/supply-order/get` | Получить детали заявки на поставку |
| `ozon_supply_order_get_v3` | `/v3/supply-order/get` | Получить детали заявки на поставку (v3) |
| `ozon_supply_order_status_counter` | `/v1/supply-order/status/counter` | Количество заявок на поставку по статусам |
| `ozon_supply_order_bundle` | `/v1/supply-order/bundle` | Содержимое поставки или заявки на поставку |
| `ozon_supply_order_cancel` | `/v1/supply-order/cancel` | Отменить заявку на поставку |
| `ozon_supply_order_cancel_status` | `/v1/supply-order/cancel/status` | Статус отмены заявки на поставку |
| `ozon_supply_order_timeslot_get` | `/v1/supply-order/timeslot/get` | Получить таймслот поставки |
| `ozon_supply_order_timeslot_update` | `/v1/supply-order/timeslot/update` | Обновить таймслот поставки |
| `ozon_supply_order_timeslot_status` | `/v1/supply-order/timeslot/status` | Статус таймслота поставки |
| `ozon_supply_order_pass_create` | `/v1/supply-order/pass/create` | Создать пропуск для поставки |
| `ozon_supply_order_pass_status` | `/v1/supply-order/pass/status` | Статус пропуска для поставки |

## supply_draft (8 tools)

FBO supply draft management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_draft_cluster_list` | `/v1/cluster/list` | Информация о кластерах и их складах |
| `ozon_draft_warehouse_fbo_list` | `/v1/warehouse/fbo/list` | Найти точки для отгрузки поставки |
| `ozon_draft_create` | `/v1/draft/create` | Создать черновик заявки на поставку |
| `ozon_draft_create_info` | `/v1/draft/create/info` | Детали черновика заявки на поставку |
| `ozon_draft_supply_create` | `/v1/draft/supply/create` | Создать поставку из черновика |
| `ozon_draft_supply_create_status` | `/v1/draft/supply/create/status` | Статус создания поставки из черновика |
| `ozon_draft_timeslot_info` | `/v1/draft/timeslot/info` | Информация о таймслотах черновика |
| `ozon_draft_supplier_available_warehouses` | `/v1/supplier/available_warehouses` | Доступные склады поставщика |

## delivery_fbs (17 tools)

FBS delivery methods and freights

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_delivery_fbs_carriage_create` | `/v1/carriage/create` | Создать грузоперевозку |
| `ozon_delivery_fbs_carriage_approve` | `/v1/carriage/approve` | Подтвердить грузоперевозку |
| `ozon_delivery_fbs_carriage_cancel` | `/v1/carriage/cancel` | Удалить грузоперевозку |
| `ozon_delivery_fbs_carriage_get` | `/v1/carriage/get` | Получить информацию о грузоперевозке |
| `ozon_delivery_fbs_carriage_set_postings` | `/v1/carriage/set-postings` | Изменить состав отправлений грузоперевозки |
| `ozon_delivery_fbs_carriage_delivery_list` | `/v1/carriage/delivery/list` | Список способов доставки и грузоперевозок |
| `ozon_delivery_fbs_carriage_available_list` | `/v1/posting/carriage-available/list` | Список отправлений доступных для грузоперевозки |
| `ozon_delivery_fbs_act_create` | `/v2/posting/fbs/act/create` | Создать акт приёма-передачи |
| `ozon_delivery_fbs_act_check_status` | `/v2/posting/fbs/act/check-status` | Проверить статус акта |
| `ozon_delivery_fbs_act_get_pdf` | `/v2/posting/fbs/act/get-pdf` | Получить акт приёма-передачи в PDF |
| `ozon_delivery_fbs_act_get_barcode` | `/v2/posting/fbs/act/get-barcode` | Получить штрихкод акта |
| `ozon_delivery_fbs_act_get_barcode_text` | `/v2/posting/fbs/act/get-barcode/text` | Получить текстовый штрихкод акта |
| `ozon_delivery_fbs_act_get_container_labels` | `/v2/posting/fbs/act/get-container-labels` | Получить этикетки контейнеров |
| `ozon_delivery_fbs_act_get_postings` | `/v2/posting/fbs/act/get-postings` | Список отправлений в акте |
| `ozon_delivery_fbs_act_list` | `/v2/posting/fbs/act/list` | Список актов приёма-передачи |
| `ozon_delivery_fbs_digital_act_check_status` | `/v2/posting/fbs/digital/act/check-status` | Проверить статус цифрового акта |
| `ozon_delivery_fbs_digital_act_get_pdf` | `/v2/posting/fbs/digital/act/get-pdf` | Получить цифровой акт в PDF |

## delivery_rfbs (7 tools)

rFBS delivery management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_delivery_rfbs_tracking_number_set` | `/v2/fbs/posting/tracking-number/set` | Добавить трек-номера отправлений |
| `ozon_delivery_rfbs_sent_by_seller` | `/v2/fbs/posting/sent-by-seller` | Изменить статус на 'Отправлено продавцом' |
| `ozon_delivery_rfbs_delivering` | `/v2/fbs/posting/delivering` | Изменить статус на 'Доставляется' |
| `ozon_delivery_rfbs_last_mile` | `/v2/fbs/posting/last-mile` | Изменить статус на 'Последняя миля' |
| `ozon_delivery_rfbs_delivered` | `/v2/fbs/posting/delivered` | Изменить статус на 'Доставлено' |
| `ozon_delivery_rfbs_timeslot_set` | `/v1/posting/fbs/timeslot/set` | Установить таймслот отгрузки |
| `ozon_delivery_rfbs_timeslot_change_restrictions` | `/v1/posting/fbs/timeslot/change-restrictions` | Получить ограничения на изменение таймслота |

## marks (10 tools)

FBS/rFBS product labeling and order packaging

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_marks_exemplar_validate_v5` | `/v5/fbs/posting/product/exemplar/validate` | Проверить коды маркировки (v5) |
| `ozon_marks_exemplar_validate_v4` | `/v4/fbs/posting/product/exemplar/validate` | Проверить коды маркировки (v4) |
| `ozon_marks_exemplar_set_v6` | `/v6/fbs/posting/product/exemplar/set` | Проверить и сохранить данные экземпляров (v6) |
| `ozon_marks_exemplar_set_v5` | `/v5/fbs/posting/product/exemplar/set` | Проверить и сохранить данные экземпляров (v5) |
| `ozon_marks_exemplar_set_v4` | `/v4/fbs/posting/product/exemplar/set` | Проверить и сохранить данные экземпляров (v4) |
| `ozon_marks_exemplar_status_v5` | `/v5/fbs/posting/product/exemplar/status` | Статус проверки экземпляров (v5) |
| `ozon_marks_exemplar_status_v4` | `/v4/fbs/posting/product/exemplar/status` | Статус проверки экземпляров (v4) |
| `ozon_marks_exemplar_create_or_get_v6` | `/v6/fbs/posting/product/exemplar/create-or-get` | Создать или получить данные экземпляров (v6) |
| `ozon_marks_exemplar_create_or_get_v5` | `/v5/fbs/posting/product/exemplar/create-or-get` | Создать или получить данные экземпляров (v5) |
| `ozon_marks_exemplar_update` | `/v1/fbs/posting/product/exemplar/update` | Обновить данные экземпляра |

## prices_stocks (5 tools)

Prices and stock management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_prices_stocks_update` | `/v2/products/stocks` | Обновить количество товаров на складе |
| `ozon_prices_stocks_info` | `/v4/product/info/stocks` | Информация о количестве товара на складах |
| `ozon_prices_stocks_by_warehouse_fbs` | `/v1/product/info/stocks-by-warehouse/fbs` | Остатки на складах продавца (FBS и rFBS) |
| `ozon_prices_import` | `/v1/product/import/prices` | Обновить цены товаров |
| `ozon_prices_info` | `/v5/product/info/prices` | Информация о ценах, комиссиях и скидках |

## finance (12 tools)

Financial reports and transactions

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_finance_transaction_list` | `/v3/finance/transaction/list` | Список транзакций |
| `ozon_finance_transaction_totals` | `/v3/finance/transaction/totals` | Общая сумма транзакций |
| `ozon_finance_realization` | `/v2/finance/realization` | Отчёт о реализации (v2) |
| `ozon_finance_realization_posting` | `/v1/finance/realization/posting` | Отчёт о реализации по заказу |
| `ozon_finance_realization_by_day` | `/v1/finance/realization/by-day` | Отчёт о реализации по дням (Premium) |
| `ozon_finance_cash_flow_statement_list` | `/v1/finance/cash-flow-statement/list` | Финансовый отчёт (ДДС) |
| `ozon_finance_compensation` | `/v1/finance/compensation` | Получить информацию о компенсациях |
| `ozon_finance_decompensation` | `/v1/finance/decompensation` | Получить информацию о декомпенсациях |
| `ozon_finance_mutual_settlement` | `/v1/finance/mutual-settlement` | Взаиморасчёты |
| `ozon_finance_products_buyout` | `/v1/finance/products/buyout` | Отчёт о выкупе товаров |
| `ozon_finance_document_b2b_sales` | `/v1/finance/document-b2b-sales` | Документы B2B продаж |
| `ozon_finance_document_b2b_sales_json` | `/v1/finance/document-b2b-sales/json` | Документы B2B продаж в JSON |

## analytics (10 tools)

Analytics and data reports

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_analytics_data` | `/v1/analytics/data` | Получить аналитические данные (Premium) |
| `ozon_analytics_stock_on_warehouses` | `/v2/analytics/stock_on_warehouses` | Отчёт об остатках и товарах на складах |
| `ozon_analytics_stocks` | `/v1/analytics/stocks` | Аналитика по остаткам на складах |
| `ozon_analytics_manage_stocks` | `/v1/analytics/manage/stocks` | Управление остатками |
| `ozon_analytics_turnover_stocks` | `/v1/analytics/turnover/stocks` | Оборачиваемость товаров |
| `ozon_analytics_average_delivery_time` | `/v1/analytics/average-delivery-time` | Аналитика среднего времени доставки |
| `ozon_analytics_average_delivery_time_details` | `/v1/analytics/average-delivery-time/details` | Детальная аналитика среднего времени доставки по кластерам |
| `ozon_analytics_average_delivery_time_summary` | `/v1/analytics/average-delivery-time/summary` | Сводка среднего времени доставки |
| `ozon_analytics_product_queries` | `/v1/analytics/product-queries` | Поисковые запросы по товарам (Premium) |
| `ozon_analytics_product_queries_details` | `/v1/analytics/product-queries/details` | Детали поисковых запросов по товарам (Premium) |

## warehouse (11 tools)

Warehouse management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_warehouse_list` | `/v1/warehouse/list` | Список складов FBS и rFBS |
| `ozon_warehouse_list_v2` | `/v2/warehouse/list` | Список складов (v2) |
| `ozon_warehouse_delivery_method_list` | `/v1/delivery-method/list` | Список способов доставки для склада |
| `ozon_warehouse_fbs_create` | `/v1/warehouse/fbs/create` | Создать склад FBS |
| `ozon_warehouse_fbs_update` | `/v1/warehouse/fbs/update` | Обновить настройки склада FBS |
| `ozon_warehouse_fbs_first_mile_update` | `/v1/warehouse/fbs/first-mile/update` | Обновить первую милю склада |
| `ozon_warehouse_archive` | `/v1/warehouse/archive` | Переместить склад в архив |
| `ozon_warehouse_unarchive` | `/v1/warehouse/unarchive` | Вернуть склад из архива |
| `ozon_warehouse_operation_status` | `/v1/warehouse/operation/status` | Статус операции со складом |
| `ozon_warehouse_fbs_create_dropoff_list` | `/v1/warehouse/fbs/create/drop-off/list` | Список точек отгрузки для создания склада |
| `ozon_warehouse_fbs_update_dropoff_list` | `/v1/warehouse/fbs/update/drop-off/list` | Список точек отгрузки для изменения склада |

## category (4 tools)

Product categories and attributes

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_category_tree` | `/v1/description-category/tree` | Дерево категорий и типов товаров |
| `ozon_category_attribute` | `/v1/description-category/attribute` | Список характеристик категории |
| `ozon_category_attribute_values` | `/v1/description-category/attribute/values` | Справочник значений характеристик |
| `ozon_category_attribute_values_search` | `/v1/description-category/attribute/values/search` | Поиск значений характеристик |

## report (7 tools)

Report generation and management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_report_info` | `/v1/report/info` | Детали отчёта |
| `ozon_report_list` | `/v1/report/list` | Список отчётов |
| `ozon_report_products_create` | `/v1/report/products/create` | Создать отчёт по товарам |
| `ozon_report_returns_create` | `/v2/report/returns/create` | Создать отчёт по возвратам |
| `ozon_report_postings_create` | `/v1/report/postings/create` | Создать отчёт по отправлениям |
| `ozon_report_warehouse_stock` | `/v1/report/warehouse/stock` | Создать отчёт по остаткам на складах |
| `ozon_report_discounted_create` | `/v1/report/discounted/create` | Создать отчёт по уценённым товарам |

## chat (8 tools)

Customer chat management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_chat_list` | `/v3/chat/list` | Список чатов (v3) |
| `ozon_chat_list_v2` | `/v2/chat/list` | Список чатов (v2) |
| `ozon_chat_history` | `/v3/chat/history` | История чата (v3, Premium) |
| `ozon_chat_history_v2` | `/v2/chat/history` | История чата (v2) |
| `ozon_chat_send_message` | `/v1/chat/send/message` | Отправить текстовое сообщение (Premium) |
| `ozon_chat_send_file` | `/v1/chat/send/file` | Отправить файл в чат |
| `ozon_chat_start` | `/v1/chat/start` | Создать новый чат с покупателем (Premium) |
| `ozon_chat_read` | `/v2/chat/read` | Отметить сообщения прочитанными (Premium) |

## review (7 tools)

Product reviews management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_review_list` | `/v1/review/list` | Список отзывов |
| `ozon_review_info` | `/v1/review/info` | Информация об отзыве |
| `ozon_review_count` | `/v1/review/count` | Количество отзывов по статусам |
| `ozon_review_change_status` | `/v1/review/change-status` | Изменить статус отзыва |
| `ozon_review_comment_create` | `/v1/review/comment/create` | Оставить комментарий к отзыву |
| `ozon_review_comment_delete` | `/v1/review/comment/delete` | Удалить комментарий к отзыву |
| `ozon_review_comment_list` | `/v1/review/comment/list` | Список комментариев к отзыву |

## promos (8 tools)

Promotions and discount tasks

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_promos_actions_list` | `/v1/actions` | Список доступных акций |
| `ozon_promos_candidates` | `/v1/actions/candidates` | Товары, которые могут участвовать в акции |
| `ozon_promos_products` | `/v1/actions/products` | Товары, участвующие в акции |
| `ozon_promos_products_activate` | `/v1/actions/products/activate` | Добавить товары в акцию |
| `ozon_promos_products_deactivate` | `/v1/actions/products/deactivate` | Убрать товары из акции |
| `ozon_promos_discounts_task_list` | `/v1/actions/discounts-task/list` | Список запросов покупателей на скидку |
| `ozon_promos_discounts_task_approve` | `/v1/actions/discounts-task/approve` | Одобрить запрос на скидку |
| `ozon_promos_discounts_task_decline` | `/v1/actions/discounts-task/decline` | Отклонить запрос на скидку |

## pricing_strategy (12 tools)

Pricing strategy management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_pricing_competitors_list` | `/v1/pricing-strategy/competitors/list` | Список конкурентов |
| `ozon_pricing_strategy_list` | `/v1/pricing-strategy/list` | Список ценовых стратегий |
| `ozon_pricing_strategy_create` | `/v1/pricing-strategy/create` | Создать ценовую стратегию |
| `ozon_pricing_strategy_info` | `/v1/pricing-strategy/info` | Информация о стратегии |
| `ozon_pricing_strategy_update` | `/v1/pricing-strategy/update` | Обновить ценовую стратегию |
| `ozon_pricing_strategy_delete` | `/v1/pricing-strategy/delete` | Удалить ценовую стратегию |
| `ozon_pricing_strategy_status` | `/v1/pricing-strategy/status` | Включить/выключить стратегию |
| `ozon_pricing_products_add` | `/v1/pricing-strategy/products/add` | Привязать товары к стратегии |
| `ozon_pricing_products_delete` | `/v1/pricing-strategy/products/delete` | Отвязать товары от стратегии |
| `ozon_pricing_products_list` | `/v1/pricing-strategy/products/list` | Список товаров привязанных к стратегии |
| `ozon_pricing_strategy_ids_by_product_ids` | `/v1/pricing-strategy/strategy-ids-by-product-ids` | Получить ID стратегий по ID товаров |
| `ozon_pricing_product_info` | `/v1/pricing-strategy/product/info` | Информация о ценовой стратегии товара |

## certification (14 tools)

Quality certificates management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_cert_accordance_types` | `/v1/product/certificate/accordance-types` | Список типов соответствия (v1) |
| `ozon_cert_accordance_types_v2` | `/v2/product/certificate/accordance-types/list` | Список типов соответствия (v2) |
| `ozon_cert_types` | `/v1/product/certificate/types` | Справочник типов документов |
| `ozon_cert_certification_list` | `/v2/product/certification/list` | Список категорий требующих сертификации |
| `ozon_cert_status_list` | `/v1/product/certificate/status/list` | Список статусов сертификатов |
| `ozon_cert_create` | `/v1/product/certificate/create` | Создать сертификат качества |
| `ozon_cert_delete` | `/v1/product/certificate/delete` | Удалить сертификат |
| `ozon_cert_info` | `/v1/product/certificate/info` | Информация о сертификате |
| `ozon_cert_list` | `/v1/product/certificate/list` | Список сертификатов |
| `ozon_cert_bind` | `/v1/product/certificate/bind` | Привязать сертификат к товару |
| `ozon_cert_unbind` | `/v1/product/certificate/products/unbind` | Отвязать товар от сертификата |
| `ozon_cert_products_list` | `/v1/product/certificate/products/list` | Список товаров привязанных к сертификату |
| `ozon_cert_product_status_list` | `/v1/product/certificate/product_status/list` | Статусы сертификации товаров |
| `ozon_cert_rejection_reasons_list` | `/v1/product/certificate/rejection_reasons/list` | Список причин отклонения сертификата |

## cancellation (3 tools)

rFBS cancellation request management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_cancellation_list` | `/v2/conditional-cancellation/list` | Список запросов на отмену rFBS |
| `ozon_cancellation_approve` | `/v2/conditional-cancellation/approve` | Одобрить запрос на отмену rFBS |
| `ozon_cancellation_reject` | `/v2/conditional-cancellation/reject` | Отклонить запрос на отмену rFBS |

## returns_fbo (2 tools)

FBO and FBS returns

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_returns_list` | `/v1/returns/list` | Информация о возвратах FBO и FBS |
| `ozon_returns_company_fbs_info` | `/v1/returns/company/fbs/info` | Количество возвратов FBS |

## returns_rfbs (8 tools)

rFBS returns management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_returns_rfbs_list` | `/v2/returns/rfbs/list` | Список заявок на возврат rFBS |
| `ozon_returns_rfbs_get` | `/v2/returns/rfbs/get` | Информация о заявке на возврат rFBS |
| `ozon_returns_rfbs_reject` | `/v2/returns/rfbs/reject` | Отклонить заявку на возврат rFBS |
| `ozon_returns_rfbs_compensate` | `/v2/returns/rfbs/compensate` | Компенсировать возврат rFBS |
| `ozon_returns_rfbs_receive_return` | `/v2/returns/rfbs/receive-return` | Подтвердить получение возврата rFBS |
| `ozon_returns_rfbs_return_money` | `/v2/returns/rfbs/return-money` | Вернуть деньги за возврат rFBS |
| `ozon_returns_rfbs_verify` | `/v2/returns/rfbs/verify` | Проверить состояние возвращённого товара |
| `ozon_returns_rfbs_action_set` | `/v1/returns/rfbs/action/set` | Установить действие по возврату rFBS |

## return_giveout (7 tools)

Return shipments by barcode

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_giveout_is_enabled` | `/v1/return/giveout/is-enabled` | Проверить возможность получения возвратов по штрихкоду |
| `ozon_giveout_list` | `/v1/return/giveout/list` | Список возвратных грузов |
| `ozon_giveout_info` | `/v1/return/giveout/info` | Информация о возвратном грузе |
| `ozon_giveout_barcode` | `/v1/return/giveout/barcode` | Получить штрихкод возвратного груза (текст) |
| `ozon_giveout_barcode_reset` | `/v1/return/giveout/barcode-reset` | Сбросить штрихкод возвратного груза |
| `ozon_giveout_get_pdf` | `/v1/return/giveout/get-pdf` | Получить штрихкод возвратного груза в PDF |
| `ozon_giveout_get_png` | `/v1/return/giveout/get-png` | Получить штрихкод возвратного груза в PNG |

## pass (7 tools)

Warehouse delivery passes

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_pass_list` | `/v1/pass/list` | Список пропусков |
| `ozon_pass_carriage_create` | `/v1/carriage/pass/create` | Создать пропуск для грузоперевозки |
| `ozon_pass_carriage_update` | `/v1/carriage/pass/update` | Обновить пропуск для грузоперевозки |
| `ozon_pass_carriage_delete` | `/v1/carriage/pass/delete` | Удалить пропуск для грузоперевозки |
| `ozon_pass_return_create` | `/v1/return/pass/create` | Создать пропуск для возврата |
| `ozon_pass_return_update` | `/v1/return/pass/update` | Обновить пропуск для возврата |
| `ozon_pass_return_delete` | `/v1/return/pass/delete` | Удалить пропуск для возврата |

## barcode (2 tools)

Product barcode management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_barcode_add` | `/v1/barcode/add` | Привязать штрихкоды к товарам |
| `ozon_barcode_generate` | `/v1/barcode/generate` | Сгенерировать штрихкоды для товаров |

## polygon (2 tools)

Delivery zone polygons

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_polygon_create` | `/v1/polygon/create` | Создать полигон доставки |
| `ozon_polygon_bind` | `/v1/polygon/bind` | Привязать способ доставки к полигону |

## rating (2 tools)

Seller rating

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_rating_summary` | `/v1/rating/summary` | Текущие рейтинги продавца |
| `ozon_rating_history` | `/v1/rating/history` | Рейтинги продавца за период |

## brand (1 tools)

Brand certificates

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_brand_company_certification_list` | `/v1/brand/company-certification/list` | Список сертифицированных брендов |

## quant (2 tools)

Economy segment products

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_quant_list` | `/v1/product/quant/list` | Список товаров эконом-сегмента |
| `ozon_quant_info` | `/v1/product/quant/info` | Информация о товаре эконом-сегмента |

## digital (3 tools)

Digital products management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_digital_codes_upload` | `/v1/posting/digital/codes/upload` | Загрузить коды для цифровых товаров |
| `ozon_digital_posting_list` | `/v1/posting/digital/list` | Список отправлений цифровых товаров |
| `ozon_digital_stocks_import` | `/v1/product/digital/stocks/import` | Обновить количество цифровых товаров |

## invoice (4 tools)

Invoice management

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_invoice_create_or_update` | `/v2/invoice/create-or-update` | Создать или обновить счёт-фактуру |
| `ozon_invoice_file_upload` | `/v1/invoice/file/upload` | Загрузить файл счёт-фактуры |
| `ozon_invoice_get` | `/v2/invoice/get` | Получить информацию о счёт-фактуре |
| `ozon_invoice_delete` | `/v1/invoice/delete` | Удалить ссылку на счёт-фактуру |

## seller (1 tools)

Seller information

| Инструмент | Endpoint | Описание |
|------------|----------|----------|
| `ozon_seller_roles` | `/v1/roles` | Получить список ролей и методов по API-ключу |

