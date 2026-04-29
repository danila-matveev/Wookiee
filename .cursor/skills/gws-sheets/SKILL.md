---
name: gws-sheets
description: "Google Sheets через gws CLI: чтение, запись, создание таблиц. Используй этот скилл при любой работе с Google Таблицами — чтение данных, добавление строк, создание spreadsheet, работа с ячейками и диапазонами. Срабатывает на: Google Sheets, Google Таблицы, spreadsheet, gws sheets, таблица Google."
---

# Google Sheets через gws

> Базовые флаги и auth — см. скилл `gws`

## Быстрые команды (хелперы)

### +read — Чтение данных

```bash
gws sheets +read --spreadsheet <ID> --range <RANGE>
```

| Флаг | Обязательный | Описание |
|------|-------------|----------|
| `--spreadsheet` | да | ID таблицы |
| `--range` | да | Диапазон (напр. `'Sheet1!A1:D10'`) |

Примеры:

```bash
gws sheets +read --spreadsheet 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms --range 'Sheet1!A1:D10'
gws sheets +read --spreadsheet 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms --range Sheet1
```

### +append — Добавление строк

```bash
gws sheets +append --spreadsheet <ID>
```

| Флаг | Обязательный | Описание |
|------|-------------|----------|
| `--spreadsheet` | да | ID таблицы |
| `--values` | — | Через запятую: `'Alice,100,true'` |
| `--json-values` | — | JSON массив: `'[["a","b"],["c","d"]]'` |

> WRITE-операция — подтвердить у пользователя перед выполнением!

Примеры:

```bash
gws sheets +append --spreadsheet ID --values 'Alice,100,true'
gws sheets +append --spreadsheet ID --json-values '[["a","b"],["c","d"]]'
```

## Полный API

```bash
gws sheets <resource> <method> [flags]
```

### Ресурсы

- `spreadsheets` — create, get, batchUpdate
- `spreadsheets.values` — get, update, append, batchGet, batchUpdate, clear
- `spreadsheets.sheets` — copyTo

### Discovery

```bash
gws sheets --help
gws schema sheets.spreadsheets.values.get
```

### Примеры через полный API

```bash
# Прочитать диапазон
gws sheets spreadsheets values get \
  --params '{"spreadsheetId": "ID", "range": "Sheet1!A1:C10"}'

# Записать значения
gws sheets spreadsheets values update \
  --params '{"spreadsheetId": "ID", "range": "Sheet1!A1", "valueInputOption": "USER_ENTERED"}' \
  --json '{"values": [["Name", "Score"], ["Alice", 95]]}'

# Добавить строки (через API)
gws sheets spreadsheets values append \
  --params '{"spreadsheetId": "ID", "range": "Sheet1!A1", "valueInputOption": "USER_ENTERED"}' \
  --json '{"values": [["Bob", 87]]}'

# Создать таблицу
gws sheets spreadsheets create --json '{"properties": {"title": "New Sheet"}}'

# Прочитать несколько диапазонов за раз
gws sheets spreadsheets values batchGet \
  --params '{"spreadsheetId": "ID", "ranges": ["Sheet1!A1:B5", "Sheet2!A1:C3"]}'
```

## Заметка для Wookiee

В проекте уже есть `services/sheets_sync/` для автоматической синхронизации данных.
gws CLI — для ad-hoc операций: быстрое чтение, ручное добавление данных, создание новых таблиц.
