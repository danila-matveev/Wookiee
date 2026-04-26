# Кросс-платформенный setup: Claude Code + Codex CLI + Cursor

Wookiee-скиллы и MCP-серверы доступны во всех трёх AI-CLI: Claude Code, Codex, Cursor. Работает через [ecosystem-sync](https://github.com/2030ai/2030ai-claudecode-allecosystem-sync) — Claude Code как источник истины, остальные платформы получают симлинки.

## Onboarding нового члена команды

### 1. Установить ecosystem-sync (один раз на машину)

```bash
git clone https://github.com/2030ai/2030ai-claudecode-allecosystem-sync.git ~/.claude/skills/ecosystem-sync
```

### 2. Клонировать репо Wookiee

```bash
git clone <wookiee-repo-url>
cd Wookiee
```

После клона ты сразу получишь:
- `.claude/skills/` — 30 скиллов (источник истины)
- `.cursor/skills/` — относительные симлинки → работают сразу в Cursor
- `.codex/skills/` — относительные симлинки → работают сразу в Codex
- `.mcp.json.example` — шаблон конфигурации MCP-серверов

### 3. Настроить MCP-серверы

```bash
cp .mcp.json.example .mcp.json
# Открой .mcp.json и замени плейсхолдеры на реальные токены:
#   - WB_API_TOKEN (IP, OOO) — Wildberries
#   - FINOLOG_API_TOKEN — Finolog
#   - OZON_CLIENT_ID + OZON_API_KEY — Ozon
# Токены спроси у Данилы (1Password или защищённый канал)
```

> ⚠️ `.mcp.json` в `.gitignore` — никогда не коммитить с реальными токенами.

### 4. Запустить sync для генерации платформенных конфигов

В Claude Code или Codex (в директории Wookiee):

```
запусти ecosystem-sync sync
```

Это создаст:
- `.cursor/mcp.json` — конфиг MCP для Cursor (из твоего `.mcp.json`)
- `.codex/config.toml` — конфиг MCP для Codex (из твоего `.mcp.json`)

Эти файлы тоже в `.gitignore` — у каждого свои токены.

### 5. Установить MCP-server бинарники

В соседних с Wookiee директориях должны лежать:
- `../wildberries-mcp-server/` — собранный (`npm run build`)
- `../finolog-mcp-server/` — собранный
- `../ozon-mcp-server/` — собранный

Или подправь пути в `.mcp.json` под свою структуру.

### 6. Готово

Открой Claude Code, Codex или Cursor в Wookiee — скиллы и MCP сразу работают.

## Как пользоваться

### Claude Code
Слэш-команды: `/finance-report`, `/daily-brief`, `/abc-audit`, `/marketing-report` и т.д.

### Codex CLI
Слэш-команд нет. Просишь агента:
> «Запусти скилл finance-report»
> или
> «Прочитай `.codex/skills/daily-brief/SKILL.md` и выполни»

### Cursor
То же что в Codex — попроси агента запустить скилл по имени.

## Создание нового скилла

Чтобы новый скилл сразу работал на всех платформах:

```bash
# 1. Создать директорию и SKILL.md
mkdir -p .claude/skills/my-new-skill
cat > .claude/skills/my-new-skill/SKILL.md << 'EOF'
---
name: my-new-skill
description: Краткое описание триггеров и того, что делает скилл
user-invocable: true
---

# My New Skill

Инструкция для агента — что и как делать.
EOF

# 2. Создать относительные симлинки для Codex и Cursor
(cd .cursor/skills && ln -s ../../.claude/skills/my-new-skill my-new-skill)
(cd .codex/skills && ln -s ../../.claude/skills/my-new-skill my-new-skill)

# 3. Закоммитить (источник + оба симлинка)
git add .claude/skills/my-new-skill .cursor/skills/my-new-skill .codex/skills/my-new-skill
git commit -m "skills: add my-new-skill"
```

После `git push` коллеги получают новый скилл во всех трёх CLI автоматически — симлинки относительные.

### Альтернатива: автоматизировать через ecosystem-sync

Можно просто создать `.claude/skills/my-new-skill/SKILL.md` и затем выполнить:

```
запусти ecosystem-sync sync
```

Скилл сам найдёт новый скилл и создаст симлинки. Но он сделает их **абсолютными** — чтобы коммитить кросс-платформенно, лучше создавать вручную как выше.

## Добавление нового MCP-сервера

```bash
# 1. Добавить запись в .mcp.json (локально, не коммитить!)
# 2. Обновить .mcp.json.example с плейсхолдером для коллег
# 3. Запустить /ecosystem-sync sync — обновит .cursor/mcp.json и .codex/config.toml
# 4. Закоммитить только .mcp.json.example
```

## Что синхронизируется и что нет

| Что | Источник | Где появляется | Коммитится? |
|---|---|---|---|
| Project-local скиллы | `.claude/skills/<name>/` | `.cursor/skills/`, `.codex/skills/` | ✅ Да (источник + симлинки) |
| Глобальные скиллы (gstack, bitrix-task, finolog, и т.д.) | `~/.claude/skills/` (личный home) | `~/.cursor/skills-cursor/`, `~/.codex/skills/` | ❌ Нет (личное у каждого) |
| Plugin-скиллы (`gsd:*`, `superpowers:*`) | Marketplace через `/plugins` | Только Claude Code | ❌ Каждый ставит сам |
| MCP-серверы | `.mcp.json` | `.cursor/mcp.json`, `.codex/config.toml` | ❌ Шаблон в `.mcp.json.example` |

## Что не работает в Codex (ограничения платформы)

- **HTTP MCP-серверы** — Codex CLI поддерживает только stdio. HTTP-серверы (например `context7`) ставятся как `unsupported` и работают только в Claude Code и Cursor.
- **Слэш-команды** — нет интерфейса `/skill-name`, нужно просить агента по имени.
- **Plugin marketplace** — у Codex свой `codex` CLI marketplace, не Claude. Эквиваленты `gsd:*`, `superpowers:*` ставятся отдельно.

## Если что-то сломалось

```
запусти ecosystem-sync audit
```

Покажет что синхронизировано / что MISSING / есть ли battle-сломанные симлинки. Дальше — `sync`.
