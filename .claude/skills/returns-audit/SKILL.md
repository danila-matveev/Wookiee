---
name: returns-audit
description: Анализ заявок на возврат покупателей через WB Returns API — динамика, причины, фото, карточки моделей, публикация в Notion.
---

# Returns Audit Skill

Анализ заявок на возврат через WB Returns API. Собирает claims за последние 14 дней (ИП + ООО), обогащает данными заказов из БД, анализирует через субагенты и публикует в Notion.

## Stage 0 — Параметры

Параметры фиксированы:
- Период: последние 14 дней (ограничение API)
- Кабинеты: ИП + ООО
- Без вопросов пользователю

Вычисли даты:
```
END = сегодня (YYYY-MM-DD)
START = сегодня − 14 дней (YYYY-MM-DD)
PERIOD_LABEL = "{START} — {END}"
```

## Stage 1 — Сбор данных

Запусти коллектор:

```bash
python3 scripts/returns_audit/collect_data.py --output /tmp/returns_audit_data.json
```

Прочитай результат из `/tmp/returns_audit_data.json`.

**Проверки:**
- Если `summary.total_claims == 0` → СТОП, сообщи пользователю "Нет заявок на возврат за период"
- Если файл не создался → СТОП, покажи ошибку коллектора

Сохрани содержимое файла в переменную `DATA`.

## Stage 2 — Анализ (субагенты)

### Wave 1 — Тренд + Причины (параллельно)

Прочитай промпт-файлы:
- `.claude/skills/returns-audit/prompts/trend.md`
- `.claude/skills/returns-audit/prompts/reasons.md`

В каждом замени плейсхолдеры:
- `{{DATA}}` → содержимое `DATA` (полный JSON)
- `{{PERIOD_LABEL}}` → `PERIOD_LABEL`

Запусти **2 Agent-а В ОДНОМ сообщении** (параллельно):

```
Agent 1: subagent_type="general-purpose", prompt=trend_prompt
Agent 2: subagent_type="general-purpose", prompt=reasons_prompt
```

Сохрани результаты как `TREND_OUTPUT` и `REASONS_OUTPUT`.

### Wave 2 — Модельные карточки (параллельно)

Из `DATA.summary.by_model` выбери модели с `claims >= 3`.

Прочитай промпт: `.claude/skills/returns-audit/prompts/model_card.md`

Для каждой модели замени:
- `{{MODEL_NAME}}` → имя модели
- `{{MODEL_CLAIMS}}` → claims этой модели (отфильтрованные из DATA.claims)
- `{{MODEL_SUMMARY}}` → summary этой модели из DATA.summary.by_model
- `{{TREND_FINDINGS}}` → ключевые выводы из TREND_OUTPUT
- `{{REASON_FINDINGS}}` → ключевые выводы из REASONS_OUTPUT

Запусти **все модельные Agent-ы В ОДНОМ сообщении** (параллельно).

Сохрани результаты как `MODEL_CARDS` (массив).

### Wave 3 — Верификация + Синтез (последовательно)

**Шаг 1: Верификатор**

Прочитай промпт: `.claude/skills/returns-audit/prompts/verifier.md`

Замени:
- `{{RAW_DATA}}` → `DATA` (сырые данные)
- `{{TREND_OUTPUT}}` → `TREND_OUTPUT`
- `{{REASONS_OUTPUT}}` → `REASONS_OUTPUT`
- `{{MODEL_CARDS}}` → `MODEL_CARDS`

Запусти Agent. Сохрани как `VERIFIER_OUTPUT`.

Проверь `verdict`:
- `PASS` или `FLAG` → продолжай
- `REJECT` → покажи пользователю ошибки и СТОП

**Шаг 2: Синтезайзер**

Прочитай промпт: `.claude/skills/returns-audit/prompts/synthesizer.md`

Замени:
- `{{TREND_OUTPUT}}` → `TREND_OUTPUT`
- `{{REASONS_OUTPUT}}` → `REASONS_OUTPUT`
- `{{MODEL_CARDS}}` → `MODEL_CARDS`
- `{{VERIFIER_OUTPUT}}` → `VERIFIER_OUTPUT`
- `{{PERIOD_LABEL}}` → `PERIOD_LABEL`

Запусти Agent. Сохрани как `SYNTH_OUTPUT`.

## Stage 3 — Публикация

### Notion

Используй Notion MCP для создания страницы в БД "Аналитические отчеты":
- Заголовок: `SYNTH_OUTPUT.publish_title`
- Содержимое: `SYNTH_OUTPUT.final_document_notion`
- data_source_id: `returns_audit`
- Период: `PERIOD_LABEL`

### Markdown файл

Сохрани `SYNTH_OUTPUT.final_document_notion` в:
`docs/reports/returns-audit-{START}_{END}.md`

### Финальное сообщение

Покажи пользователю:
- Ссылку на Notion-страницу
- Сводку: total claims, return rate %, топ-3 модели
- Если верификатор дал FLAG — упомяни замечания
