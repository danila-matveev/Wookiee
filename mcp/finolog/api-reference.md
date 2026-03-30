# Finolog MCP Server — API Reference

Полный справочник всех инструментов с параметрами.

---

## Biz (5 tools)

### `finolog_list_biz`
Список всех бизнесов. Без параметров.

### `finolog_create_biz`
Создать бизнес.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| name | string | да | Название |
| base_currency_id | number | да | ID базовой валюты |

### `finolog_get_biz`
Получить бизнес. Параметр: `id` (number, обяз.)

### `finolog_update_biz`
Обновить бизнес.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| id | number | да | ID бизнеса |
| name | string | - | Название |

### `finolog_delete_biz`
Удалить бизнес. Параметр: `id` (number, обяз.)

---

## Account (5 tools)

### `finolog_list_accounts`
Список счетов бизнеса.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| ids | string | - | Фильтр по ID (через запятую) |

### `finolog_create_account`
Создать счёт.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| company_id | number | да | ID юрлица |
| currency_id | number | да | ID валюты |
| name | string | да | Название |
| initial_balance | number | - | Начальный остаток |

### `finolog_get_account`
Получить счёт. Параметры: `biz_id`, `id` (обяз.)

### `finolog_update_account`
Обновить счёт.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| id | number | да | ID счёта |
| name | string | - | Название |
| company_id | number | - | ID юрлица |
| currency_id | number | - | ID валюты |
| initial_balance | number | - | Начальный остаток |

### `finolog_delete_account`
Удалить счёт. Параметры: `biz_id`, `id` (обяз.)

---

## Transaction (8 tools)

### `finolog_list_transactions`
Список транзакций с фильтрацией.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| date_from | string | - | Начало (YYYY-MM-DD) |
| date_to | string | - | Конец |
| category_id | number | - | Категория ДДС |
| contractor_id | number | - | Контрагент |
| account_id | number | - | Счёт |
| project_id | number | - | Проект |
| type | string | - | in / out / transfer |
| status | string | - | created / reconciled |
| page | number | - | Страница |
| per_page | number | - | На странице |

### `finolog_create_transaction`
Создать транзакцию.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| date | string | да | Дата (YYYY-MM-DD) |
| value | number | да | Сумма |
| from_id | number | - | Счёт списания |
| to_id | number | - | Счёт зачисления |
| category_id | number | - | Категория ДДС |
| contractor_id | number | - | Контрагент |
| project_id | number | - | Проект |
| description | string | - | Описание |
| status | string | - | Статус |

### `finolog_get_transaction`
Получить транзакцию. Параметры: `biz_id`, `id` (обяз.)

### `finolog_update_transaction`
Обновить транзакцию. Все параметры как в create, `id` обязателен.

### `finolog_delete_transaction`
Удалить. Параметры: `biz_id`, `id` (обяз.)

### `finolog_split_transaction`
Разделить по категориям.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| id | number | да | ID транзакции |
| items | array | да | [{category_id, value}] |

### `finolog_update_split`
Обновить разделение. Параметры аналогичны split.

### `finolog_delete_split`
Отменить разделение. Параметры: `biz_id`, `id` (обяз.)

---

## Category (5 tools)

### `finolog_list_categories`
Список категорий ДДС. Параметр: `biz_id` (обяз.)

### `finolog_create_category`
Создать категорию.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| name | string | да | Название |
| type | string | да | in / out / inout |
| parent_id | number | - | Родительская категория |
| color | string | - | Цвет |

### `finolog_get_category`
Получить. Параметры: `biz_id`, `id` (обяз.)

### `finolog_update_category`
Обновить. Все параметры как в create, `id` обязателен.

### `finolog_delete_category`
Удалить. Параметры: `biz_id`, `id` (обяз.)

---

## Contractor (6 tools)

### `finolog_list_contractors`
Список контрагентов.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| email | string | - | Поиск по email |
| inn | string | - | Поиск по ИНН |
| query | string | - | Полнотекстовый поиск |
| page | number | - | Страница |
| per_page | number | - | На странице |

### `finolog_create_contractor`
Создать контрагента.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| name | string | да | Название |
| email | string | - | Email |
| phone | string | - | Телефон |
| person | string | - | Контактное лицо |
| description | string | - | Описание |

### `finolog_get_contractor`
Получить. Параметры: `biz_id`, `id` (обяз.)

### `finolog_update_contractor`
Обновить. Все параметры как в create, `id` обязателен.

### `finolog_delete_contractor`
Удалить. Параметры: `biz_id`, `id` (обяз.)

### `finolog_create_autoeditor`
Создать автоправило для контрагента.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| id | number | да | ID контрагента |
| config | object | да | Конфигурация правила |

---

## Company (5 tools)

### `finolog_list_companies`
Список юрлиц. Параметр: `biz_id` (обяз.)

### `finolog_create_company`
Создать юрлицо.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| name | string | да | Краткое название |
| full_name | string | - | Полное название |
| phone | string | - | Телефон |
| web | string | - | Сайт |
| address | string | - | Адрес |

### `finolog_get_company`
Получить. Параметры: `biz_id`, `id` (обяз.)

### `finolog_update_company`
Обновить. Все параметры как в create, `id` обязателен.

### `finolog_delete_company`
Удалить. Параметры: `biz_id`, `id` (обяз.)

---

## Project (5 tools)

### `finolog_list_projects`
Список проектов. Параметр: `biz_id` (обяз.)

### `finolog_create_project`
Создать проект.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| name | string | да | Название |
| currency_id | number | да | ID валюты |
| status | string | - | active / on hold / completed / archive |

### `finolog_get_project`
Получить. Параметры: `biz_id`, `id` (обяз.)

### `finolog_update_project`
Обновить. Все параметры как в create, `id` обязателен.

### `finolog_delete_project`
Удалить. Параметры: `biz_id`, `id` (обяз.)

---

## Requisite (5 tools)

### `finolog_list_requisites`
Список реквизитов.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| contractor_id | number | - | Контрагент |
| ids | string | - | ID через запятую |
| is_bizzed | boolean | - | Только реквизиты бизнеса |

### `finolog_create_requisite`
Создать реквизиты.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| contractor_id | number | да | ID контрагента |
| name | string | да | Название |
| bank_name | string | - | Банк |
| bank_bik | string | - | БИК |
| bank_account | string | - | Расчётный счёт |
| corr_account | string | - | Корр. счёт |
| inn | string | - | ИНН |
| kpp | string | - | КПП |
| ogrn | string | - | ОГРН |
| address | string | - | Адрес |

### `finolog_get_requisite`
Получить. Параметры: `biz_id`, `id` (обяз.)

### `finolog_update_requisite`
Обновить. Все параметры как в create, `id` обязателен.

### `finolog_delete_requisite`
Удалить. Параметры: `biz_id`, `id` (обяз.)

---

## Debt (6 tools)

### `finolog_list_debts`
Список долгов контрагента.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| contractor_id | number | да | ID контрагента |
| date_from | string | - | Начало |
| date_to | string | - | Конец |
| page | number | - | Страница |
| per_page | number | - | На странице |

### `finolog_create_debt`
Создать долг.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| contractor_id | number | да | ID контрагента |
| value | number | да | Сумма |
| date | string | да | Дата (YYYY-MM-DD) |
| type | string | да | in / out |
| currency_id | number | да | ID валюты |

### `finolog_get_debt`
Получить. Параметры: `biz_id`, `contractor_id`, `debt_id` (обяз.)

### `finolog_update_debt`
Обновить.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| contractor_id | number | да | ID контрагента |
| debt_id | number | да | ID долга |
| value | number | - | Сумма |
| date | string | - | Дата |
| type | string | - | in / out |
| currency_id | number | - | Валюта |

### `finolog_delete_debt`
Удалить. Параметры: `biz_id`, `contractor_id`, `debt_id` (обяз.)

### `finolog_delete_debts_bulk`
Массовое удаление.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| contractor_id | number | да | ID контрагента |
| ids | string | да | ID через запятую |

---

## Order (6 tools)

### `finolog_list_orders`
Список заказов.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| type | string | - | in / out |
| status | string | - | Статус |
| date_from | string | - | Начало |
| date_to | string | - | Конец |
| page | number | - | Страница |
| per_page | number | - | На странице |

### `finolog_create_order`
Создать заказ.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| type | string | да | in / out |
| seller_id | number | да | ID продавца |
| buyer_id | number | да | ID покупателя |
| cost_package | object | - | Пакет |
| description | string | - | Описание |

### `finolog_get_order`
Получить. Параметры: `biz_id`, `order_id` (обяз.)

### `finolog_update_order`
Обновить.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| order_id | number | да | ID заказа |
| type | string | - | in / out |
| seller_id | number | - | Продавец |
| buyer_id | number | - | Покупатель |
| description | string | - | Описание |
| status | string | - | Статус |

### `finolog_delete_order`
Удалить. Параметры: `biz_id`, `order_id` (обяз.)

### `finolog_list_order_statuses`
Справочник статусов заказов. Параметр: `biz_id` (обяз.)

---

## Document (6 tools)

### `finolog_list_documents`
Список документов.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| kind | string | - | invoice / shipment |
| template | string | - | Шаблон |
| page | number | - | Страница |
| per_page | number | - | На странице |

### `finolog_create_document`
Создать документ.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| kind | string | да | invoice / shipment |
| vat_type | string | - | Тип НДС |
| contractors | array | - | Контрагенты |
| items | array | - | Позиции |

### `finolog_get_document`
Получить. Параметры: `biz_id`, `id` (обяз.)

### `finolog_update_document`
Обновить. Все параметры как в create, `id` обязателен.

### `finolog_delete_document`
Удалить. Параметры: `biz_id`, `id` (обяз.)

### `finolog_get_document_pdf`
Скачать PDF документа.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| id | number | да | ID документа |
| no_sign | boolean | - | Без подписи |

---

## Item (5 tools)

### `finolog_list_items`
Список товаров/услуг.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| query | string | - | Поиск |
| page | number | - | Страница |
| per_page | number | - | На странице |

### `finolog_create_item`
Создать товар/услугу.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| name | string | да | Название |
| price | number | да | Цена |
| currency_id | number | да | ID валюты |
| type | string | - | product / service |
| unit_id | number | - | Единица измерения |
| description | string | - | Описание |

### `finolog_get_item`
Получить. Параметры: `biz_id`, `id` (обяз.)

### `finolog_update_item`
Обновить. Параметры: `biz_id`, `id` (обяз.) + `name`, `price`, `currency_id` (обяз.)

### `finolog_delete_item`
Удалить. Параметры: `biz_id`, `id` (обяз.)

---

## Package (3 tools)

### `finolog_create_package`
Создать пакет в заказе.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| vat_type | string | - | Тип НДС |

### `finolog_update_package`
Обновить пакет.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| package_id | number | да | ID пакета |
| vat_type | string | - | Тип НДС |

### `finolog_delete_package`
Удалить пакет. Параметры: `biz_id`, `package_id` (обяз.)

---

## Package-Item (3 tools)

### `finolog_add_package_item`
Добавить позицию в пакет.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| package_id | number | да | ID пакета |
| item_id | number | да | ID товара/услуги |
| count | number | да | Количество |
| price | number | да | Цена |
| vat | number | - | НДС (%) |

### `finolog_update_package_item`
Обновить позицию.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| package_id | number | да | ID пакета |
| package_item_id | number | да | ID позиции |
| count | number | - | Количество |
| price | number | - | Цена |
| vat | number | - | НДС |

### `finolog_delete_package_item`
Удалить позицию. Параметры: `biz_id`, `package_id`, `package_item_id` (обяз.)

---

## Comment (2 tools)

### `finolog_list_comments`
Список комментариев.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| model_type | string | - | Тип объекта |
| model_id | number | - | ID объекта |
| type | string | - | Тип комментария |
| page | number | - | Страница |
| per_page | number | - | На странице |

### `finolog_create_comment`
Добавить комментарий.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| biz_id | number | да | ID бизнеса |
| model_type | string | да | Тип объекта |
| model_id | number | да | ID объекта |
| text | string | да | Текст |
| files | string[] | - | Файлы |

---

## Currency (1 tool)

### `finolog_list_currencies`
Справочник валют. Без параметров.

---

## Unit (1 tool)

### `finolog_list_units`
Справочник единиц измерения. Без параметров.

---

## User (2 tools)

### `finolog_get_user`
Текущий пользователь. Без параметров.

### `finolog_update_user`
Обновить профиль.

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| first_name | string | - | Имя |
| last_name | string | - | Фамилия |
