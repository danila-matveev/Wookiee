# Ozon MCP Server

MCP-сервер для интеграции с [Ozon Seller API](https://docs.ozon.ru/api/seller/) — маркетплейса Ozon. Покрывает товары, заказы FBS/FBO, финансы, аналитику, цены, склады, возвраты, акции, чаты и другие разделы API.

**Репозиторий:** [github.com/danila-matveev/ozon-mcp-server](https://github.com/danila-matveev/ozon-mcp-server)

## Установка

```bash
git clone https://github.com/danila-matveev/ozon-mcp-server.git
cd ozon-mcp-server
npm install
npm run build
```

## Настройка

Создайте `.env`:

```env
OZON_CLIENT_ID=<ваш Client-Id>
OZON_API_KEY=<ваш Api-Key>

# Опционально — второй аккаунт (ООО)
OZON_CLIENT_ID_OOO=<Client-Id ООО>
OZON_API_KEY_OOO=<Api-Key ООО>

MCP_TRANSPORT=stdio    # stdio (по умолчанию) или http
MCP_PORT=8082          # порт для HTTP транспорта
LOG_LEVEL=info
```

Ключи получите в [личном кабинете Ozon](https://seller.ozon.ru/app/settings/api-keys).

## Подключение к Claude Code

В `.mcp.json` вашего проекта:

```json
{
  "mcpServers": {
    "ozon": {
      "type": "stdio",
      "command": "node",
      "args": ["/path/to/ozon-mcp-server/dist/index.js"],
      "env": {
        "OZON_CLIENT_ID": "<your-client-id>",
        "OZON_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

## Мульти-аккаунт

Каждый инструмент поддерживает параметр `account`:
- `"ip"` (по умолчанию) — аккаунт ИП
- `"ooo"` — аккаунт ООО

Пример: `{ "limit": 10, "account": "ooo" }`

## Категории инструментов

| Категория | Tools | Описание |
|-----------|-------|----------|
| product | 24 | Загрузка, обновление и управление товарами |
| fbs | 26 | Обработка заказов FBS и rFBS |
| fbo | 3 | Управление заказами FBO |
| supply_order | 13 | Управление заявками на поставку FBO |
| supply_draft | 8 | Черновики поставок FBO |
| delivery_fbs | 17 | Методы доставки FBS и фрахт |
| delivery_rfbs | 7 | Управление доставкой rFBS |
| marks | 10 | Маркировка товаров FBS/rFBS |
| prices_stocks | 5 | Цены и остатки |
| finance | 12 | Финансовые отчёты и транзакции |
| analytics | 10 | Аналитика и отчёты |
| warehouse | 11 | Управление складами |
| category | 4 | Категории и атрибуты товаров |
| report | 7 | Генерация отчётов |
| chat | 8 | Чаты с покупателями |
| review | 7 | Отзывы на товары |
| promos | 8 | Акции и скидки |
| pricing_strategy | 12 | Ценовые стратегии |
| certification | 14 | Сертификаты качества |
| cancellation | 3 | Отмены заказов rFBS |
| returns_fbo | 2 | Возвраты FBO/FBS |
| returns_rfbs | 8 | Возвраты rFBS |
| return_giveout | 7 | Выдача возвратов по штрихкоду |
| pass | 7 | Пропуска на склад |
| barcode | 2 | Штрихкоды товаров |
| polygon | 2 | Зоны доставки (полигоны) |
| rating | 2 | Рейтинг продавца |
| brand | 1 | Сертификаты брендов |
| quant | 2 | Товары эконом-сегмента |
| digital | 3 | Цифровые товары |
| invoice | 4 | Счета-фактуры |
| seller | 1 | Информация о продавце |

**Всего: 250 инструментов в 32 категориях**

Полный справочник: [api-reference.md](api-reference.md)
