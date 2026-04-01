# Requirements: Wookiee Reports v2.0

**Defined:** 2026-03-30
**Core Value:** Одна простая рабочая система аналитических отчётов — стабильная генерация каждый день

## v2.0 Requirements

### Очистка (CLEAN)

- [x] **CLEAN-01**: agents/v3/ полностью удалён (все файлы, директории, зависимости)
- [x] **CLEAN-02**: Зависимости langchain/langgraph/langchain-openai удалены из requirements
- [x] **CLEAN-03**: V3-related docs, plans, specs удалены из docs/
- [x] **CLEAN-04**: Docker-compose обновлён — контейнер запускает V2 систему напрямую, без V3

### Отчёты (RPT)

- [ ] **RPT-01**: Финансовый ежедневный отчёт генерируется корректно с полными данными
- [ ] **RPT-02**: Финансовый еженедельный отчёт генерируется с глубоким анализом (тренды, модели, гипотезы)
- [ ] **RPT-03**: Финансовый ежемесячный отчёт генерируется с максимальной глубиной (P&L, юнит-экономика, стратегия)
- [ ] **RPT-04**: Маркетинговый еженедельный отчёт генерируется корректно
- [ ] **RPT-05**: Маркетинговый ежемесячный отчёт генерируется корректно
- [ ] **RPT-06**: Воронка продаж еженедельный отчёт генерируется корректно
- [ ] **RPT-07**: ДДС (finolog) еженедельный отчёт генерируется корректно
- [ ] **RPT-08**: Локализация еженедельный отчёт генерируется корректно

### Надёжность (REL)

- [x] **REL-01**: Pre-flight проверка данных перед запуском — если данных нет, отчёт не запускается
- [x] **REL-02**: Retry при пустом/неполном ответе LLM (до 2 повторов)
- [x] **REL-03**: Валидация полноты секций перед публикацией — пустой отчёт не публикуется в Notion
- [x] **REL-04**: Graceful degradation — если секция не может быть заполнена, пишется причина
- [x] **REL-05**: Каждый опубликованный отчёт содержит все обязательные секции для своего типа
- [x] **REL-06**: Один отчёт = одна страница в Notion (upsert по период+тип, без дублей)
- [x] **REL-07**: Telegram-уведомление отправляется ТОЛЬКО после успешной валидации и публикации в Notion

### Плейбуки (PLAY)

- [x] **PLAY-01**: playbook.md разбит на модули (core + templates + rules) без потери бизнес-правил
- [x] **PLAY-02**: Каждый тип отчёта загружает только релевантные модули плейбука
- [x] **PLAY-03**: Глубина анализа настроена по периоду: daily=компактный, weekly=глубокий, monthly=максимальный

### Запуск и доставка (SCHED)

- [x] **SCHED-01**: Простые cron-задачи для запуска всех 8 типов отчётов
- [x] **SCHED-02**: Отчёт публикуется в Notion с правильными properties (период, тип, статус)
- [x] **SCHED-03**: Telegram-уведомление отправляется после публикации (без бота с командами)
- [x] **SCHED-04**: Русские названия типов отчётов в Notion и Telegram

### Документация и зачистка (DOC)

- [ ] **DOC-01**: Полная документация системы — архитектура, компоненты, типы отчётов, расписания, доставка
- [ ] **DOC-02**: На сервере удалены все лишние контейнеры, запущена только одна рабочая система
- [ ] **DOC-03**: В репозитории удалён весь мёртвый код, неиспользуемые скрипты, устаревшие docs/plans/specs

### Верификация (VER)

- [ ] **VER-01**: Все 8 типов отчётов сгенерированы и проверены на реальных данных
- [ ] **VER-02**: Лучшие отчёты из Notion найдены и используются как эталон качества
- [x] **VER-03**: Структура отчётов единообразна с toggle-заголовками

## Отложено (v3.0)

### Алерты и мониторинг

- **ALERT-01**: Автоматические алерты при резких изменениях метрик (маржа, ДРР, выручка)
- **ALERT-02**: Watchdog мониторинг здоровья системы

### Самообучение

- **LEARN-01**: Persistent Instructions из Notion feedback
- **LEARN-02**: Prompt Tuner — автоматическая настройка промптов

### Telegram бот

- **BOT-01**: Telegram бот с командами (/report_daily, /report_weekly и т.д.)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Ценовой анализ (отдельный отчёт) | Не работал, не приоритет |
| LangGraph микроагенты | Сложно, ненадёжно, дорого — удаляем |
| Confidence scoring per agent | Overcomplicated для V2 архитектуры |
| 24 параллельных микроагента | 1 Reporter надёжнее чем 7 параллельных агентов |
| APScheduler в Python | Cron проще и надёжнее |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLEAN-01 | Phase 1 | Complete |
| CLEAN-02 | Phase 1 | Complete |
| CLEAN-03 | Phase 1 | Complete |
| CLEAN-04 | Phase 1 | Complete |
| PLAY-01 | Phase 2 | Complete |
| PLAY-02 | Phase 2 | Complete |
| PLAY-03 | Phase 2 | Complete |
| VER-03 | Phase 2 | Complete |
| REL-01 | Phase 3 | Complete |
| REL-02 | Phase 3 | Complete |
| REL-03 | Phase 3 | Complete |
| REL-04 | Phase 3 | Complete |
| REL-05 | Phase 3 | Complete |
| REL-06 | Phase 3 | Complete |
| REL-07 | Phase 3 | Complete |
| SCHED-01 | Phase 4 | Complete |
| SCHED-02 | Phase 4 | Complete |
| SCHED-03 | Phase 4 | Complete |
| SCHED-04 | Phase 4 | Complete |
| RPT-01 | Phase 5 | Pending |
| RPT-02 | Phase 5 | Pending |
| RPT-03 | Phase 5 | Pending |
| RPT-04 | Phase 5 | Pending |
| RPT-05 | Phase 5 | Pending |
| RPT-06 | Phase 5 | Pending |
| RPT-07 | Phase 5 | Pending |
| RPT-08 | Phase 5 | Pending |
| VER-01 | Phase 5 | Pending |
| VER-02 | Phase 5 | Pending |
| DOC-01 | Phase 6 | Pending |
| DOC-02 | Phase 6 | Pending |
| DOC-03 | Phase 6 | Pending |

**Coverage:**
- v2.0 requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 after roadmap creation*
