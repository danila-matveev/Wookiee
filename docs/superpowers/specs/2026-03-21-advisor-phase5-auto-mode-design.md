# Advisor Phase 5 — Auto-Verification & Adaptive Thresholds

**Date:** 2026-03-21
**Status:** Draft (реализация после Phase 4 + 3-6 месяцев feedback данных)
**Author:** Claude + Danila
**Depends on:** Phase 4 (`advisor-phase4-self-learning-design.md`)

## Контекст

Phase 4 реализует:
- Feedback loop (пользователь оценивает рекомендации: useful/inaccurate/irrelevant)
- Pattern confirmation через Telegram
- Effectiveness dashboard
- Manual threshold tuning

**Что остаётся нерешённым после Phase 4:**

1. **Пороги всё ещё ручные** — пользователь сам решает, когда менять порог
2. **Паттерны всё ещё требуют ручного подтверждения** — advisor предлагает, но без автоматизации
3. **Нет адаптации к сезонности** — один порог ДРР для всех сезонов
4. **Нет автоматического удаления неэффективных паттернов**

---

## Проблема

Advisor chain с feedback loop — это полуавтоматическая система. Пользователь тратит время на:
- Подтверждение/отклонение каждого предложенного паттерна
- Ручной тюнинг порогов
- Анализ effectiveness report для принятия решений

При масштабировании (больше каналов, больше моделей) ручное управление становится бутылочным горлышком.

---

## Goals

1. **Auto-Threshold**: система автоматически предлагает изменение порогов на основе feedback data (useful rate < 30% → порог слишком низкий)
2. **Auto-Verification**: предложенные паттерны, которые стабильно срабатывают и получают positive feedback, автоматически переходят в `verified: true`
3. **Pattern Deprecation**: паттерны с consistently low useful rate автоматически деактивируются
4. **Seasonal Adaptation**: пороги корректируются в зависимости от сезона/периода (на основе исторических данных)

## Non-Goals

- ML-модель для генерации рекомендаций (LLM остаётся)
- Автоматическое применение рекомендаций (human-in-the-loop остаётся)
- Замена Signal Detector на ML (детерминированные паттерны остаются)
- Multi-tenant (один пользователь)

---

## Компонент 1: Auto-Threshold Adjustment

### Логика

Еженедельный анализ feedback по каждому signal type:

```python
def analyze_threshold_effectiveness(signal_type: str, days: int = 30) -> dict:
    """Analyze if threshold needs adjustment based on feedback."""
    # Собрать все feedback для данного signal_type
    # useful_rate = useful / (useful + inaccurate + irrelevant)
    #
    # Правила:
    # - useful_rate < 30% AND total_feedback >= 10 → порог слишком низкий, предложить +20%
    # - useful_rate > 80% AND total_feedback >= 10 → порог оптимален
    # - inaccurate_rate > 40% → числа в рекомендациях неточны (проблема advisor, не порога)
    # - irrelevant_rate > 50% → паттерн не актуален для бизнеса
```

### Действие

Система НЕ применяет изменения автоматически. Она:
1. Формирует предложение: "Порог `high_drr` → 15% (было 12%). Причина: useful rate 25% за 30 дней"
2. Отправляет в Telegram с кнопками `[Применить] [Отклонить] [Другое значение]`
3. При "Применить" — обновляет `kb_patterns.trigger_condition.threshold`

### Периодичность

- Раз в неделю, в составе weekly effectiveness report
- Только для паттернов с >= 10 feedback записей

---

## Компонент 2: Auto-Verification

### Критерии автоматической верификации

Предложенный паттерн (`verified: false`) переходит в `verified: true` если:

1. **Срабатывает >= 3 раза** за последние 30 дней (из recommendation_log)
2. **Useful rate >= 60%** (из feedback за эти срабатывания)
3. **Нет конфликтов** с существующими verified паттернами (check_kb_rules)
4. **Возраст >= 14 дней** (не спешим верифицировать)

```python
def check_auto_verification() -> list[dict]:
    """Find patterns ready for auto-verification."""
    unverified = load_kb_patterns(verified_only=False)
    candidates = []
    for p in unverified:
        if p["verified"]:
            continue
        stats = get_pattern_stats(p["pattern_name"], days=30)
        if (stats["trigger_count"] >= 3
            and stats["useful_rate"] >= 0.6
            and stats["age_days"] >= 14
            and not stats["has_conflicts"]):
            candidates.append(p)
    return candidates
```

### Действие

- Отправляет batch-уведомление в Telegram: "3 паттерна готовы к автоверификации: ..."
- Кнопки: `[Подтвердить все] [Просмотреть по одному] [Пропустить]`
- При подтверждении — `UPDATE verified = true`

---

## Компонент 3: Pattern Deprecation

### Критерии деактивации

Verified паттерн деактивируется если:

1. **Не срабатывал 60 дней** (из recommendation_log)
2. **Useful rate < 20%** за последние 30 дней при >= 5 feedback
3. **Пользователь отклонил > 3 раз** (через Telegram feedback "irrelevant")

### Действие

- Паттерн переводится в `verified: false` (не удаляется)
- Уведомление: "Паттерн `low_margin_model` деактивирован (useful rate 15%). Восстановить?"
- Кнопки: `[Восстановить] [Удалить навсегда] [OK]`

---

## Компонент 4: Seasonal Adaptation

### Концепция

Некоторые пороги зависят от сезона (например, ДРР в высокий сезон может быть выше нормы). Система анализирует исторические данные и предлагает сезонные корректировки.

### Реализация

```python
def detect_seasonal_shift(signal_type: str) -> Optional[dict]:
    """Detect if current period has different normal values."""
    # Сравнить avg метрику за текущий месяц vs предыдущие 3 месяца
    # Если отклонение > 2 стандартных отклонения → предложить сезонный порог
    #
    # Пример:
    # ДРР средний за окт-дек: 8%
    # ДРР средний за январь: 14% (сезон распродаж)
    # → Предложить: временный порог high_drr = 18% до конца января
```

### Ограничения

- Требует минимум 6 месяцев данных в recommendation_log
- Только для числовых порогов (threshold-based patterns)
- Сезонные изменения временные (auto-revert после периода)

---

## Файловая структура изменений

```
# CREATE
agents/oleg/services/advisor_auto.py       # Auto-threshold, auto-verification, deprecation
agents/oleg/services/seasonal_adapter.py   # Seasonal shift detection

# MODIFY
agents/oleg/services/advisor_feedback.py   # + pattern stats aggregation
agents/oleg/app.py                         # Telegram handlers for auto-suggestions
shared/signals/kb_patterns.py              # + deactivate_pattern(), reactivate_pattern()
agents/oleg/storage/state_store.py         # + threshold_change_log table

# TESTS
tests/agents/oleg/services/test_advisor_auto.py
tests/agents/oleg/services/test_seasonal_adapter.py
```

---

## Prerequisite: данные от Phase 4

Phase 5 имеет смысл начинать только после:

1. **3-6 месяцев работы Phase 4** — достаточно feedback данных
2. **Минимум 200 feedback записей** — статистическая значимость
3. **Минимум 10 verified KB-паттернов** — есть что тюнить
4. **Feedback rate > 30%** — пользователь реально оценивает рекомендации (иначе авто-тюнинг бессмысленен)
5. **Phase 4 стабильна** — no bugs, effectiveness report генерируется корректно

---

## Критерий успеха

1. Система предлагает изменение порогов на основе feedback (не применяет автоматически)
2. Паттерны с хорошей статистикой автоматически предлагаются к верификации
3. Неэффективные паттерны автоматически деактивируются (с уведомлением)
4. Сезонные сдвиги обнаруживаются и предлагаются временные корректировки
5. Все автоматические действия логируются и могут быть отменены (reversible)
6. Human-in-the-loop сохраняется — система предлагает, не применяет

---

## Архитектурное ограничение

Phase 5 остаётся **advisory** (предлагает, не применяет). Полная автоматизация (auto-apply thresholds, auto-verify without confirmation) — потенциальная Phase 6, после доказательства надёжности авто-рекомендаций.
