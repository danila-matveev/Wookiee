# Advisor Phase 5 — Auto-Verification & Adaptive Thresholds — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Автоматизировать управление паттернами: авто-верификация, авто-деактивация, предложение порогов на основе feedback, сезонная адаптация. Система предлагает — человек подтверждает.

**Prerequisites:** Phase 4 завершена + 3-6 месяцев feedback данных + минимум 200 feedback записей + 10 verified KB-паттернов.

**Spec:** `docs/superpowers/specs/2026-03-21-advisor-phase5-auto-mode-design.md`

---

## File Structure

```
# CREATE
agents/oleg/services/advisor_auto.py       # Auto-threshold, auto-verification, deprecation logic
agents/oleg/services/seasonal_adapter.py   # Seasonal shift detection

# MODIFY
agents/oleg/services/advisor_feedback.py   # + pattern stats aggregation for auto-decisions
agents/oleg/app.py                         # Telegram handlers for auto-suggestions
shared/signals/kb_patterns.py             # + deactivate_pattern(), reactivate_pattern()
agents/oleg/storage/state_store.py         # + threshold_change_log table (audit)

# TESTS
tests/agents/oleg/services/test_advisor_auto.py
tests/agents/oleg/services/test_seasonal_adapter.py
```

---

## Batch A: Auto-Threshold

### Task 1: Threshold analysis engine

**Files:** Create `agents/oleg/services/advisor_auto.py`

- [ ] `analyze_threshold_effectiveness(signal_type, days=30) -> dict` — calculates useful_rate, suggests threshold change
- [ ] Rules: useful_rate < 30% → suggest +20%, useful_rate > 80% → optimal, inaccurate_rate > 40% → advisor problem
- [ ] `generate_threshold_suggestions() -> list[dict]` — batch analysis for all signal types with >= 10 feedbacks

### Task 2: Threshold change audit log

**Files:** Modify `agents/oleg/storage/state_store.py`

- [ ] Add `threshold_change_log` table: pattern_name, old_threshold, new_threshold, reason, applied_by (auto/manual)
- [ ] `log_threshold_change()` method

### Task 3: Telegram flow for threshold suggestions

**Files:** Modify `agents/oleg/app.py`

- [ ] Weekly: send threshold suggestions with `[Применить] [Отклонить] [Другое значение]`
- [ ] Handle callbacks → update kb_patterns → log change

---

## Batch B: Auto-Verification & Deprecation

### Task 4: Auto-verification engine

**Files:** Add to `agents/oleg/services/advisor_auto.py`

- [ ] `check_auto_verification() -> list[dict]` — find patterns ready for verification
- [ ] Criteria: trigger_count >= 3, useful_rate >= 60%, age >= 14 days, no conflicts
- [ ] Uses `check_kb_rules` for conflict detection

### Task 5: Pattern deprecation engine

**Files:** Add to `agents/oleg/services/advisor_auto.py`, modify `shared/signals/kb_patterns.py`

- [ ] `check_deprecation_candidates() -> list[dict]` — find patterns to deactivate
- [ ] Criteria: no triggers 60 days OR useful_rate < 20% with >= 5 feedback OR rejected > 3 times
- [ ] `deactivate_pattern(pattern_name)` — set verified=false (reversible)
- [ ] `reactivate_pattern(pattern_name)` — set verified=true

### Task 6: Telegram batch management

**Files:** Modify `agents/oleg/app.py`

- [ ] "3 паттерна готовы к верификации" → `[Подтвердить все] [По одному] [Пропустить]`
- [ ] "Паттерн X деактивирован" → `[Восстановить] [Удалить] [OK]`

---

## Batch C: Seasonal Adaptation

### Task 7: Seasonal shift detector

**Files:** Create `agents/oleg/services/seasonal_adapter.py`

- [ ] `detect_seasonal_shift(signal_type) -> Optional[dict]` — compare current month vs 3-month baseline
- [ ] Requires >= 6 months of data in recommendation_log
- [ ] Returns: suggested temporary threshold, period, confidence

### Task 8: Seasonal threshold application

**Files:** Modify `shared/signals/kb_patterns.py`, `agents/oleg/app.py`

- [ ] Temporary threshold override mechanism (expires after period)
- [ ] Telegram notification: "Сезонная корректировка: high_drr 12% → 18% до конца января"
- [ ] Auto-revert when period ends

### Task 9: Tests

**Files:** Create test files

- [ ] `test_advisor_auto.py` — threshold analysis, auto-verification, deprecation
- [ ] `test_seasonal_adapter.py` — seasonal shift detection, temporary overrides
- [ ] Mock recommendation_log and feedback data for all scenarios
