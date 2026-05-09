# Catalog Rework — Master Execution Prompt

**Этот файл — единая точка входа для запуска полного rework каталога Wookiee Hub через субагентов.**

Скопируй ВЕСЬ ЭТОТ ФАЙЛ в начало новой сессии Claude Code в Wookiee Hub репозитории. Он самодостаточен.

---

## Контекст для тебя, Claude

Ты получаешь приоритетную задачу: переписать модуль каталога в Wookiee Hub так, чтобы он 1:1 соответствовал MVP-прототипу, и привести БД в согласованное состояние. План разбит на 4 фазы (Wave 0-3) с подробными описаниями в этой же папке.

Все материалы находятся в:
```
/Users/danilamatveev/Projects/Wookiee/wookiee-hub/.planning/catalog-rework/
```

**ОБЯЗАТЕЛЬНО прочитай эти файлы ПЕРЕД началом работы (в указанном порядке):**

1. `00_README.md` — общий обзор и согласованные решения
2. `01_DATA_AUDIT.md` — DQ-проблемы в БД с фактами
3. `02_STATUSES_FROM_SHEET.md` — реальные статусы из Google Sheet
4. `03_GAP_LIST.md` — полный gap-list MVP → текущая реализация
5. `04_WAVE_0_SYNC.md` — фаза 0 (миграции БД и заливка из Sheet)
6. `05_WAVE_1_FOUNDATION.md` — фаза 1 (4 параллельных агента: типы, service, atomic UI, layout)
7. `06_WAVE_2_PAGES.md` — фаза 2 (6 параллельных агентов: страницы)
8. `07_WAVE_3_QA.md` — фаза 3 (3+1 QA-агентов)
9. `09_VERIFICATION_PROTOCOL.md` — что проверять после каждой фазы

**Эталон UI:** `/Users/danilamatveev/Projects/Wookiee/redesign + PIX/wookiee_matrix_mvp_v4.jsx` (2044 строк).
**Эталон данных:** Google Sheet `19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg` (читать через `services/sheets_sync/credentials/google_sa.json`).
**Supabase project:** `gjvwcdtfglupewcwzfhw` (через `mcp__plugin_supabase_supabase__*`).

---

## Согласованные решения (от пользователя)

- ✅ Схема статусов — 5 типов (model/artikul/product/sayt/color), плюс lamoda как отдельный
- ✅ Дубликаты kategorii/kollekcii — мердж автоматически
- ✅ Семейства цветов — заполнить миграцией по префиксам
- ✅ Hex для цветов — программный маппинг + color picker для уточнения
- ✅ Сертификаты — отдельный справочник со ссылкой на Drive (`file_url`)
- ✅ Дублирование модели = шаблон (только modeli_osnova, без вариаций)
- ✅ Архивирование — каскадное (модель → все вниз)
- ✅ Bulk actions — реализовать (статус, привязка к склейке, экспорт)
- ✅ Inline editing — везде (через editing/draft state)
- ✅ Каналы продаж — все 4, ColumnsManager-настройка видимости
- ✅ Время не считать — параллельные агенты

---

## Workflow выполнения

### ШАГ 1: Подготовка
1. Прочитать 9 планерных файлов (см. список выше)
2. Создать TodoWrite со списком всех фаз и проверок
3. Проверить, что dev сервер не запущен и нет блокирующих процессов
4. Создать ветку для всей работы:
   ```bash
   git checkout -b catalog-rework-2026-05-07
   git push -u origin catalog-rework-2026-05-07
   ```

### ШАГ 2: Запуск Wave 0 (последовательно, 1 агент)

Wave 0 — единственная фаза, которая выполняется **последовательно одним агентом**, потому что это data migration. Параллелизм здесь сломал бы БД.

```
Agent({
    description: "Wave 0 — data migration",
    subagent_type: "general-purpose",
    prompt: ПРОМПТ ИЗ 04_WAVE_0_SYNC.md (раздел "Self-contained промпт для агента Wave 0")
})
```

После завершения:
- Прочитать `wave_0_report.md`
- Запустить проверки из `09_VERIFICATION_PROTOCOL.md` раздел W0
- Если что-то провалилось → исправить и повторить
- Если ОК → переходить к Wave 1

### ШАГ 3: Запуск Wave 1 (4 параллельных агента)

⚠ ВАЖНО: запускать ВСЕ 4 в одном сообщении (multiple Agent tool calls в одном response), чтобы они работали параллельно.

```
[В ОДНОМ СООБЩЕНИИ четыре Agent-вызова]:
Agent({
    description: "Wave 1 A1 — TypeScript types",
    isolation: "worktree",
    subagent_type: "general-purpose",
    prompt: ПРОМПТ A1 ИЗ 05_WAVE_1_FOUNDATION.md
})
Agent({
    description: "Wave 1 A2 — service.ts",
    isolation: "worktree",
    subagent_type: "general-purpose",
    prompt: ПРОМПТ A2 ИЗ 05_WAVE_1_FOUNDATION.md
})
Agent({
    description: "Wave 1 A3 — atomic UI",
    isolation: "worktree",
    subagent_type: "general-purpose",
    prompt: ПРОМПТ A3 ИЗ 05_WAVE_1_FOUNDATION.md
})
Agent({
    description: "Wave 1 A4 — layout",
    isolation: "worktree",
    subagent_type: "general-purpose",
    prompt: ПРОМПТ A4 ИЗ 05_WAVE_1_FOUNDATION.md
})
```

После завершения всех 4:
- Поочерёдно мерджить в catalog-rework-2026-05-07: A1 → A2 → A3 → A4
- Запустить W1 проверки из VERIFICATION_PROTOCOL
- Если ОК → Wave 2

### ШАГ 4: Запуск Wave 2 (6 параллельных агентов)

Снова — все 6 в одном сообщении.

```
[В ОДНОМ СООБЩЕНИИ шесть Agent-вызовов]:
Agent({ description: "Wave 2 B1 — Matrix",        isolation: "worktree", prompt: ПРОМПТ B1 из 06_WAVE_2_PAGES.md })
Agent({ description: "Wave 2 B2 — Registries",    isolation: "worktree", prompt: ПРОМПТ B2 из 06_WAVE_2_PAGES.md })
Agent({ description: "Wave 2 B3 — ModelCard",     isolation: "worktree", prompt: ПРОМПТ B3 из 06_WAVE_2_PAGES.md })
Agent({ description: "Wave 2 B4 — Colors",        isolation: "worktree", prompt: ПРОМПТ B4 из 06_WAVE_2_PAGES.md })
Agent({ description: "Wave 2 B5 — Skleyki",       isolation: "worktree", prompt: ПРОМПТ B5 из 06_WAVE_2_PAGES.md })
Agent({ description: "Wave 2 B6 — References",    isolation: "worktree", prompt: ПРОМПТ B6 из 06_WAVE_2_PAGES.md })
```

После всех 6:
- Мердж по очереди в catalog-rework-2026-05-07
- Решение конфликтов вручную (в основном в Sidebar и роутах — A4 и B6 могут пересечься)
- W2 проверки
- Если ОК → Wave 3

### ШАГ 5: Запуск Wave 3 (3 параллельных QA агента + 1 финальный)

```
[В ОДНОМ СООБЩЕНИИ три Agent-вызова]:
Agent({ description: "Wave 3 C1 — visual diff",   prompt: ПРОМПТ C1 из 07_WAVE_3_QA.md })
Agent({ description: "Wave 3 C2 — functional QA", prompt: ПРОМПТ C2 из 07_WAVE_3_QA.md })
Agent({ description: "Wave 3 C3 — data integrity",prompt: ПРОМПТ C3 из 07_WAVE_3_QA.md })
```

После всех 3 — запустить C4:
```
Agent({ description: "Wave 3 C4 — final fixes",   prompt: ПРОМПТ C4 из 07_WAVE_3_QA.md })
```

После C4:
- W3 проверки
- Создать FINAL_REPORT.md (см. 07_WAVE_3_QA.md финальный раздел)
- Создать PR в main: `gh pr create --base main --title "Catalog rework: 1:1 with MVP + DB cleanup"` (НО НЕ мерджить — пользователь должен ревьюить)

### ШАГ 6: Презентация пользователю

После Wave 3 — НЕ мерджить в main. Вместо этого:
1. Запустить dev сервер: `npm run dev`
2. Сделать скриншоты ключевых страниц
3. Ответить пользователю с:
   - Списком сделанного по фазам
   - Скриншотами до/после
   - Открытым PR с возможностью ревью
   - Предложением посмотреть в браузере

---

## Правила оркестрации

### 1. Параллелизм
Wave 1 и Wave 2 — параллельно через worktree. Wave 0 — последовательно. Wave 3 QA — параллельно (C1+C2+C3), затем C4 последовательно.

### 2. Проверки между фазами — БЛОКИРУЮЩИЕ
- Никогда не запускать следующую Wave если предыдущая не прошла все проверки `09_VERIFICATION_PROTOCOL.md`
- Если проверка провалилась — fix-итерация (до 3 попыток), потом эскалация

### 3. Безопасность БД
- Все мутации БД через `mcp__plugin_supabase_supabase__apply_migration` (а не execute_sql) — для логирования
- Backups в `.planning/catalog-rework/backups/` ОБЯЗАТЕЛЬНЫ перед Wave 0
- DELETE только через миграции с подтверждённой логикой

### 4. Не ломать существующий код
- Все существующие маршруты каталога должны продолжать работать
- Hub-вне-каталога (Activity, Tools, etc.) НЕ трогать
- Текущие фишки (channel filter в TovaryTable, fetchSkleykaDetail и т.д.) — сохранить

### 5. Коммиты
- Каждый агент делает свои коммиты в свою ветку
- В корневой ветке catalog-rework-2026-05-07 — мердж-коммиты с понятными сообщениями
- Финальный коммит «catalog rework: complete» с co-authored

### 6. Не запрашивать у пользователя
Все решения уже приняты (см. секцию «Согласованные решения»). Если возник новый вопрос:
- Сначала попытаться найти ответ в MVP-файле
- Затем — решить здравым смыслом и зафиксировать в отчёте
- Только в крайнем случае — остановиться и спросить

### 7. Когда что-то идёт не так
- Не сносить работу субагента — фиксировать проблему в issue-файле, запускать fix-агента
- Не делать «по дороге» рефакторинг
- Не добавлять backwards-compat шим — пользователь явно сказал «делать заново правильно»

---

## Готов?

Если ты — Claude в новой сессии и читаешь этот файл, начинай по ШАГ 1. Используй `Skill` tool со скиллом `superpowers:brainstorming` ТОЛЬКО если возникла стратегическая дилемма не описанная здесь.

В остальном — действуй по плану. План полный.

---

## Запасные команды (если что-то пошло не так)

### Откатить Wave 0
```bash
# JSON-снимки в backups/wave_0/
# Через mcp execute_sql восстановить из бэкапов
```

### Откатить Wave 1/2
```bash
git checkout main
git branch -D catalog-rework-2026-05-07
git push origin :catalog-rework-2026-05-07
# Начать заново с свежего main
```

### Залогать в Memory если контекст переполняется
- Используй memory-систему: `/Users/danilamatveev/.claude/projects/-Users-danilamatveev-Projects-Wookiee/memory/`
- Сохранять проектные/feedback memories по ходу работы

---

**Финальная цель:**
Каталог Hub визуально и функционально 1:1 с `wookiee_matrix_mvp_v4.jsx`, БД консистентна, RLS на всех таблицах, нет ни одной из 13 жалоб пользователя из последнего скриншота-фидбека.
