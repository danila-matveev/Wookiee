# Wookiee — Production-сервер

## Подключение

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

<details>
<summary>Старый сервер (DigitalOcean) — отключён</summary>

| Параметр | Значение |
|----------|----------|
| Провайдер | DigitalOcean Droplet |
| IP | `167.99.12.42` |
| SSH | `ssh supabase-server` |
| ОС | Ubuntu 22.04, kernel 5.15 |
| CPU | 1 vCPU |
| RAM | 2 GB |
| Диск | 34 GB |

</details>

## Запущенные контейнеры

| Контейнер | Назначение | Домен / порт |
|-----------|-----------|--------------|
| `n8n-docker-caddy-caddy-1` | Reverse proxy + автоматический SSL (Let's Encrypt) | порты 80, 443 |
| `n8n-docker-caddy-n8n-1` | N8N автоматизация | `n8n.matveevdanila.com` |
| `wookiee_analytics_agent` | Олег — финансовый AI-агент | — |
| `wookiee_analytics_bot` | Telegram-бот (UI для Олега) | — |
| `wookiee_sheets_sync` | Синхронизация Google Sheets | — |

Лендинг (`matveevdanila.com`) отдаётся Caddy как static file server из `/srv/landing`.

## Ключевые пути на сервере

| Путь | Назначение |
|------|-----------|
| `/home/danila/projects/wookiee/` | Основной проект (git clone) |
| `/home/danila/n8n-docker-caddy/caddy_config/Caddyfile` | Конфиг Caddy (reverse proxy) |
| `/home/danila/n8n-docker-caddy/docker-compose.yml` | Caddy + N8N compose |

## CI/CD

Деплой автоматизирован через **GitHub Actions** ([`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml)):

1. Push в `main` → GitHub Actions запускает workflow
2. SSH на сервер через пользователя `deploy`
3. `git pull` → `docker compose build` → `docker compose up -d`
4. Обновление лендинга в Caddy volume
5. Проверка healthcheck-статусов

### Ручной деплой (резервный)

```bash
ssh timeweb
cd /home/danila/projects/wookiee/deploy
bash deploy.sh --build
```

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
