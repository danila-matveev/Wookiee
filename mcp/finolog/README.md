# Finolog MCP Server

MCP-сервер для интеграции с [Finolog API](https://finolog.ru) — сервисом финансового учёта. Покрывает бизнесы, счета, транзакции, контрагентов, документы, заказы, долги и справочники.

**Репозиторий:** [github.com/danila-matveev/finolog-mcp-server](https://github.com/danila-matveev/finolog-mcp-server)

## Установка

```bash
git clone https://github.com/danila-matveev/finolog-mcp-server.git
cd finolog-mcp-server
npm install
npm run build
```

## Настройка

Создайте `.env`:

```env
FINOLOG_API_TOKEN=<ваш API токен Finolog>
MCP_TRANSPORT=stdio    # stdio (по умолчанию) или http
MCP_PORT=8081          # порт для HTTP транспорта
LOG_LEVEL=info
```

Токен получите в Finolog: Настройки → API.

## Подключение к Claude Code

В `.mcp.json` вашего проекта:

```json
{
  "mcpServers": {
    "finolog": {
      "type": "stdio",
      "command": "node",
      "args": ["/path/to/finolog-mcp-server/dist/index.js"],
      "env": {
        "FINOLOG_API_TOKEN": "<your-token>"
      }
    }
  }
}
```

## Категории инструментов

| Категория | Tools | Описание |
|-----------|-------|----------|
| [Biz](#biz) | 5 | Бизнесы (организации) |
| [Account](#account) | 5 | Банковские счета |
| [Transaction](#transaction) | 8 | Транзакции ДДС, split |
| [Category](#category) | 5 | Категории ДДС (статьи) |
| [Contractor](#contractor) | 6 | Контрагенты, автоправила |
| [Company](#company) | 5 | Юридические лица |
| [Project](#project) | 5 | Проекты |
| [Requisite](#requisite) | 5 | Реквизиты контрагентов |
| [Debt](#debt) | 6 | Долги контрагентов |
| [Order](#order) | 6 | Заказы, статусы |
| [Document](#document) | 6 | Счета, накладные, PDF |
| [Item](#item) | 5 | Товары и услуги |
| [Package](#package) | 3 | Пакеты в заказах |
| [Package-Item](#package-item) | 3 | Позиции в пакетах |
| [Comment](#comment) | 2 | Комментарии к объектам |
| [Currency](#currency) | 1 | Справочник валют |
| [Unit](#unit) | 1 | Единицы измерения |
| [User](#user) | 2 | Профиль пользователя |
| **Итого** | **79** | |

## Biz

Управление бизнесами (организациями) в Finolog.

- `finolog_list_biz` — Список всех бизнесов
- `finolog_create_biz` — Создать бизнес (name, base_currency_id)
- `finolog_get_biz` — Получить по ID
- `finolog_update_biz` — Обновить
- `finolog_delete_biz` — Удалить

## Account

Банковские счета бизнеса.

- `finolog_list_accounts` — Список счетов
- `finolog_create_account` — Создать счёт (company_id, currency_id, name)
- `finolog_get_account` — Получить по ID
- `finolog_update_account` — Обновить
- `finolog_delete_account` — Удалить

## Transaction

Транзакции ДДС — основная сущность финансового учёта.

- `finolog_list_transactions` — Список с фильтрацией (дата, категория, контрагент, счёт, проект, тип, статус)
- `finolog_create_transaction` — Создать (date, value, from_id/to_id, category_id, contractor_id, project_id)
- `finolog_get_transaction` — Получить по ID
- `finolog_update_transaction` — Обновить
- `finolog_delete_transaction` — Удалить
- `finolog_split_transaction` — Разделить по категориям
- `finolog_update_split` — Обновить разделение
- `finolog_delete_split` — Отменить разделение

## Category

Категории ДДС (статьи доходов/расходов).

- `finolog_list_categories` — Список категорий
- `finolog_create_category` — Создать (name, type: in/out/inout, parent_id)
- `finolog_get_category` — Получить по ID
- `finolog_update_category` — Обновить
- `finolog_delete_category` — Удалить

## Contractor

Контрагенты и автоправила.

- `finolog_list_contractors` — Список (поиск по email, ИНН, query)
- `finolog_create_contractor` — Создать (name, email, phone, person)
- `finolog_get_contractor` — Получить по ID
- `finolog_update_contractor` — Обновить
- `finolog_delete_contractor` — Удалить
- `finolog_create_autoeditor` — Автоправило для контрагента

## Company

Юридические лица бизнеса.

- `finolog_list_companies` — Список
- `finolog_create_company` — Создать (name, full_name, phone, web, address)
- `finolog_get_company` — Получить по ID
- `finolog_update_company` — Обновить
- `finolog_delete_company` — Удалить

## Project

Проекты для аналитики по направлениям.

- `finolog_list_projects` — Список
- `finolog_create_project` — Создать (name, currency_id, status)
- `finolog_get_project` — Получить по ID
- `finolog_update_project` — Обновить
- `finolog_delete_project` — Удалить

## Requisite

Реквизиты контрагентов (ИНН, КПП, расчётный счёт).

- `finolog_list_requisites` — Список
- `finolog_create_requisite` — Создать (contractor_id, name, bank_name, bank_bik, inn, kpp, ogrn)
- `finolog_get_requisite` — Получить по ID
- `finolog_update_requisite` — Обновить
- `finolog_delete_requisite` — Удалить

## Debt

Долги контрагентов.

- `finolog_list_debts` — Список долгов контрагента
- `finolog_create_debt` — Создать (value, date, type: in/out, currency_id)
- `finolog_get_debt` — Получить по ID
- `finolog_update_debt` — Обновить
- `finolog_delete_debt` — Удалить
- `finolog_delete_debts_bulk` — Массовое удаление

## Order

Заказы (входящие/исходящие).

- `finolog_list_orders` — Список с фильтрацией (type, status, даты)
- `finolog_create_order` — Создать (type: in/out, seller_id, buyer_id)
- `finolog_get_order` — Получить по ID
- `finolog_update_order` — Обновить
- `finolog_delete_order` — Удалить
- `finolog_list_order_statuses` — Справочник статусов

## Document

Счета и накладные.

- `finolog_list_documents` — Список (kind: invoice/shipment)
- `finolog_create_document` — Создать
- `finolog_get_document` — Получить по ID
- `finolog_update_document` — Обновить
- `finolog_delete_document` — Удалить
- `finolog_get_document_pdf` — Скачать PDF

## Item

Товары и услуги.

- `finolog_list_items` — Список (поиск по query)
- `finolog_create_item` — Создать (name, price, currency_id, type: product/service)
- `finolog_get_item` — Получить по ID
- `finolog_update_item` — Обновить
- `finolog_delete_item` — Удалить

## Package

Пакеты в заказах (группировка позиций).

- `finolog_create_package` — Создать
- `finolog_update_package` — Обновить
- `finolog_delete_package` — Удалить

## Package-Item

Позиции в пакетах.

- `finolog_add_package_item` — Добавить позицию (item_id, count, price)
- `finolog_update_package_item` — Обновить
- `finolog_delete_package_item` — Удалить

## Comment

- `finolog_list_comments` — Список комментариев (model_type, model_id)
- `finolog_create_comment` — Добавить комментарий (text, files)

## Currency

- `finolog_list_currencies` — Справочник валют

## Unit

- `finolog_list_units` — Справочник единиц измерения

## User

- `finolog_get_user` — Текущий пользователь
- `finolog_update_user` — Обновить профиль (first_name, last_name)

## Техническая информация

- **Runtime:** Node.js 18+
- **Язык:** TypeScript 5.7+
- **MCP SDK:** @modelcontextprotocol/sdk ^1.0.4
- **HTTP клиент:** axios
- **Валидация:** Zod
- **Логирование:** Winston
- **API Base URL:** `https://api.finolog.ru`
- **Rate limiting:** 60 запросов/мин, retry с exponential backoff (макс. 3 попытки)
- **Timeout:** 30 сек (стандартный), 120 сек (загрузка файлов)
