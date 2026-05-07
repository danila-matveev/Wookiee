# /product-launch-review — Валидация продуктового запуска

**Запуск:** `/product-launch-review` (или: "стоит ли запускать", "оценить запуск", "проверь продукт", "целесообразность запуска")

## Что делает

5-агентная панель валидации запуска нового продукта на WB/OZON. Архитектура из 3 волн с зависимостями:

```
Wave 1 (parallel, background, 3 агента)
├─ Marketplace Strategist (рынок, конкуренты, SEO, OZON)
├─ Product/Marketing Strategist (концепция, УТП, контент карточки)
└─ Financial Modeler (маржа, sensitivity, ROI, прибыль партии)

Wave 2 (sequential, 1 агент)
└─ Red Team / Devil's Advocate (pre-mortem, оспаривание, минимальный бар)

Wave 3 (foreground, 1 агент)
└─ Brand Director (синтез + явный ответ на возражения Red Team)
```

## Параметры (Stage 0)

8 обязательных вопросов через AskUserQuestion:

1. Источник контекста (Notion URL / текст / уже в чате)
2. MOQ (минимальная партия от производителя)
3. Полная COGS на единицу (₽, с доставкой и налогами)
4. Целевая финальная цена (старт + после 100+ отзывов)
5. Целевая маржа (%)
6. Каналы (только WB / WB+OZON параллельно / WB сейчас, OZON позже)
7. Аналоги в портфеле (Charlotte, Wendy и т.п. для бенчмарка)
8. Дедлайн / сезонная привязка

## Stage 0.5: Pre-flight check (КРИТИЧНО)

Inline-расчёт перед запуском агентов:
- Минимальная финальная цена для целевой маржи
- Cash commitment (`MOQ × COGS`)
- Прогнозируемая прибыль с партии
- Прогнозируемый ROI и payback

Если расхождение цены пользователя с min_price > 10% → **СТОП**, попросить пересмотреть. Если cash > 2,000,000 ₽ → явный warning.

## Результат

1. **Финальный вердикт от Brand Director** в чате (9 секций):
   - Вердикт (GO / УСЛОВНЫЙ GO / NO-GO)
   - Топ-3 довода
   - **Ответ Red Team** (явное принятие/отвержение возражений)
   - Критические условия
   - Остаточные риски
   - Параметры запуска (таблица)
   - Прогноз 6 месяцев (3 сценария + вероятности)
   - Стратегический смысл для бренда
   - Главное действие сейчас

2. **Артефакт** в `docs/reports/YYYY-MM-DD-product-launch-{slug}.md` — все входы Stage 0, Pre-flight, 4 отчёта аналитиков, синтез директора. Полная воспроизводимость.

3. **Stage 5: Iteration loop** — при изменении входов (MOQ/цена/аналог) — перезапуск только нужных волн.

## Промпт-файлы агентов

| Файл | Агент |
|------|-------|
| `prompts/marketplace-specialist.md` | Marketplace Strategist (рынок, без детальной экономики) |
| `prompts/product-marketing.md` | Product/Marketing Strategist |
| `prompts/financial-modeler.md` | Financial Modeler (8 ценовых точек, sensitivity, ROI) |
| `prompts/red-team.md` | Red Team (pre-mortem, оспаривание, минимальный бар) |
| `prompts/brand-director.md` | Brand Director (9-секционный финальный вердикт) |

## Зависимости

- Supabase MCP (`gjvwcdtfglupewcwzfhw`) — логирование в `tool_runs`
- Notion MCP (`mcp__claude_ai_Notion__notion-fetch`) — fetch продуктовой карточки
- PostgreSQL (DB Server, read-only) — данные аналогов через `shared/data_layer.py`
- AskUserQuestion — Stage 0 интерактивный сбор экономики

## Critical Rules

- **Stage 0 + 0.5 не пропускать** даже если все цифры в Notion — карточки часто содержат убыточные ценовые рекомендации
- **Wave 1 строго параллельно** (3 агента в одном сообщении)
- **Wave 2 НЕ запускать** до получения всех 3 отчётов Wave 1
- **Wave 3 НЕ запускать** до Wave 2
- **Director обязан адресовать возражения Red Team** явно — иначе вердикт неполный
- **Все цифры в промптах — только из подтверждённых Stage 0**

## История запусков (проверка)

```bash
# Через Hub UI: https://hub.os.wookiee.shop → Activity → product-launch-review
# Или через Supabase MCP:
# SELECT started_at, status, notes, result_url, duration_sec
# FROM tool_runs WHERE tool_slug = '/product-launch-review'
# ORDER BY started_at DESC LIMIT 10;
```

## Использовавшийся кейс

**Боди Love (2026-05-07):** Notion рекомендовал 1,499-1,999₽ при COGS 808₽. Pre-flight check поймал противоречие: при марже 28% минимум 2,900₽. После пивота MOQ 240→3,000 партия = 2.4M₽ commit. Финальный вердикт: УСЛОВНЫЙ GO при цене 2,900₽, партии 3,000 ед., прибыль ~2.3-2.5M₽ за 4 месяца.
