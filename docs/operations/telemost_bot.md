# Telemost Recorder — operator runbook

Что делать с ботом-рекордером встреч в проде: ротация куки, диагностика падений, восстановление после деградации.

## Что это

Бот заходит в Telemost-встречи как **залогиненный сотрудник Yandex 360 Business** (`recorder@wookiee.shop`), пишет аудио, транскрибирует, шлёт саммари в Telegram + Notion. Архитектура — см. [services/telemost_recorder/README.md](../../services/telemost_recorder/README.md).

**Ключевой секрет:** Playwright `storage_state.json` (cookies + localStorage) залогиненного юзера. Лежит на сервере в `/opt/wookiee/secrets/telemost_storage_state.json` (perms 600, owner root). Маунтится readonly в API-контейнер и оттуда в каждый recorder-контейнер.

## Симптомы и что делать

### Бот не может записать встречи, falls back to гостю

**Признаки:** в Telegram-алертах `TELEMOST_STORAGE_STATE_PATH=... is set but file is missing — falling back to guest mode`. Или: бот заходит, но Telemost кикает его через 30-300 секунд (как было до PR #142).

**Что случилось:**
- Файл `telemost_storage_state.json` пропал/повредился на сервере, ИЛИ
- Куки внутри файла протухли (Yandex просит перелогиниться раз в ~60 дней)

**Что делать:** переэкспортировать куки. См. **«Ротация куки»** ниже.

### Бот не заходит в встречу: `UI_DETECTION_FAILED`

**Признаки:** в `data/telemost/<meeting_id>/unknown_state.png` бот сидит на каком-то экране, который наш FSM не распознал.

**Что делать:**
1. Скачать `unknown_state.png` себе, посмотреть что там
2. Если это новый pre-join экран — добавить новое состояние в `_STATE_SELECTORS` в [services/telemost_recorder/join.py](../../services/telemost_recorder/join.py), обработать в `_execute_join()`
3. Пример из истории: PR #143 — Yandex 360 показывает залогиненным юзерам экран без поля имени (только кнопка «Подключиться»), пришлось добавить `AUTH_PRE_JOIN` state

### Бот сам выходит из живой встречи через ~5 минут

**Признаки:** статус `MEETING_ENDED_DETECTED` через 5 минут, хотя встреча идёт.

**Что случилось:** `detect_meeting_ended()` сработал ложно-положительно. Скорее всего:
- Yandex изменил DOM, и `extract_participants()` или один из text-selectors срабатывает на не-финальной строке
- Или появился новый Telemost-оверлей со словом «Meeting ended» в дочернем элементе

**Что делать:**
1. Глянуть последние 2-3 скриншота — определить какое именно состояние UI триггернуло выход
2. Поправить селекторы в `detect_meeting_ended()` в [join.py](../../services/telemost_recorder/join.py)
3. Помнить: эта функция должна срабатывать ТОЛЬКО на однозначных сигналах. Если есть сомнения — лучше пропустить тик, защита от runaway записи в пустой комнате есть через `RECORDING_HARD_LIMIT_HOURS` (default 4ч)

История: в PR #144 убрали проверку через `extract_participants()` именно по этой причине — на Yandex 360 UI селекторы не находили имена и каждые 5 минут False-positive «никого нет → выйти».

### Контейнер recorder ушёл в SIGKILL / ffmpeg ругается

**Признаки:** Telegram-алерт `Recorder-контейнер упал на этапе записи (Playwright/Xvfb/PulseAudio)` + traceback с ffmpeg или PulseAudio.

**Что делать:**
1. `docker logs telemost_rec_<8chars>` — посмотреть последние строки
2. Проверить остаток места на диске: `df -h /home/danila/projects/wookiee/data`
3. Проверить остаточные PulseAudio sinks: `docker exec telemost_recorder_api pactl list sinks short` (на хосте PulseAudio не используется, всё в контейнерах)
4. Если просто эпизод — recorder_worker сам обработает фейл (запишет FAILED, отпустит семафор). Если повторяется — поднять issue с логами

## Ротация куки

Yandex требует перелогиниться раз в ~60 дней (точно не задокументировано, по факту — где-то так). Когда это случится, бот перестанет авторизоваться и будет заходить как гость (и сразу получать anti-bot кик).

### Когда обновлять

- Раз в **45 дней профилактически** (поставить в календарь)
- Сразу как только из Telegram-алертов придёт `falling back to guest mode` или серия кратких (< 5 мин) записей с anti-bot признаками
- После любой Yandex 360 пасс-операции (смена пароля, ребиндинг телефона)

### Как обновить

**На локальной машине** (Mac, где есть GUI):

```bash
cd ~/Projects/Wookiee
TELEMOST_LOGIN='recorder@wookiee.shop' \
  TELEMOST_PASSWORD='<пароль из пасс-менеджера>' \
  .venv/bin/python scripts/telemost_export_cookies.py
```

Что произойдёт:
1. Откроется видимый Chromium на твоём экране
2. Скрипт авто-вводит логин + пароль
3. **Если Yandex попросит капчу/SMS/привязку телефона** — реши прямо в этом окне. Скрипт ждёт до 7 минут.
4. Как только в куках появится `Session_id` — скрипт seedит куки на `telemost.yandex.ru` и сохраняет в `data/telemost_storage_state.json`
5. В конце печатается сводка (сколько cookies, есть ли Session_id) + готовая `scp` команда

**Загрузить на сервер:**

```bash
scp data/telemost_storage_state.json timeweb:/opt/wookiee/secrets/telemost_storage_state.json
ssh timeweb 'chmod 600 /opt/wookiee/secrets/telemost_storage_state.json'
```

**Перезапустить API-контейнер** чтобы он подхватил новый файл (mount readonly — содержимое перечитывается на старте каждого нового recorder-контейнера, но я бы рестартанул для чистоты):

```bash
ssh timeweb 'cd /home/danila/projects/wookiee/deploy && docker compose restart telemost-recorder-api'
```

**Проверить что подхватилось:**

```bash
ssh timeweb 'docker exec telemost_recorder_api ls -la /opt/wookiee/secrets/'
# Должен быть свежий timestamp на telemost_storage_state.json
```

**Удалить локальную копию куки** после загрузки — не стоит держать секрет в `data/` дольше чем нужно:

```bash
rm data/telemost_storage_state.json
```

### Если скрипт не смог авто-залогиниться

Yandex иногда меняет CSS-классы на passport.yandex.ru. Скрипт пробует несколько вариантов селекторов, но если все не сработали — он перейдёт в режим «жду 7 минут пока ты сам залогинишься в открытом окне».

В таком случае:
1. В открытом Chromium-окне руками введи логин и пароль
2. Реши капчу
3. Дождись редиректа на главную Yandex 360 (Mail / Disk / etc.)
4. Скрипт сам поймает `Session_id` cookie и сохранит файл

Если 7 минут не хватило — перезапусти скрипт.

### Что НЕ работает

- **Headless логин** — Yandex показывает капчу при заходе без GUI. Скрипт всегда открывает видимый Chromium.
- **Скрипт на сервере** — нет дисплея, нельзя капчу решить. Куки экспортируются только локально.
- **Шеринг куки между организациями** — каждый Yandex 360 Business org имеет свои домены и свою юрисдикцию anti-bot. Один бот-аккаунт = одна organisation.

## Деплой нового бот-аккаунта (multi-tenant в будущем)

Если когда-нибудь будем продавать рекордер другим командам:

1. Каждая организация заводит **свой** Yandex 360 Business юзер на свой домен (бренд во встрече будет их, не Wookiee)
2. Экспортирует куки тем же скриптом, заливает на сервер в `/opt/wookiee/secrets/<tenant_id>/telemost_storage_state.json`
3. API при спавне recorder-контейнера выбирает нужный файл по tenant_id триггерной встречи

Сейчас архитектура к этому готова — один env var (`TELEMOST_STORAGE_STATE_PATH`), но фактически hardcoded на один тенант (Wookiee). Multi-tenant требует:
- Таблицу `telemost.tenant_credentials` (tenant_id, storage_state_blob_encrypted, last_validated_at)
- Логику в `docker_client.spawn_recorder_container(..., tenant_id=...)`
- Health-check воркер раз в сутки

См. PR #142 — там это намечено как Phase 2.

## Где смотреть логи

| Что смотрим | Команда |
|-------------|---------|
| API event loop, спавны recorder-контейнеров, ошибки | `ssh timeweb 'docker logs telemost_recorder_api --tail 200'` |
| Конкретный recorder-контейнер (он короткоживущий) | `ssh timeweb 'docker logs telemost_rec_<8chars>'` |
| Состояния FSM, скриншоты, экспорты | `/home/danila/projects/wookiee/data/telemost/<meeting_id>/` |
| Telegram-алерты | `@wookiee_alerts_bot` чат |

## Где смотреть метрики

- `telemost.meetings` в Supabase — статусы, длительность, ошибки
- `data/telemost/<meeting_id>/raw_segments.json` — что распозналось в транскрипте
- Notion-страницы — где постпроцесс положил саммари

## Quick reference

```bash
# Статус всех recorder-контейнеров
ssh timeweb 'docker ps --filter "label=telemost.role=recorder"'

# Здоровье API
ssh timeweb 'docker ps --filter "name=telemost_recorder_api" --format "{{.Status}}"'

# Последние 10 встреч из БД
ssh timeweb 'docker exec telemost_recorder_api python -c "
import asyncio
from services.telemost_recorder_api.db import get_pool
async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(\"SELECT id, status, created_at FROM telemost.meetings ORDER BY created_at DESC LIMIT 10\")
        for r in rows: print(dict(r))
asyncio.run(main())
"'

# Принудительно проверить, что storage_state файл подхватывается
ssh timeweb 'docker exec telemost_recorder_api env | grep TELEMOST_STORAGE'
ssh timeweb 'docker exec telemost_recorder_api ls -la /opt/wookiee/secrets/'
```

## История

- **2026-05-15 PR #142** — авторизованный бот через Yandex 360 cookies, anti-bot kick устранён
- **2026-05-15 PR #143** — фикс `AUTH_PRE_JOIN` экрана (залогиненный юзер видит pre-join без поля имени)
- **2026-05-15 PR #144** — убрана ложная participant-count проверка из `detect_meeting_ended` (выкидывала на 5-й минуте на Yandex 360 UI)
- **2026-05-15 verification** — smoke test `1af24f67` прожил 23 минуты, DONE clean
