---
name: abc-audit
description: "ABC-аудит товарной матрицы Wookiee (WB+OZON) — классификация ABC x ROI, color_code анализ, рекомендации по каждому артикулу"
triggers:
  - /abc-audit
  - abc анализ
  - товарная аналитика
  - аудит товаров
---

# ABC-аудит товарной матрицы

Глубокий товарный ABC-анализ бренда Wookiee (WB + OZON): классификация по матрице ABC × ROI, анализ color_code связок в коллекциях, рекомендации по каждому артикулу.

**Время выполнения:** ~25 минут
**Результат:** `docs/reports/{CUT_DATE}_abc_audit.md`

---

## Stage 0: Парсинг аргументов

Разбери `$ARGUMENTS` — это дата отсечки в формате YYYY-MM-DD. Если не указана — используй сегодня.

Вычисли:
- `CUT_DATE` — дата отсечки
- `P30_START` = CUT_DATE - 30 дней
- `P90_START` = CUT_DATE - 90 дней
- `P180_START` = CUT_DATE - 180 дней

Сообщи пользователю:
```
Запуск ABC-аудита по состоянию на {CUT_DATE}
Периоды: 30д ({P30_START}), 90д ({P90_START}), 180д ({P180_START})
```

---

## Stage 1: Сбор данных (Collector)

Запусти Python-коллектор:

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 scripts/abc_audit/collect_data.py --date {CUT_DATE} --output /tmp/abc-audit-{CUT_DATE}.json
```

Прочитай результат из `/tmp/abc-audit-{CUT_DATE}.json`.

**Проверка:**
- Если в `meta.errors` больше 3 ошибок → СТОП, сообщи пользователю
- Если `meta.quality_flags.coverage_pct` < 50% → СТОП

Сообщи пользователю:
```
Данные собраны за {meta.duration_sec}с
Артикулов в анализе: {count}
Ошибки: {meta.errors or "нет"}
```

### 1.3 Start Tool Logging

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
logger = ToolLogger('/abc-audit')
run_id = logger.start(trigger='manual', user='danila', version='v1')
print(f'RUN_ID={run_id}')
"
```

Save `RUN_ID`. If `None` — continue, logging is fire-and-forget.

---

## Stage 2: Data Analyst (один агент)

Прочитай промпт: `.claude/skills/abc-audit/prompts/data_analyst.md`
Прочитай KB: `.claude/skills/abc-audit/references/abc-kb.md`

Запусти Agent:
- description: "ABC-audit: Data Analyst — validation, metrics, classification"
- prompt: содержимое data_analyst.md, где `{{DATA_BUNDLE}}` заменён на JSON из коллектора. Добавь содержимое abc-kb.md как раздел "# База знаний" в конец промпта.

Сохрани выход как `ENRICHED_DATA`.

**Gate:** Если Data Analyst вернул "GATE FAILED" → СТОП, сообщи пользователю причину.

Сообщи пользователю:
```
Stage 2 завершён: {N} артикулов обогащено, ABC-классификация готова
A: {count_A} артикулов ({margin_A_pct}% маржи)
B: {count_B} артикулов ({margin_B_pct}% маржи)
C: {count_C} артикулов ({margin_C_pct}% маржи)
```

---

## Stage 3: Экспертный совет (3 агента ПАРАЛЛЕЛЬНО)

Прочитай промпты:
- `.claude/skills/abc-audit/prompts/merchandiser.md`
- `.claude/skills/abc-audit/prompts/financier.md`
- `.claude/skills/abc-audit/prompts/marketer.md`

Прочитай KB: `.claude/skills/abc-audit/references/abc-kb.md`

Запусти 3 Agent-а **в одном сообщении** (параллельно):

1. **Товаровед:**
   - description: "ABC-audit: Товаровед — hierarchy, collections, MOQ"
   - prompt: содержимое merchandiser.md + abc-kb.md, где `{{ENRICHED_DATA}}` заменён на ENRICHED_DATA

2. **Финансист:**
   - description: "ABC-audit: Финансист — unit economics, pricing, ROI"
   - prompt: содержимое financier.md + abc-kb.md, где `{{ENRICHED_DATA}}` заменён на ENRICHED_DATA

3. **Маркетолог:**
   - description: "ABC-audit: Маркетолог — DRR, conversion, budget"
   - prompt: содержимое marketer.md + abc-kb.md, где `{{ENRICHED_DATA}}` заменён на ENRICHED_DATA

Дождись всех трёх. Сохрани выходы как `MERCHANDISER_FINDINGS`, `FINANCIER_FINDINGS`, `MARKETER_FINDINGS`.

Сообщи пользователю:
```
Stage 3 завершён: 3 эксперта отработали
Товаровед: {N} находок
Финансист: {N} находок
Маркетолог: {N} находок
```

---

## Stage 4: Арбитр (один агент)

Прочитай промпт: `.claude/skills/abc-audit/prompts/arbiter.md`
Прочитай KB: `.claude/skills/abc-audit/references/abc-kb.md`

Запусти Agent:
- description: "ABC-audit: Арбитр — final decisions, contradictions, confidence"
- prompt: содержимое arbiter.md + abc-kb.md, где:
  - `{{MERCHANDISER_FINDINGS}}` → MERCHANDISER_FINDINGS
  - `{{FINANCIER_FINDINGS}}` → FINANCIER_FINDINGS
  - `{{MARKETER_FINDINGS}}` → MARKETER_FINDINGS
  - `{{ENRICHED_DATA}}` → ENRICHED_DATA

**Обработка вердикта:**
- **APPROVE** → Stage 5
- **CORRECT** → Stage 5 (Арбитр уже исправил)
- **REJECT** → перезапустить указанного эксперта (макс 1 раз). После повторного прохода — если снова проблема, пометить как `⚠️ Данные ненадёжны` и продолжить.

Сохрани выход как `ARBITER_VERDICTS`.

Сообщи пользователю:
```
Stage 4 завершён: {protocol_verdict}
Вердикты: {count} артикулов/групп
P0 (срочно): {count_p0}
P1 (неделя): {count_p1}
P2 (месяц): {count_p2}
```

---

## Stage 5: Synthesizer + Notion Publish

Прочитай промпт: `.claude/skills/abc-audit/prompts/synthesizer.md`

### 5a. Генерация отчёта (Agent)

Запусти Agent:
- description: "ABC-audit: Synthesizer — Notion Enhanced Markdown report"
- prompt: содержимое synthesizer.md, где:
  - `{{ARBITER_VERDICTS}}` → ARBITER_VERDICTS
  - `{{ENRICHED_DATA}}` → ENRICHED_DATA
  - `{{QUALITY_FLAGS}}` → quality_flags из meta

Агент должен сохранить отчёт в `docs/reports/{CUT_DATE}_abc_audit.md` в **Notion Enhanced Markdown** формате (таблицы через `<table>` с цветами строк, callout-блоки с иконками, toggle-заголовки).

### 5b. Верификация

Прочитай сохранённый файл и проверь:
1. Содержит все 13 секций (1–13)
2. Таблицы используют `<table fit-page-width="true">`, а НЕ markdown pipe-формат
3. Есть callout-блоки с цветами (`<callout icon="..." color="...">`)
4. Секции 3-11 имеют `{toggle="true"}`
5. Есть ссылка на Google Sheets в секции 2
6. P0/P1/P2 таблицы имеют цветные заголовки (red/orange/yellow)

Если любой пункт не выполнен — исправь перед публикацией.

### 5c. Публикация в Notion (MCP)

Используй Notion MCP для публикации:

1. Найти предыдущий отчёт ABC в database "Аналитические отчеты" → перевести в статус "Архив"
2. Создать новую страницу через `notion-create-pages`:
   - Parent: database "Аналитические отчеты"
   - Title: "📊 ABC-аудит v4 — {period_label}"
   - Icon: 📊
   - Properties: Тип анализа = "ABC анализ", Статус = "Актуальный", Источник = "Claude Code"
   - Content: содержимое MD-файла
3. Прочитать созданную страницу через `notion-fetch` и убедиться что таблицы и callouts отображаются корректно

### Finish Tool Logging

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
logger = ToolLogger('/abc-audit')
logger.finish('{RUN_ID}', status='success',
    result_url='{NOTION_URL}',
    items_processed={ARTICLE_COUNT},
    output_sections=13)
"
```

If `RUN_ID` is empty — skip.

Сообщи пользователю:
```
ABC-аудит завершён

📊 Notion: {page_url}
📄 MD: docs/reports/{CUT_DATE}_abc_audit.md
📋 Sheets: {sheets_url}
Секций: 13 | Артикулов: {N} | Время: ~{minutes} мин

Топ-3 действия:
1. {P0 action 1}
2. {P0 action 2}
3. {P1 action 1}
```
