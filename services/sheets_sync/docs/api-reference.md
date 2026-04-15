# API Reference — Внешние API синхронизации

Справочник по всем внешним API, используемым в системе синхронизации с Google Sheets.

---

## WB (Wildberries)

### Аутентификация

Все запросы к WB API используют заголовок:

```
Authorization: {API_KEY}
```

API-ключи хранятся в `shared/config.py` отдельно для каждого кабинета (ИП и ООО).

---

### 1. Warehouse Remains — Остатки на складах

Асинхронный отчёт. Работает в три этапа: создание задачи → опрос статуса → скачивание результата.

**Шаг 1. Создание задачи**

```
GET seller-analytics-api.wildberries.ru/api/v1/warehouse_remains
    ?groupByBarcode=true
    &groupByBrand=true
    &groupBySubject=true
    &groupBySa=true
    &groupByNm=true
    &groupBySize=true
```

Возвращает `taskId`.

**Шаг 2. Опрос статуса задачи**

```
GET seller-analytics-api.wildberries.ru/api/v1/warehouse_remains/tasks/{taskId}/status
```

- Опрашивать каждые **15 секунд**
- Максимум **100 попыток**
- Ожидать статус `"done"`

**Шаг 3. Скачивание результата**

```
GET seller-analytics-api.wildberries.ru/api/v1/warehouse_remains/tasks/{taskId}/download
```

- Ждать **60 секунд** после получения статуса `"done"` перед скачиванием
- Возвращает JSON-массив с остатками по всем складам

---

### 2. Prices — Цены и скидки

Пагинированный запрос. Страницы запрашиваются до тех пор, пока не придёт пустой список.

```
GET discounts-prices-api.wildberries.ru/api/v2/list/goods/filter
    ?limit=1000
    &offset={offset}
```

- `limit`: максимум 1000 записей на страницу
- `offset`: сдвиг (0, 1000, 2000, ...)
- Итерировать до пустого ответа

---

### 3. Feedbacks — Отзывы

Пагинированный запрос. Запрашиваются отдельно отвеченные и неотвеченные отзывы.

```
GET feedbacks-api.wildberries.ru/api/v1/feedbacks
    ?isAnswered={true|false}
    &take=5000
    &skip={offset}
```

- `isAnswered`: `true` — отвеченные, `false` — новые
- `take`: максимум 5000 за запрос
- `skip`: сдвиг для пагинации

---

### 4. Search Analytics — Аналитика поиска

```
POST {WB_SEARCH_REPORT_API_URL}
Content-Type: application/json
Authorization: {API_KEY}
```

Тело запроса включает: диапазон дат, список `nmIds`, параметры лимита.

**Лимиты по кабинетам:**

| Кабинет | Лимит nmIds за запрос |
|---------|----------------------|
| ООО | 100 |
| ИП | 30 |

---

### Обработка ошибок WB

| Код | Действие |
|-----|----------|
| `429` | Ждать **60 секунд**, повторить запрос |
| Другие ошибки | Повторить **3 раза** с экспоненциальной задержкой |

---

## Ozon

### Аутентификация

Все запросы к Ozon API используют заголовки:

```
Client-Id: {CLIENT_ID}
Api-Key: {API_KEY}
```

Значения хранятся в `shared/config.py` отдельно для ИП и ООО.

---

### 1. Products Report — Отчёт по товарам

Асинхронный отчёт. Работает в два этапа: создание → опрос → скачивание CSV.

**Шаг 1. Создание отчёта**

```
POST api-seller.ozon.ru/v1/report/products/create
Content-Type: application/json

{
    "sku": [...],
    "language": "DEFAULT",
    "visibility": "ALL"
}
```

- Максимум **1000 SKU** за один запрос
- При большем количестве — разбивать на батчи по 1000

Возвращает `code` отчёта.

**Шаг 2. Опрос статуса**

```
POST api-seller.ozon.ru/v1/report/info
Content-Type: application/json

{
    "code": "{report_code}"
}
```

- Опрашивать каждые **5 секунд**
- Максимум **12 попыток**
- Ожидать статус `"success"`

**Шаг 3. Скачивание CSV**

После успешного статуса в ответе возвращается URL файла. Скачать CSV по этому URL.

**Задержки:**

- **5 секунд** между попытками опроса статуса
- **2 секунды** между батчами при большом количестве SKU

---

## МойСклад

### Аутентификация

```
Authorization: Bearer {TOKEN}
Accept-Encoding: gzip
```

Токен хранится в `shared/config.py`.

---

### 1. Assortment — Ассортимент

Пагинированный запрос для получения всего ассортимента товаров с остатками на указанный момент.

```
GET api.moysklad.ru/api/remap/1.2/entity/assortment
    ?limit=500
    &offset={offset}
    &filter=stockMoment={date}
```

- `limit`: максимум 500 записей на страницу
- `offset`: сдвиг (0, 500, 1000, ...)
- `stockMoment`: дата/время для расчёта остатков в формате ISO 8601
- Итерировать до пустого ответа

---

### 2. Stock All — Остатки (все склады)

Используется для получения данных о себестоимости.

```
GET api.moysklad.ru/api/remap/1.2/report/stock/all
```

Возвращает текущие остатки по всем складам с ценами закупки.

---

### 3. Purchase Orders — Заказы поставщикам

Двухэтапный запрос: сначала список заказов, затем позиции каждого заказа.

**Список заказов:**

```
GET api.moysklad.ru/api/remap/1.2/entity/purchaseorder
```

**Позиции заказа:**

```
GET api.moysklad.ru/api/remap/1.2/entity/purchaseorder/{id}/positions
```

---

### Задержки МойСклад

| Между запросами | Задержка |
|-----------------|----------|
| Между страницами пагинации | 0.3–0.5 секунды |

---

## Сводная таблица rate limits

| API | Ограничение | Действие при превышении |
|-----|-------------|------------------------|
| WB (все эндпоинты) | Rate limit | 429 → ждать 60с, повторить |
| WB (все эндпоинты) | Другие ошибки | Повторить 3 раза |
| Ozon Products Report | 1000 SKU/батч | Разбивать на батчи |
| Ozon (опрос статуса) | — | 5с между попытками, макс. 12 |
| Ozon (батчи) | — | 2с между батчами |
| МойСклад (пагинация) | — | 0.3–0.5с между страницами |
