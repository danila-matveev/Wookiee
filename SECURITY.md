# Безопасность проекта Wookiee Analytics

## Политика безопасности

**Главное правило:** Все секреты хранятся ТОЛЬКО в `.env`. Никогда не коммитить реальные значения API-ключей, паролей и токенов в git.

## Управление секретами

### Хранение конфиденциальных данных

- **`.env`** — git-ignored, содержит ВСЕ API-ключи, токены и пароли
- **`.env.example`** — шаблон с плейсхолдерами для новых участников команды
- **`services/sheets_sync/credentials/`** — git-ignored директория для Google Service Account JSON
- **`.cursorignore`** — защита от случайной утечки через AI-агенты и IDE

### Чтение конфигурации

Код читает секреты ТОЛЬКО через `shared/config.py`, который загружает `.env` при помощи `python-dotenv`.

```python
# Правильно
from shared.config import TELEGRAM_BOT_TOKEN

# Неправильно
token = "HARDCODED_TOKEN"  # НИКОГДА!
```

## Ротация ключей

### Процедура при подозрении на утечку

1. **Немедленно сменить ключ** в сервисе-провайдере (Telegram, WB API, OZON, и т.д.)
2. **Обновить `.env`** на всех серверах и локальных машинах разработчиков
3. **Если ключ попал в git-историю:**
   - Использовать [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/)
   - Force-push очищенной истории
   - Уведомить всех участников команды о необходимости `git clone` заново

### Плановая ротация

Рекомендуется менять критичные ключи (БД, Supabase service_role) каждые 90 дней.

## Supabase безопасность

### Row Level Security (RLS)

- **RLS включён** на ВСЕХ таблицах в production
- **Роль `anon`** — заблокирована (никакого публичного доступа)
- **Роль `authenticated`** — только SELECT на читаемых таблицах
- **Python-скрипты** через `postgres` (service_role) — RLS НЕ применяется, полный доступ

### Создание новых таблиц

При создании новой таблицы ОБЯЗАТЕЛЬНО:

```sql
ALTER TABLE your_table ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated read" ON your_table
  FOR SELECT TO authenticated
  USING (true);
```

Подробнее: `wookiee_sku_database/README.md`

## Типы секретов в проекте

| Секрет | Переменная в .env | Провайдер | Как ротировать |
|--------|-------------------|-----------|----------------|
| Telegram Bot Token | `TELEGRAM_TOKEN` | @BotFather | `/revoke` в BotFather, создать новый токен |
| Telegram Analytics Token | `TELEGRAM_ANALYTICS_TOKEN` | @BotFather | `/revoke` в BotFather, создать новый токен |
| WB API Key | `WB_API_KEY` | Личный кабинет WB | Сгенерировать новый в ЛК → API → Доступ |
| OZON Client ID/Secret | `OZON_CLIENT_ID`, `OZON_CLIENT_SECRET` | Seller Cabinet OZON | Сгенерировать новый в Seller API Settings |
| Claude API Key | `ANTHROPIC_API_KEY` | console.anthropic.com | Settings → API Keys → Revoke + Create New |
| z.ai API Key | `Z_AI_API_KEY` | z.ai dashboard | API Settings → Regenerate |
| Supabase URL/Keys | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard | Project Settings → API → Reset service_role |
| PostgreSQL Password | `DB_PASSWORD` | Supabase Dashboard | Database → Settings → Reset Password |
| Notion Integration Token | `NOTION_TOKEN` | notion.so/my-integrations | Regenerate Secret в интеграции |
| Bitrix Webhook | `BITRIX_WEBHOOK_URL` | Bitrix24 Settings | Удалить старый webhook, создать новый |
| Google Service Account | `credentials/service_account.json` | Google Cloud Console | IAM → Service Accounts → Keys → Delete + Create |
| МойСклад API Token | `MOYSKLAD_TOKEN` | МойСклад → Настройки → API | Удалить старый токен, создать новый |

## Контрольный список для разработчиков

- [ ] Проверить, что `.env` в `.gitignore`
- [ ] Проверить, что `credentials/` в `.gitignore`
- [ ] Использовать только `scripts/config.py` для чтения секретов
- [ ] Новые таблицы Supabase — включить RLS
- [ ] Перед коммитом: `git diff` для проверки отсутствия секретов
- [ ] При подозрении на утечку — немедленная ротация ключей
