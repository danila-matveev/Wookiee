# /finolog-dds-report — ДДС отчёт из Finolog

**Запуск:** `/finolog-dds-report`

## Что делает

Формирует отчёт ДДС (движение денежных средств) из данных Finolog: поступления, расходы, остатки по счетам. Анализирует cash flow vs плановые операции (не абсолютные остатки).

## Параметры

- `period` — период (по умолчанию: текущий месяц)
- `account` — счёт/юрлицо для фильтрации (опционально)

## Результат

Отчёт публикуется в Notion и выводится в stdout.

## Зависимости

- Finolog API (`FINOLOG_API_KEY`)
- Notion API (`NOTION_TOKEN`)
- `shared/clients/finolog.py`
