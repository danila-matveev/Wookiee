# Саймон — operator runbook

**Назначение:** пошаговая шпаргалка для оператора (Данилы) после того как
все 7 PR-ов смержены в `main`. Описывает порядок включения каждой фичи,
куда смотреть на алерты, что выключать когда что-то идёт не так, где брать
метрики качества и что делать когда OAuth-токен Telemost истекает.

Ничего, что описано здесь, **не нужно делать на этапе ревью PR** — это
сценарий для production включения. Все флаги дефолтят в `false`, поэтому
до сознательного включения Саймон молчит.

---

## 0. Map of feature flags

| Env var                          | Что включает                                              | Default | Где задан        |
|----------------------------------|-----------------------------------------------------------|---------|------------------|
| `TELEMOST_BOT_NAME`              | Имя бота в текстах /start, /help, саммари                 | (нет)   | `.env` на сервере |
| `TELEMOST_SCHEDULER_ENABLED`     | Авто-постановка встреч в очередь из Bitrix-календаря      | `false` | `.env`           |
| `MORNING_DIGEST_ENABLED`         | Утренний дайджест 09:00 МСК в DM каждому юзеру            | `false` | `.env`           |
| `VOICE_TRIGGERS_ENABLED`         | Детекция «Саймон, ...» + рендер секций в саммари + Phase 2 кнопки | `false` | `.env`   |

Все остальные настройки (`YANDEX_TELEMOST_*`, `BITRIX24_WEBHOOK_URL`,
`TELEMOST_SCHEDULER_TICK_SECONDS`, `MORNING_DIGEST_HOUR_MSK` etc.) уже стоят
в `.env` и менять их в штатном режиме не нужно.

---

## 1. Порядок включения (день 0 → день 10)

Между шагами оставляем смысловую паузу — посмотреть что новая фича не
ломает старое, прежде чем включать следующую.

### День 0 — после merge T1 (rename)

1. Положить квадратную и прямоугольную PNG-аватарки в `data/branding/`
   (имена файлов есть в `data/branding/README.md`).
2. @BotFather → `/setname` → «Саймон» для `@wookiee_recorder_bot`.
3. @BotFather → `/setdescription` → текст из SPEC §4.1.
4. @BotFather → `/setuserpic` → загрузить квадратную PNG.
5. admin.yandex.ru → `recorder@wookiee.shop` → переименовать профиль в
   «Саймон», загрузить прямоугольную PNG.
6. На сервере: добавить в `.env` строку `TELEMOST_BOT_NAME=Саймон`.
7. `docker compose restart telemost-recorder-api`.

После этого в /start и /help должен показываться «Саймон». Запись и
саммари — без изменений.

### День 1 — после merge T2 (Yandex wrapper) + T3 (OAuth health)

OAuth-переменные `YANDEX_TELEMOST_*` уже в `.env` (см. SPEC §3.1). Контейнер
`wookiee_cron` нужно пересоздать, чтобы он их подхватил:

```bash
docker compose up -d wookiee-cron   # без --build
```

Smoke: ручной запуск чек-скрипта:

```bash
docker exec wookiee_cron python3 -m scripts.telemost_check_cookies --once
```

В Telegram должен прийти алерт «OAuth: OK» (или сразу первое предупреждение
если токен близко к истечению).

### День 2 — после merge T4 (scheduler multi-user)

1. На сервере: убедиться что в `.env` НЕТ `TELEMOST_SCHEDULER_BITRIX_USER_ID`
   и `TELEMOST_SCHEDULER_TELEGRAM_ID` (legacy single-user перебивает multi-user).
2. Поставить `TELEMOST_SCHEDULER_ENABLED=true` в `.env`.
3. `docker compose restart telemost-recorder-api`.
4. Подождать 5 минут, проверить логи — должны идти строки
   `scheduler tick processed N users` без exceptions.
5. **Сразу выключить обратно** (`TELEMOST_SCHEDULER_ENABLED=false` + restart),
   пока не сделан T5 (дайджест). Иначе Саймон начнёт записывать встречи без
   предупреждения юзеров.

### День 3 — после merge T5 (morning digest)

1. `MORNING_DIGEST_ENABLED=true` в `.env`.
2. `docker compose restart telemost-recorder-api`.
3. На следующее утро в 09:00 МСК проверить что в `@wookiee_alerts_bot` нет
   ошибок и что один-два юзера получили DM (если их попросить).

### День 4 — включить scheduler постоянно

1. `TELEMOST_SCHEDULER_ENABLED=true`.
2. `docker compose restart telemost-recorder-api`.
3. Smoke-watch — открыть телеграм-бот, попросить кого-то из команды
   подключиться к ближайшей встрече с Telemost-ссылкой, убедиться что
   Саймон зашёл и записал.

### Дни 5-7 — после merge T6 (voice Phase 1)

1. `VOICE_TRIGGERS_ENABLED=true`.
2. `docker compose restart telemost-recorder-api`.
3. На 5–10 встречах в неделю собрать ручную выборку precision / recall.
   Записать в `docs/projects/saimon/PHASE1_METRICS.md` (создашь сам).
4. Если precision < 0.7 — выключить обратно, поправить промпт в
   `services/telemost_recorder_api/voice_triggers.py`, релизнуть фикс.

### День 8 — после merge T7 (этот PR)

1. Применить миграцию 006 руками:

   ```bash
   PGPASSWORD="$SUPABASE_PASSWORD" psql \
     -h "$SUPABASE_HOST" -p "$SUPABASE_PORT" -U "$SUPABASE_USER" \
     -d "$SUPABASE_DB" \
     -f services/telemost_recorder_api/migrations/006_voice_trigger_candidates.sql
   ```

   Проверка:
   ```sql
   SELECT to_regclass('telemost.voice_trigger_candidates');
   -- ожидаем: telemost.voice_trigger_candidates
   ```

2. `docker compose restart telemost-recorder-api` (чтобы подтянулись новые
   обработчики).

3. Никаких новых env-флагов не нужно — Phase 2 активируется тем же
   `VOICE_TRIGGERS_ENABLED=true`, что и Phase 1. Просто на следующей записи
   с голосовыми триггерами кнопки «✅ Создать» начнут реально создавать
   задачи в Bitrix.

### День 10 — финальный smoke

Записать тестовую встречу с фразой «Саймон, поставь задачу [имя из команды]
сделать [что-то] к пятнице», подождать саммари в Telegram, нажать
«✅ Создать», убедиться что задача появилась в Bitrix24.

---

## 2. Куда смотреть на алерты

Все системные оповещения идут в Telegram-канал `@wookiee_alerts_bot`
(токен: `TELEGRAM_ALERTS_BOT_TOKEN`, chat: `TELEGRAM_ALERTS_CHAT_ID`).

| Что | Когда | Что увидишь в чате |
|-----|-------|--------------------|
| Куки Yandex 360 | Daily 08:00 МСК | «Куки истекают через X дней» / «OK» |
| OAuth Telemost  | Daily 08:00 МСК | «OAuth: OK» / «обновлён» / «check failed» |
| scheduler_worker упал | при exception в `run_forever` | стектрейс через `error_alerts.py` |
| postprocess_worker упал | при exception | стектрейс |
| morning_digest упал | при exception | стектрейс |
| recorder crashed | docker exit !=0 | сообщение от docker hook |

Все скриптовые логи в `docker compose logs telemost-recorder-api --tail 200`.

---

## 3. Откат — какой флаг что выключает

| Симптом | Что выключить | Команда |
|---------|---------------|---------|
| Саймон записывает чужие встречи или ненужные | `TELEMOST_SCHEDULER_ENABLED=false` | restart api |
| Утренние дайджесты идут слишком часто / не тем | `MORNING_DIGEST_ENABLED=false` | restart api |
| Voice-triggers галлюцинируют, плодят ложные секции | `VOICE_TRIGGERS_ENABLED=false` | restart api |
| Бот вообще сломался, не отвечает | `docker compose restart telemost-recorder-api` (если не помогло — `docker compose stop telemost-recorder-api` и разобраться по логам) | — |
| Phase 2 кнопки создают задачи с мусорными полями | `VOICE_TRIGGERS_ENABLED=false` (выключает и Phase 1, и Phase 2 одной кнопкой) | restart api |
| Конкретный юзер не должен записываться | Поставь `is_active=false` в `telemost.users` для его `telegram_id` | SQL |

После любого rollback — расскажи команде в общем чате, что Саймон
временно тише, чтобы не ждали саммари.

---

## 4. Метрики Phase 1 / Phase 2

### Voice-trigger precision (Phase 1)

«Из всех показанных кандидатов сколько % были валидными.»

Считается вручную: после каждой встречи смотришь в саммари секции
🔖 / 📌 / 📅 / 🔔 / 📝, помечаешь для каждого пункта `valid` / `invalid`,
складываешь. Цель ≥ 0.7. Записывай в `docs/projects/saimon/PHASE1_METRICS.md`.

### Voice-trigger recall

«Из всех команд `Саймон, ...` сколько % мы поймали.»

Меряем по выборке: раз в неделю послушай 1 записанную встречу руками и
сравни с тем что Саймон вычленил. Точная цифра не критична, но если
recall заметно ниже 0.8 — добавлять варианты ASR-имени в Stage 1 промт.

### Phase 2 conversion

«Из всех показанных кнопок ✅ Создать сколько нажато.» Считается одним SQL:

```sql
SELECT
  status,
  COUNT(*) AS n
FROM telemost.voice_trigger_candidates
WHERE created_at > now() - interval '7 days'
GROUP BY status;
```

Целевая воронка:
- pending → < 10% (юзер не отреагировал)
- created → > 50% (нажал ✅)
- ignored → < 30% (нажал ❌)
- edited  → ≈ 0% (Phase 2 — placeholder, реальная правка через Bitrix)

---

## 5. OAuth Telemost — что делать при refresh-алерте

Когда придёт сообщение вида:

```
Telemost OAuth обновлён. Перезапиши в .env:
YANDEX_TELEMOST_OAUTH_TOKEN=abcdef12...
YANDEX_TELEMOST_REFRESH_TOKEN=xyz98765...
```

1. Открой `.env` на сервере (`ssh timeweb`, потом `nano /home/danila/projects/wookiee/.env`).
2. Замени `YANDEX_TELEMOST_OAUTH_TOKEN` и `YANDEX_TELEMOST_REFRESH_TOKEN`
   на новые значения из алерта.
3. `docker compose up -d telemost-recorder-api wookiee-cron`
   (без `--build`, чтобы контейнеры пересоздались и подтянули новые env).
4. Проверь что следующий tick health-check шлёт «OAuth: OK».

Auto-update `.env` намеренно не сделан в Phase 2 — это отдельный backlog
(требует прав на запись в `.env` из контейнера + atomic recreate).

---

## 6. Сценарии частых разборов

### «Саймон пришёл на встречу с внешним участником без согласия»

- Если разовый случай: положи `#nobot` в название встречи в Bitrix
  на будущее. Удали запись через кнопку «🗑 Удалить» под саммари в DM.
- Если это паттерн (приходит на любую встречу с клиентами): обсуди с
  командой и в Bitrix-календаре договоритесь о тегировании внешних встреч.
- Аварийный отключатель: `TELEMOST_SCHEDULER_ENABLED=false`.

### «Кнопка ✅ Создать ничего не сделала»

1. Проверь `docker compose logs telemost-recorder-api --tail 100` —
   ищи строки `voice_actions: create_task failed`.
2. Если видно `BitrixWriteError: WRONG_RESPONSIBLE_ID` — значит LLM не
   распознал имя. Создай задачу руками через `/bitrix-task`.
3. Если видно `httpx.TimeoutException` — Bitrix-вебхук под нагрузкой,
   повтори через минуту.

### «Кандидат в БД но кнопок в Telegram нет»

Это значит persistence упала на конкретной записи. Юзер увидел legacy
placeholder («Phase 2 не активирован»). Найди кандидат вручную:

```sql
SELECT id, intent, speaker, raw_text, status, created_at
FROM telemost.voice_trigger_candidates
WHERE meeting_id = '<UUID-встречи>'
ORDER BY created_at DESC;
```

Если строки нет вообще — смотри логи `_persist_candidates` в API. Обычно
это connection issue к Supabase.

---

## 7. Будущее (что НЕ в этой раскатке)

- Inline-форма для правки полей задачи перед созданием (Phase 2 это
  placeholder; реальный flow — backlog).
- Real-time голосовые ответы Саймона в звонке.
- Multi-tenant (другие Yandex 360 организации).
- Auto-update `.env` после OAuth refresh.

Все эти пункты — out-of-scope, см. SPEC §8.
