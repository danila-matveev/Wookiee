# Wookiee Hub — Project Cleanup v2

**Date:** 2026-04-13
**Status:** Approved
**Supersedes:** 2026-04-03-project-restructuring-design.md
**Goal:** Удалить весь мусор из проекта, извлечь полезные знания из Oleg Agent, описать все скиллы/сервисы/инструменты.

---

## 1. Решения пользователя

- **Все бинарные файлы** (PDF, Excel, PNG, DOCX) — УДАЛИТЬ, кроме: финальных аудитов логистики + исходных примеров
- **Oleg Agent** — УДАЛИТЬ код, извлечь аналитические знания для скиллов, оставить документацию
- **Скиллы** — ВСЕ оставить, документировать (это основной рабочий инструмент)
- **Глобальные скиллы** — оставить в проекте (используются)
- **.agents/, .kiro/, .superpowers/** — разобраться и почистить
- **Planning/specs мусор** — удалить завершённые/неактуальные

---

## 2. Полный список удаления

### 2.1 Корневые бизнес-документы (УДАЛИТЬ ВСЕ)

```
2026_Договор купли-продажи Familia -Чернецкая.docx     # 50K
Экосбор_ИП_Медведева_2025.xlsx                          # 11K
Экосбор_ООО_Вуки_2025.xlsx                              # 11K
Запрос_сведений_для_подготовки_отчетности_по_экосбору.xlsx  # 17K
Условия поставки Покупателя (статус РЦ).pdf             # 1.1M
agent-dashboard-full.png                                 # 421K
mockup-full-page.png                                     # 421K
CleanShot 2026-03-28 at 15.28.34@2x.png                # 235K
scripts.txt                                              # 69K (shell history)
```

### 2.2 Logistics Audit бинарные файлы

**УДАЛИТЬ:**
```
services/logistics_audit/Аудит логистики 2026-01-01 — 2026-03-23.xlsx        # 124M — старый полный аудит
services/logistics_audit/ООО_Вуки_проверка_логистики_05_01_01_02.xlsx        # 55M — промежуточный
services/logistics_audit/ООО Wookiee — Перерасчёт логистики (v2).xlsx        # 1.3M — черновик v2
services/logistics_audit/Расчет переплаты по логистике.pdf                    # 634K
services/logistics_audit/Рекомендации к изменениям в расчете логистики.pdf    # 342K
```

**ОСТАВИТЬ:**
```
services/logistics_audit/ООО Wookiee — Перерасчёт логистики (v2-final).xlsx  # 8.6M — ФИНАЛЬНЫЙ
services/logistics_audit/ИП Фисанов. Проверка логистики...Итоговый.xlsx      # 24M — ИТОГОВЫЙ ИП
services/logistics_audit/ИП Фисанов — Исправленный расчёт логистики (v2).xlsx # 172K — исправленный
services/logistics_audit/Тарифы на логискику.xlsx                             # 882K — справочник тарифов
```

### 2.3 Localization & other бинарные

**УДАЛИТЬ ВСЕ:**
```
services/wb_localization/data/reports/*.xlsx              # 2 файла, фев 2026
services/wb_localization/Отчеты готовые/                  # 6 файлов, мар 2026
docs/database/POWERBI DATA SAMPLES/*.xlsx                # 2 файла
docs/archive/agents/vasily/docs/wb_references/*.pdf      # 2 файла, 3.7M
docs/archive/agents/vasily/docs/wb_references/*.png      # 2 файла
docs/future/agent-ops-dashboard/mockups/*.png            # 1 файл, 3.1M
wookiee-hub/mockups/*.png                                # 2 файла, 5.5M
wookiee-hub/e2e-*.png                                    # 5 файлов
wookiee-hub/планы/референсы-otveto/                      # 12 файлов, 1.5M
```

### 2.4 Oleg Agent

**Извлечь → shared/services/ (нужно для MCP):**
```
agents/oleg/services/agent_tools.py      → shared/services/agent_tools.py
agents/oleg/services/price_tools.py      → shared/services/price_tools.py
agents/oleg/services/marketing_tools.py  → shared/services/marketing_tools.py
agents/oleg/services/funnel_tools.py     → shared/services/funnel_tools.py
```

**Документировать (создать docs/archive/oleg-v2-architecture.md):**
- Архитектура: 5 ролей (Reporter, Marketer, Funnel Analyzer, Validator, Advisor)
- ReAct loop + circuit breaker
- Orchestrator decision flow
- Какие аналитические знания были в промптах (извлечь в скиллы)

**УДАЛИТЬ всё остальное в agents/oleg/:**
- orchestrator/, executor/, pipeline/, storage/, anomaly/, playbooks/, watchdog/
- data/ (SQLite DBs, price reports JSON)
- logs/ (oleg.log 5.5M, oleg_v2.log 242K)
- Оставить только README.md с ссылкой на архитектурный док

### 2.5 Устаревший код (из первого spec, всё ещё актуально)

```
services/dashboard_api/                    # Удалить целиком
deploy/Dockerfile.vasily_api              # Код не существует
deploy/Dockerfile.dashboard_api           # Удаляем с dashboard_api
deploy/deploy-v3-migration.sh             # V3 удалена
docker-compose.yml → vasily-api service   # Убрать из конфига
docker-compose.yml → dashboard-api service # Убрать из конфига
docs/archive/retired_agents/lyudmila/     # 3.2M ретайрнутый агент
.playwright-mcp/                           # 30+ автосгенерированных файлов
```

### 2.6 Planning/specs мусор

```
.planning/archive/v1.0/                    # 80+ файлов
.planning/research/                        # 5 файлов
.planning/milestones/v2.0-phases/          # ~30 файлов
.superpowers/brainstorm/                   # Кэш старой сессии
docs/future/agent-ops-dashboard/           # Нереализованная фича
docs/plans/2026-02-25-dashboard-tz.md
docs/plans/2026-02-25-db-audit-results.md
docs/plans/2026-04-business-plan.md        # Черновик (есть final)
docs/superpowers/specs/2026-03-19-multi-agent-redesign.md
docs/superpowers/specs/2026-03-21-smart-conductor-design.md
docs/superpowers/specs/2026-03-25-vasily-localization-full-description.md
```

### 2.7 Dead code

```
shared/data_layer/quality.py → validate_wb_data_quality()  # 0 использований
```

---

## 3. Новые директории — что это

| Директория | Что | Действие |
|-----------|-----|----------|
| `.agents/skills/` | Внешние скиллы Vercel Labs (agent-browser, slack, dogfood, etc.) | Оставить — устанавливаются автоматически |
| `.kiro/skills/` | Symlinks на .agents/skills/ | Оставить — автоматически управляется |
| `.superpowers/brainstorm/` | Кэш brainstorm-сессии от 26 мар | УДАЛИТЬ |
| `skills-lock.json` | Lock-файл для .agents/ скиллов | Оставить |

---

## 4. Обновление docker-compose.yml

Удалить сервисы:
- `vasily-api` (код не существует)
- `dashboard-api` (services/dashboard_api удалён)

Обновить `wookiee-oleg`:
- После извлечения services → shared/services/, обновить volume mount

---

## 5. Обновление MCP-серверов

После переноса `agents/oleg/services/` → `shared/services/`:
- `mcp_servers/wookiee_data/server.py` — обновить import path
- `mcp_servers/wookiee_price/server.py` — обновить import path  
- `mcp_servers/wookiee_marketing/server.py` — обновить import path

---

## 6. Action Plan

### Phase 1: Удаление бинарного мусора (~200MB)
Удалить всё из п.2.1, 2.2 (помеченное УДАЛИТЬ), 2.3. Коммит.

### Phase 2: Удаление устаревшего кода и planning мусора
Удалить всё из п.2.5, 2.6, 2.7, п.3 (.superpowers/brainstorm/). Коммит.

### Phase 3: Извлечение Oleg services → shared/services/
Переместить 4 файла tools, обновить импорты в MCP-серверах. Коммит.

### Phase 4: Извлечение знаний из Oleg + архивация
Прочитать все промпты/playbooks Oleg, извлечь аналитические знания.
Создать docs/archive/oleg-v2-architecture.md. Удалить остальное. Коммит.

### Phase 5: Обновление Docker
Убрать vasily-api, dashboard-api из docker-compose. Удалить Dockerfiles. Коммит.

### Phase 6: Добавление .gitignore правил
Добавить правила для предотвращения повторного накопления мусора:
```gitignore
# Business documents — не хранить в репо
*.xlsx
*.docx
*.pdf
!services/logistics_audit/*final*.xlsx
!services/logistics_audit/*Итоговый*.xlsx
!services/logistics_audit/*Тарифы*.xlsx

# Screenshots and mockups
*.png
!wookiee-hub/public/**/*.png

# Generated data
agents/oleg/data/
agents/oleg/logs/
.playwright-mcp/
.superpowers/brainstorm/
```

### Phase 7: PROJECT_MAP.md + READMEs
Корневая карта проекта. README для каждого модуля. Коммит.

---

## 7. Рекомендации по работе с файлами в будущем

1. **Бинарные файлы** → Google Drive, не в git. Скилл `/gws-drive` для загрузки
2. **Отчёты/аудиты** → Notion или Google Sheets, не .xlsx в репо
3. **Скриншоты** → Временные, не коммитить. Если нужны для документации — docs/images/ с .gitkeep
4. **Логи агентов** → Supabase (services/observability), не файлы
5. **Бизнес-документы** → Google Drive папка "Wookiee/Документы"
6. **.gitignore** — обновить для блокировки типичных мусорных расширений
