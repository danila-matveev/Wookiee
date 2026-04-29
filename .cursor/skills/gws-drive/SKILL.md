---
name: gws-drive
description: "Google Drive через gws CLI: загрузка, скачивание, управление файлами и папками. Используй этот скилл при работе с Google Диском — загрузка файлов, поиск файлов, создание папок, управление доступом. Срабатывает на: Google Drive, Google Диск, gws drive, загрузить на диск, файлы Google."
---

# Google Drive через gws

> Базовые флаги и auth — см. скилл `gws`

## Быстрые команды (хелперы)

### +upload — Загрузка файла

```bash
gws drive +upload <file> [--parent FOLDER_ID] [--name 'Имя файла']
```

| Флаг | Обязательный | Описание |
|------|-------------|----------|
| `<file>` | да | Путь к файлу |
| `--parent` | — | ID папки назначения |
| `--name` | — | Имя файла (по умолчанию — из пути) |

> WRITE-операция — подтвердить у пользователя перед выполнением!

Примеры:

```bash
gws drive +upload ./report.pdf
gws drive +upload ./data.csv --parent FOLDER_ID --name 'Sales Data.csv'
```

## Полный API

```bash
gws drive <resource> <method> [flags]
```

### Основные ресурсы

- `files` — list, get, create, copy, update, delete, download
- `permissions` — create, list, get, update, delete
- `drives` — list, get, create (shared drives)

### Discovery

```bash
gws drive --help
gws schema drive.files.list
```

### Частые операции

```bash
# Список файлов (последние 10)
gws drive files list --params '{"pageSize": 10}'

# Поиск по имени
gws drive files list --params '{"q": "name contains '\''report'\''", "pageSize": 10}'

# Поиск по типу (только таблицы)
gws drive files list --params '{"q": "mimeType='\''application/vnd.google-apps.spreadsheet'\''", "pageSize": 10}'

# Скачать файл
gws drive files get --params '{"fileId": "FILE_ID", "alt": "media"}' -o ./output.pdf

# Создать папку
gws drive files create --json '{"name": "New Folder", "mimeType": "application/vnd.google-apps.folder"}'

# Загрузить файл в папку
gws drive files create \
  --json '{"name": "report.pdf", "parents": ["FOLDER_ID"]}' \
  --upload ./report.pdf

# Выдать доступ на чтение
gws drive permissions create \
  --params '{"fileId": "FILE_ID"}' \
  --json '{"role": "reader", "type": "user", "emailAddress": "user@example.com"}'

# Потоковая пагинация всех файлов
gws drive files list --params '{"pageSize": 100}' --page-all | jq -r '.files[].name'

# Информация о файле
gws drive files get --params '{"fileId": "FILE_ID", "fields": "id,name,mimeType,size,modifiedTime"}'
```