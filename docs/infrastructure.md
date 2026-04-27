# Wookiee — Инфраструктура

## Два сервера

| Сервер | IP | Назначение | Доступ |
|---|---|---|---|
| **App Server** | `77.233.212.61` | Docker runtime, CI/CD, все контейнеры | SSH `timeweb`, полный контроль |
| **DB Server** | `89.23.119.253` | PostgreSQL с эталонными данными WB/OZON | TCP :6433, **только чтение** |

- **Деплоить** — только на App Server (`77.233.212.61`)
- **DB Server** — сторонний, управляется разработчиком БД. Мы подключаемся через `.env` (`DB_HOST`, `DB_PORT=6433`)

---

## App Server — подключение

```bash
ssh timeweb
```

Или напрямую:

```bash
ssh -i ~/.ssh/id_ed25519_timeweb root@77.233.212.61
```

## Характеристики

| Параметр | Значение |
|----------|----------|
| Провайдер | Timeweb Cloud (Amsterdam) |
| IP | `77.233.212.61` |
| ОС | Ubuntu |
| CPU | 2 vCPU |
| RAM | 2 GB |
| Диск | 40 GB NVMe |
| Docker | latest |
| Домен | `matveevdanila.com` (GoDaddy) |

## Запущенные контейнеры

| Контейнер | Назначение | Домен / порт |
|-----------|-----------|--------------|
| `n8n-docker-caddy-caddy-1` | Reverse proxy + автоматический SSL (Let's Encrypt) | порты 80, 443 |
| `n8n-docker-caddy-n8n-1` | N8N автоматизация | `n8n.matveevdanila.com` |
| `wookiee_cron` | Cron-диспетчер: `search_queries_sync` + `sync_sheets_to_supabase` | — |
| `wookiee_sheets_sync` | Sheets sync runner (`services.sheets_sync.control_panel`) | — |
| `wb-logistics-api` | FastAPI для WB localization расчётов | — |
| `wb_mcp_ip` | Wildberries MCP server (кабинет ИП) | — |
| `wb_mcp_ooo` | Wildberries MCP server (кабинет ООО) | — |
| `bitrix24_mcp` | Bitrix24 MCP server | — |

## Ключевые пути на сервере

| Путь | Назначение |
|------|-----------|
| `/home/danila/projects/wookiee/` | Основной проект (git clone) |
| `/home/danila/n8n-docker-caddy/caddy_config/Caddyfile` | Конфиг Caddy (reverse proxy) |
| `/home/danila/n8n-docker-caddy/docker-compose.yml` | Caddy + N8N compose |

## CI/CD

Деплой автоматизирован через **GitHub Actions** ([`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml)):

1. Push в `main` запускает CI ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml))
2. Deploy workflow стартует только после `CI == success` (или вручную через `workflow_dispatch`)
3. SSH на сервер через пользователя `deploy`
4. `git pull` → `docker compose build` → `docker compose up -d`
5. Проверка healthcheck-статусов

### Server is deploy-only — НЕ редактировать код на сервере

`/home/danila/projects/wookiee/` на app-сервере — это рабочая копия для деплоя, **не для разработки**. Любая правка кода:

```
локально → PR → merge в main → CI green → GH Actions deploy.yml → сервер
```

Если кто-то правит файлы прямо на сервере (`vim`, `nano`, ручной `git commit`), это создаёт drift — на сервере появляются сиротские коммиты или uncommitted-правки, а GH Actions deploy `git pull` падает на конфликтах. **Уже было** в апреле 2026 (см. backup-tag `backup/server-before-cleanup-2026-04-27`).

Защитные механизмы (все три на месте):

1. **Autopull cron** под `deploy` (`*/5 * * * *` → `scripts/server_autopull.sh`):
   - При drift `main` vs `origin/main` — hard-reset на origin/main + (если изменён код контейнеров) `docker compose up -d --build --remove-orphans`
   - При **dirty working tree** ничего не reset-ит, шлёт Telegram alert через `TELEGRAM_BOT_TOKEN`/`TELEGRAM_ALERT_CHAT_ID`
   - Логи: `logs/autopull/YYYY-MM.log`
2. **Pre-deploy guard** (`scripts/server_predeploy_check.sh`):
   - Валидирует `.env` (required vars), существование скриптов, syntax docker-compose, python compileall
   - Запускается из autopull перед `git reset` и (потенциально) из GH Actions deploy.yml перед `docker compose build`
3. **Git config `core.sharedRepository=group`** в `.git/config`: новые объекты создаются с group-write битом, чтобы и `deploy`, и `danila`, и (если когда-нибудь) `root` могли писать в `.git/objects/` без конфликтов permissions.

Cron-jobs (host-уровень):

| Что | Кто | Когда |
|---|---|---|
| `services/logistics_audit/etl/cron_tariff_collector.sh` | `deploy` | `0 8 * * *` (daily 08:00 UTC) |
| `scripts/server_autopull.sh` | `deploy` | `*/5 * * * *` (каждые 5 мин) |

Cron-jobs внутри контейнера `wookiee_cron` (см. `deploy/docker-compose.yml`):

| Что | Когда |
|---|---|
| `python scripts/run_search_queries_sync.py` | `0 10 * * 1` (понедельник 10:00 МСК) |
| `python scripts/sync_sheets_to_supabase.py --level all` | `0 6 * * *` (daily 06:00 МСК) |

### Ручной деплой (резервный)

```bash
ssh timeweb
cd /home/danila/projects/wookiee/deploy
bash deploy.sh --build
```

Или через autopull (имитация cron-вызова): `ssh timeweb 'sudo -u deploy /home/danila/projects/wookiee/scripts/server_autopull.sh'`.

### GitHub Secrets (Settings → Secrets → Actions)

| Secret | Описание |
|--------|----------|
| `DEPLOY_SSH_KEY` | Приватный ключ `/home/deploy/.ssh/deploy_key` |
| `DEPLOY_HOST` | `77.233.212.61` |
| `DEPLOY_USER` | `deploy` |

## Деплой нового проекта

### 1. Docker-конфиг

Каждый проект должен содержать `docker-compose.yml` с обязательной сетью:

```yaml
services:
  app:
    build: .
    container_name: my-app
    restart: unless-stopped
    networks:
      - n8n-docker-caddy_default

networks:
  n8n-docker-caddy_default:
    external: true
```

### 2. Залить и запустить

```bash
ssh timeweb "mkdir -p /home/danila/projects/my-app"
scp -r ./* timeweb:/home/danila/projects/my-app/
ssh timeweb "cd /home/danila/projects/my-app && docker compose up -d --build"
```

### 3. Добавить домен в Caddyfile

```caddy
my-app.matveevdanila.com {
    reverse_proxy my-app:80
}
```

Перезапустить Caddy:

```bash
ssh timeweb "cd /home/danila/n8n-docker-caddy && docker compose restart caddy"
```

### 4. DNS в GoDaddy

A-запись: `my-app` → `77.233.212.61`. SSL-сертификат Caddy получит автоматически.

## Правила

1. **Имя контейнера = имя в Caddyfile** — иначе проксирование не работает
2. **Сеть `n8n-docker-caddy_default`** — обязательна для всех контейнеров
3. **SSL автоматический** — Caddy сам получает Let's Encrypt сертификаты
4. **`.env` только на сервере** — никогда не коммитить в git
5. **`restart: unless-stopped`** — добавлять в каждый docker-compose

## Полезные команды

## Rollout Smoke Checklist

Рекомендуемая последовательность после деплоя:

1. `wookiee-cron`
2. `wb-logistics-api`

Проверки:

```bash
# health containers
docker ps --format "table {{.Names}}\t{{.Status}}"

# sheets sync runner smoke
python -m services.sheets_sync.runner --list
```

### Контейнеры

```bash
# Статус
ssh timeweb "docker ps"

# Логи
ssh timeweb "docker logs <container> --tail 50"

# Перезапуск
ssh timeweb "docker restart <container>"

# Ресурсы
ssh timeweb "docker stats --no-stream"
```

### Caddy

```bash
# Конфиг
ssh timeweb "cat /home/danila/n8n-docker-caddy/caddy_config/Caddyfile"

# Перезапуск
ssh timeweb "cd /home/danila/n8n-docker-caddy && docker compose restart caddy"

# Логи
ssh timeweb "docker logs n8n-docker-caddy-caddy-1 --tail 50"
```

### Мониторинг

```bash
# Место на диске
ssh timeweb "df -h"

# Docker-кэш
ssh timeweb "docker system df"
```

---

## DB Server (read-only)

| Параметр | Значение |
|----------|----------|
| IP | `89.23.119.253` |
| Порт | `6433` |
| Базы | `pbi_wb_wookiee`, `pbi_ozon_wookiee` |
| Доступ | **Только чтение** |
| Владелец | Сторонний разработчик БД |

Подключение задаётся в `.env`:

```
DB_HOST=89.23.119.253
DB_PORT=6433
```

На этот сервер **ничего не деплоится**. Он используется как источник данных для аналитики (скиллы, Sheets Sync, ETL).
