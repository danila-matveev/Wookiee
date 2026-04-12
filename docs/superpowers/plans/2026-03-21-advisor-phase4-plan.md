# Advisor Phase 4 — Self-Learning & Feedback Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Замкнуть feedback loop: пользователь оценивает рекомендации в Telegram → система анализирует эффективность → паттерны можно подтверждать/отклонять/тюнить через Telegram.

**Prerequisites:** Phase 3 завершена + 2-3 месяца работы + минимум 50 записей в recommendation_log.

**Spec:** `docs/superpowers/specs/2026-03-21-advisor-phase4-self-learning-design.md`

---

## File Structure

```
# MODIFY
agents/oleg/storage/state_store.py         # + recommendation_feedback table
agents/oleg/app.py                         # Telegram callback handlers for feedback + pattern confirmation
agents/oleg/orchestrator/orchestrator.py   # Send pattern confirmation + feedback buttons
shared/signals/kb_patterns.py             # + update_pattern_threshold()

# CREATE
agents/oleg/services/advisor_feedback.py   # Feedback analysis + effectiveness report

# TESTS
tests/agents/oleg/services/test_advisor_feedback.py
tests/agents/oleg/storage/test_recommendation_feedback.py
```

---

## Batch A: Feedback Infrastructure

### Task 1: Add recommendation_feedback table to StateStore

**Files:** Modify `agents/oleg/storage/state_store.py`

- [ ] Add `recommendation_feedback` table to `init_db()`
- [ ] Add `log_feedback_on_recommendation(log_id, rec_idx, signal_type, feedback, comment)` method
- [ ] Add `get_feedback_stats(signal_type, days) -> dict` method
- [ ] Tests: `tests/agents/oleg/storage/test_recommendation_feedback.py`

### Task 2: Telegram inline buttons for recommendation feedback

**Files:** Modify `agents/oleg/app.py`, `agents/oleg/orchestrator/orchestrator.py`

- [ ] After recommendations block in report, add inline keyboard: `[👍 Полезно] [👎 Неточно] [🤔 Не актуально]`
- [ ] Callback data format: `rec_feedback:{log_id}:{rec_idx}:{feedback_type}`
- [ ] Handle callback → write to `recommendation_feedback` → send confirmation
- [ ] Pass `recommendation_log_id` from orchestrator to Telegram layer

---

## Batch B: Pattern Management

### Task 3: Pattern confirmation via Telegram

**Files:** Modify `agents/oleg/app.py`, `agents/oleg/orchestrator/orchestrator.py`

- [ ] When advisor proposes new_patterns, send Telegram message with inline buttons
- [ ] Buttons: `[✅ Подтвердить] [❌ Отклонить] [📝 Изменить порог]`
- [ ] Callbacks: update `hub.kb_patterns` (verified=true / DELETE / ask new threshold)
- [ ] "Изменить порог" → follow-up message asking for value → update trigger_condition

### Task 4: Threshold tuning command

**Files:** Modify `agents/oleg/app.py`, add to `shared/signals/kb_patterns.py`

- [ ] `/threshold <pattern_name> <new_value>` command in Telegram
- [ ] `update_pattern_threshold(pattern_name, new_threshold)` in kb_patterns.py
- [ ] Validation: only verified patterns, threshold > 0
- [ ] Confirmation message: "Порог для X изменён: Y% → Z%"

---

## Batch C: Effectiveness Analysis

### Task 5: Advisor effectiveness service

**Files:** Create `agents/oleg/services/advisor_feedback.py`

- [ ] `generate_effectiveness_report(days=7) -> dict` — aggregates recommendation_log + feedback
- [ ] Returns: total_runs, avg_signals, validation_pass_rate, top_signal_types, feedback_summary, unverified_count
- [ ] `get_pattern_effectiveness(pattern_name, days=30) -> dict` — per-pattern stats

### Task 6: Weekly effectiveness report integration

**Files:** Modify `agents/oleg/orchestrator/orchestrator.py`

- [ ] Add effectiveness section to weekly report synthesis
- [ ] Include: signal stats, validation rate, feedback summary
- [ ] Conditional: only if recommendation_log has >= 5 entries for the period

### Task 7: Tests for effectiveness analysis

**Files:** Create `tests/agents/oleg/services/test_advisor_feedback.py`

- [ ] Test report generation with mock data
- [ ] Test per-pattern effectiveness calculation
- [ ] Test edge cases: no data, no feedback
