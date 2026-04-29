---
name: gws
description: "Google Workspace CLI (gws) — базовый справочник по аутентификации, синтаксису и глобальным флагам. Используй этот скилл когда нужно работать с Google Workspace API: Google Drive, Google Sheets, и любыми другими Google-сервисами через CLI. Также используй при упоминании gws, Google API, таблиц Google, Google диска."
---

# gws — Базовый справочник

## Установка

```bash
npm install -g @googleworkspace/cli
```

## Аутентификация

```bash
gws auth login              # OAuth (интерактивно)
gws auth login -s drive,sheets  # только нужные скоупы
gws auth status             # проверить статус
```

## Синтаксис CLI

```bash
gws <service> <resource> <method> [flags]
```

### Флаги методов

| Флаг | Описание |
|------|----------|
| `--params '{"key": "val"}'` | URL/query-параметры |
| `--json '{"key": "val"}'` | Тело запроса |
| `-o, --output <PATH>` | Сохранить бинарный ответ |
| `--upload <PATH>` | Загрузить файл (multipart) |
| `--page-all` | Автопагинация (NDJSON) |
| `--page-limit <N>` | Макс. страниц (default: 10) |
| `--page-delay <MS>` | Задержка между страницами (default: 100) |
| `--dry-run` | Предпросмотр без вызова API |
| `--format <FORMAT>` | json (default), table, yaml, csv |

## Discovery — как узнать команды

```bash
gws --help                                # список сервисов
gws <service> --help                      # ресурсы и методы
gws schema <service>.<resource>.<method>  # схема запроса/ответа
```

Перед вызовом незнакомого метода всегда используй `gws schema` чтобы узнать обязательные параметры и типы.

## Правила безопасности

- Никогда не выводить токены и секреты в ответ пользователю
- Перед write/delete операциями — подтверждение у пользователя
- Для деструктивных операций сначала `--dry-run`
- Для Sheets: диапазоны с `!` оборачивать в одинарные кавычки (`'Sheet1!A1:C10'`)
