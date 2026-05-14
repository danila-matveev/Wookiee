# W9 — Orchestrator Script (полностью автономный цикл исправлений каталога)

> **Этот документ — главный prompt для оркестратора.** В новом окне Claude Code нужно
> только сказать: «Выполни инструкции из этого файла». Дальше всё делается автоматически.

## 0. Контекст и роли

- **Ты:** оркестратор W9. Координируешь параллельные sub-agent'ы.
- **Пользователь:** уже одобрил план, **подтверждения между волнами НЕ нужны**.
- **Источник правды:**
  `wookiee-hub/.planning/catalog-management-overhaul/W9-FIXES-TZ.md` —
  читай его ПОЛНОСТЬЮ перед любым диспатчем.
- **Дополнительный контекст:**
  - `AGENTS.md` (корень проекта) — общие правила
  - `wookiee-hub/CLAUDE.md` (если есть) — фронтенд-правила
  - Память: `~/.claude/projects/-Users-danilamatveev-Projects-Wookiee/memory/MEMORY.md`

## 1. Главные правила

1. **БЕЗ подтверждений между волнами.** Прошла Волна A → сразу запускай Волну B. И т.д.
   Подтверждение нужно ТОЛЬКО перед `git push` финальной ветки и `rsync deploy`.
2. **Worktree-изоляция обязательна.** Каждый sub-agent работает в `.claude/worktrees/w9-*`
   через `Agent({ isolation: "worktree", ... })`. Проверь reflog после каждой волны,
   чтобы избежать инцидента W8 Phase 2 (потеря коммита).
3. **Параллелизм внутри волны.** Запускай всех агентов волны одним сообщением с
   несколькими tool-вызовами `Agent`.
4. **Сборка перед merge.** В каждой ветке агента после изменений:
   `npx tsc --noEmit && npm run build`. Если падает — фикс на месте.
5. **Cherry-pick в feature/catalog-overhaul-w9.** После завершения волны собрать
   коммиты всех агентов в общую feature-ветку через cherry-pick (или octopus merge),
   разрешить конфликты вручную.
6. **DB-миграции** через Supabase MCP `apply_migration` (проект `gjvwcdtfglupewcwzfhw`).
   Номера: `024-*.sql`, `025-*.sql`, ...
7. **Русский в коммитах и комментариях НЕ обязателен**, но в UI-текстах — обязателен.

## 2. Подготовка перед волнами

```bash
# Из main создать ветку W9
git checkout main
git pull --rebase origin main
git checkout -b feature/catalog-overhaul-w9
git push -u origin feature/catalog-overhaul-w9
```

Запиши SHA `feature/catalog-overhaul-w9` после первого пуша — это safety point.

## 3. Волны (по порядку, без пауз на подтверждение)

### Волна A — Блокеры и data layer (параллельно: 4 агента)

| Agent | Задача | Файлы/области | DB migration |
|-------|--------|----------------|--------------|
| **A1** | W9.1 GRANT/RLS на `istoriya_izmeneniy` | DB only | `024_audit_grants.sql` |
| **A2** | W9.2 + W9.3 (status-колонки + поиск унифицированный) | matrix.tsx, artikuly.tsx, tovary.tsx, service.ts | — |
| **A3** | W9.8 (логика размеров — агрегатор размерного ряда) | service.ts (size aggregator), matrix.tsx | — |
| **A4** | W9.12 (палитра по категории) | DB + новый ColorPicker | `025_tsvet_categories.sql` |

**Запустить волну A:** один Agent-message с 4 параллельными вызовами,
каждый `isolation: "worktree"`, `subagent_type: "general-purpose"`.

**Prompt-шаблон для агента волны (адаптируй на каждый):**

```
Ты — sub-agent W9.<N> в рамках цикла исправлений каталога Wookiee Hub.

ТЗ: /Users/danilamatveev/Projects/Wookiee/wookiee-hub/.planning/catalog-management-overhaul/W9-FIXES-TZ.md
  — раздел W9.<N>. Прочитай его полностью.

Базовая ветка: feature/catalog-overhaul-w9 (создана из main).

Что делать:
1. Прочитай ТЗ (раздел W9.<N>) и связанный код в wookiee-hub/src/.
2. Реализуй ВСЕ acceptance-критерии секции.
3. Не выходи за пределы своей задачи (НЕ трогай файлы других агентов волны,
   если они явно перечислены — см. таблицу).
4. После изменений:
   - `cd wookiee-hub && npx tsc --noEmit` — должно быть 0 ошибок.
   - `cd wookiee-hub && npm run build` — должно собраться.
5. Коммит: `feat(W9.<N>): <короткое описание>` (английский OK).
6. Верни: SHA коммита, список изменённых файлов, упомяни если нужны DB-миграции.

Ограничения:
- Worktree изолирован, не пуш в origin сам.
- Не делай deploy на сервер.
- Если упёрся в архитектурный вопрос — верни вопрос в ответе, не блокируйся.
```

**После завершения волны A:**
1. Cherry-pick всех 4 коммитов в `feature/catalog-overhaul-w9`.
2. Прогнать `tsc + build` в основной ветке.
3. Если есть DB-миграции — применить через Supabase MCP.
4. **БЕЗ паузы → волна B.**

---

### Волна B — UI инфраструктура (параллельно: 7 агентов)

| Agent | Задача | Зависимости |
|-------|--------|-------------|
| **B1** | W9.4 + W9.16 (compact dropdown filters + status filter) | — |
| **B2** | W9.5 (column configurator: show/hide/drag, all fields, на 3 реестрах) | — |
| **B3** | W9.6 (collapsible groups при группировке) | — |
| **B4** | W9.7 (sticky первая колонка на 3 реестрах) | — |
| **B5** | W9.9 (channel switcher фильтрует /catalog/tovary) | A2 (must be merged) |
| **B6** | W9.15 (overflow / line-clamp / tooltip) | — |
| **B7** | W9.18 (toast errors вместо raw SQL) | — |

**Конфликт-зоны:** B1, B2, B3, B4 все трогают одни и те же файлы реестров
(`matrix.tsx`, `artikuly.tsx`, `tovary.tsx`). Стратегия:
- Каждый агент работает в своём worktree.
- Перед cherry-pick делать SHA-сравнение и резолвить конфликты вручную.
- Альтернатива: запустить B1→B2→B3→B4 последовательно, B5/B6/B7 параллельно.
  **Выбери эту стратегию для надёжности.**

**Порядок волны B:**
1. Запустить параллельно: B5, B6, B7.
2. Дождаться завершения.
3. Запустить последовательно: B1 → cherry-pick → B2 → cherry-pick → B3 → cherry-pick → B4 → cherry-pick.
4. tsc + build после полной волны.

---

### Волна C — Редактирование и консистентность (параллельно: 3 агента)

| Agent | Задача | Зависимости |
|-------|--------|-------------|
| **C1** | W9.10 (inline-edit на /catalog/artikuly и /catalog/tovary) | A1 (audit grants merged) |
| **C2** | W9.11 (редактируемое имя артикула в модалке) | A1 |
| **C3** | W9.17 (унифицированный StatusBadge) | — |

Запустить параллельно. Cherry-pick. tsc + build.

---

### Волна D — Продуктовый UX (параллельно: 4 агента)

| Agent | Задача | Зависимости |
|-------|--------|-------------|
| **D1** | W9.13 (+ Добавить цвет из карточки модели) | A4 (ColorPicker by category) |
| **D2** | W9.14 (+ Новый атрибут из карточки модели) | — |
| **D3** | W9.19 (EmptyState компонент + применение везде) | — |
| **D4** | W9.20 (прогресс заполнения атрибутов + bulk-edit) | — |

Запустить параллельно. Cherry-pick. tsc + build.

---

## 4. Верификация (после всех 4 волн)

### Verifier-1 (агент верификации):

Запустить sub-agent `general-purpose` с prompt:

```
Ты — верификатор W9. Цикл из 4 волн только что закончился.

Прочитай acceptance-чеклист из:
/Users/danilamatveev/Projects/Wookiee/wookiee-hub/.planning/catalog-management-overhaul/W9-FIXES-TZ.md
  — раздел "Acceptance Criteria (общий чек-лист W9)".

Задача: пройти по каждому пункту и убедиться, что в коде feature/catalog-overhaul-w9
он реализован. Используй grep/Read/Bash.

Дополнительно:
1. `cd wookiee-hub && npx tsc --noEmit` — должно быть 0 ошибок.
2. `cd wookiee-hub && npm run build` — успешная сборка.
3. Локальный smoke если возможно: `npm run preview` + Playwright навигация
   на /catalog, /catalog/artikuly, /catalog/tovary.

Верни:
- Список ВЫПОЛНЕННЫХ пунктов (с конкретными файлами/строками доказательством).
- Список НЕВЫПОЛНЕННЫХ пунктов (с описанием что не так).
- Список новых багов, обнаруженных в процессе.

Формат вывода — markdown-таблица: пункт | статус (PASS/FAIL/PARTIAL) | доказательство.
```

### Если есть FAIL/PARTIAL → волна F (фикс)

Для каждого FAIL/PARTIAL запустить fix-агента. Параллельно если независимы.
Каждый fix-агент: один пункт, минимальная правка, tsc + build, коммит, cherry-pick.

### Verifier-2 (повторная верификация)

После всех фиксов — снова Verifier-1 с тем же prompt'ом. Должно быть всё PASS.

**Если опять есть FAIL — ещё одна волна F (но не больше 3 циклов F, иначе сломалось
что-то фундаментальное → стоп, отчёт пользователю).**

---

## 5. Финальный deploy (ТРЕБУЕТ подтверждения пользователя)

Когда Verifier-2 вернул всё PASS:

1. Сформировать отчёт:
   ```
   ## W9 готов к деплою
   - Все 20 acceptance-пунктов: PASS
   - DB migrations: 024, 025
   - Изменённые файлы: <список>
   - SHA финального коммита: <hash>
   ```
2. Спросить пользователя: «Готово, выкатывать на прод? (push + rsync deploy)»
3. После «да»:
   - `git push origin feature/catalog-overhaul-w9`
   - Создать PR: `gh pr create --base main --title "W9 — Catalog fixes (20 items)"`
   - Smoke на preview если есть.
   - Merge PR (после CI зелёного).
   - rsync deploy:
     ```bash
     cd wookiee-hub
     npm run build
     rsync -avz --delete dist/ timeweb:/home/danila/projects/wookiee/wookiee-hub/dist/
     ```
   - Прод-smoke через Playwright MCP: `https://hub.os.wookiee.shop/catalog` —
     основные сценарии из чеклиста.
4. Отчитаться пользователю: что задеплоено, какие задачи остались (если есть).

---

## 6. Что делать если что-то идёт не так

- **Sub-agent вернул ошибку:** read его лог, проанализируй, перезапусти с уточнённым prompt.
- **Merge-конфликты:** разрешать вручную, не делать `git reset --hard` без backup-ветки.
- **DB-миграция упала:** через Supabase MCP сделать `list_migrations`, проверить state.
- **TSC валит после волны:** локализовать через `git bisect` по cherry-pick'ам.
- **Worktree сломался:** проверь branch rename (см. project memory о EnterWorktree).
- **3+ цикла F:** остановись, отчёт пользователю с конкретными нерешёнными пунктами.

---

## 7. Логирование

Каждый шаг логировать в `wookiee-hub/.planning/catalog-management-overhaul/W9-LOG.md`:
- Время старта/конца каждой волны
- SHA коммитов агентов
- Результаты tsc/build
- Verifier-отчёты
- Финальный deploy

Это файл-журнал, обновляй его как append-only после каждого значимого события.

---

## 8. Стартовая команда

После прочтения этого файла начинай сразу с раздела 2 (подготовка) → раздел 3 (волна A).
НЕ спрашивай подтверждение. Подтверждение нужно только перед deploy (раздел 5).
