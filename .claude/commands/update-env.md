# Обновить .env на сервере

Синхронизируй локальный `.env` с серверным (`/home/danila/projects/wookiee/.env` на `timeweb`).

`$ARGUMENTS` — опциональные флаги: `--dry-run` (только показать diff), `--force` (без подтверждения), `--no-validate` (пропустить compose/predeploy проверки), `--recreate <service>` (после синка пересоздать указанный контейнер).

## Когда использовать

- Изменил локальный `/Users/danilamatveev/Projects/Wookiee/.env` (новый ключ, обновил токен, добавил переменную) и хочешь чтобы прод тоже это получил.
- Не уверен что локальный и серверный `.env` синхронны — `--dry-run` покажет расхождения.

## Шаги

1. **Sanity-check**: проверь что локальный `.env` существует и не пустой:
   ```bash
   stat -c "%s %y" /Users/danilamatveev/Projects/Wookiee/.env
   ```

2. **Запусти синк** через [scripts/sync_env_to_server.sh](scripts/sync_env_to_server.sh):
   ```bash
   bash /Users/danilamatveev/Projects/Wookiee/scripts/sync_env_to_server.sh $ARGUMENTS
   ```

   Что делает скрипт:
   - читает серверный `.env` через ssh, сравнивает с локальным на уровне имён переменных (значения не печатает — безопасно для логов)
   - показывает добавления (`+`), удаления (`-`), перезапись значений (`~`)
   - просит подтверждение `[y/N]` (если не `--force`)
   - бэкапит серверный `.env` в `.env.bak.YYYYMMDD-HHMMSS`
   - заливает локальный через `scp`, сверяет byte-identity
   - валидирует `docker compose config -q` и `server_predeploy_check.sh`

3. **Если синк прошёл и пользователь менял живые переменные** (читаемые running контейнерами) — предложи пересоздать соответствующие сервисы. Контейнер читает `.env` только при старте, после синка нужен `--force-recreate`:

   ```bash
   ssh timeweb 'cd /home/danila/projects/wookiee/deploy && \
     docker compose up -d --force-recreate <service>'
   ```

   Сервисы и какие переменные они читают:

   | Сервис | Зависит от .env переменных |
   |---|---|
   | `sheets-sync` | `WB_API_KEY_*`, `OZON_*`, `SPREADSHEET_*`, `SUPABASE_*`, `SYNC_TEST_MODE` |
   | `wookiee-cron` | `WB_API_KEY_*`, `OZON_*`, `SUPABASE_*`, `TELEGRAM_*`, `OPENROUTER_API_KEY` |
   | `wb-mcp-ip` | `WB_API_KEY_IP` |
   | `wb-mcp-ooo` | `WB_API_KEY_OOO` |
   | `bitrix24-mcp` | `BITRIX24_WEBHOOK_URL`, `Bitrix_rest_api` |
   | `wb-logistics-api` | `VASILY_*`, `WB_LOGISTICS_API_KEY` |

   Если пользователь передал `--recreate <service>` — выполни пересоздание автоматически. Иначе спроси какие сервисы пересоздать (или «никакие» — если менялись только переменные, читаемые скриптами по требованию вроде `OPENROUTER_API_KEY` для агентов).

## Безопасность

- **Никогда** не печатай значения переменных в выводе. Скрипт показывает только имена.
- Если `git status` показывает `.env` как modified — это нормально, файл в `.gitignore` и не коммитится.
- Бэкап на сервере (`*.bak.*`) хранится бессрочно — можно откатить через `mv`.

## Если что-то пошло не так

- **scp failed**: проверь `ssh timeweb` — связь с сервером.
- **post-sync compare differs**: на сервере что-то изменило `.env` между нашими операциями. Откатись через `ssh timeweb 'mv /home/danila/projects/wookiee/.env.bak.<TS> /home/danila/projects/wookiee/.env'`.
- **predeploy guard failed**: посмотри какой `.env` var он требует, добавь его локально, запусти синк ещё раз.
