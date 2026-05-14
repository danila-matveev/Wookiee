---
name: night-coordinator
description: Ночной оркестратор — собирает JSON-репорты от /hygiene и /code-quality-scan, применяет известные решения из .hygiene/decisions.yaml, чинит SAFE-находки по whitelist, кладёт NEEDS_HUMAN в .hygiene/queue.yaml, открывает ОДИН PR за ночь с auto-merge. Запускается крон-задачей в 04:00 UTC после хайдиена и квалити-скана.
---

# /night-coordinator

Запускается через GitHub Actions cron 04:00 UTC. Не вызывается вручную пользователем.

## Что делает

1. **Читает отчёты за сегодня** из `.hygiene/reports/`:
   - `hygiene-YYYYMMDD.json` (от /hygiene-autofix)
   - `code-quality-YYYYMMDD.json` (от /code-quality-scan)
   - `coverage-YYYYMMDD.json` (от /test-coverage-check, если уже есть)

2. **Загружает память решений** `.hygiene/decisions.yaml`. Для каждой находки:
   - Если есть совпадение с прошлым `decision: delete/keep/exclude` и оно не устарело (не позже `expires`) → применяет это решение, в очередь не кладёт.
   - Если совпадение есть, но устарело → находку обрабатывает заново.

3. **Классифицирует** оставшиеся:
   - **SAFE** (whitelist из плана §6) → чинит сам через `shared/hygiene.autofix.apply_finding()`:
     * orphan-imports (`git rm` если 0 grep refs)
     * broken-doc-links (правка если target существует на относительном пути)
     * skill-registry-drift (rsync из mirror)
     * stray binaries вне whitelist (`git rm --cached`)
     * gitignore-violations (`git rm --cached`)
   - **NEEDS_HUMAN** → добавляет в `.hygiene/queue.yaml` (если не уже там)

4. **Проверка coverage gate**: читает `coverage-YYYYMMDD.json` от /test-coverage-check (если файл есть). Если в нём `blocking: true` (покрытие упало >2 п.п.) → **не пушит фиксы**, оставляет всё на завтра, шлёт Telegram-алерт.

5. **Read-only mode check**: читает `.hygiene/config.yaml`. Если `read_only: true` (дефолт первой недели):
   - **Не пушит**, не открывает PR, не вызывает `gh pr merge`
   - Шлёт Telegram-сводку: «Я бы починил вот это (список), задал бы вот эти вопросы (список из queue.yaml)»
   - Записывает ход работы в `.hygiene/reports/coordinator-dry-run-YYYYMMDD.json`
   - Завершается

6. **Иначе (продакшн режим)**:
   - Создаёт ветку `night-devops/YYYY-MM-DD`
   - Коммитит все применённые фиксы атомарно (один коммит на каждый тип находки, для удобного отката)
   - Логирует каждый коммит в Supabase `fix_log` (через `scripts/nightly/supabase_fix_log.py` если есть, иначе пропускает)
   - Пушит ветку
   - Создаёт PR через `gh pr create` с описанием на простом русском
   - Включает auto-merge: `gh pr merge --auto --squash --delete-branch`
   - Если в `.hygiene/queue.yaml` остались NEEDS_HUMAN — шлёт Telegram digest через `shared.telegram_digest.render_needs_human_digest()` + `send_digest()`
   - Если очередь пустая — Telegram молчит (или шлёт heartbeat в 05:00, это другой скилл)

## Лимиты

- Максимум **10 SAFE-фиксов за один прогон**. Остальное переносится на завтра.
- Wall clock 20 минут (timeout-minutes в workflow).
- Если что-то падает на любом шаге — Telegram-алерт через `shared.telegram_digest.render_failure_alert()`, выход с ненулевым кодом, никаких частичных пушей.

## Конкаррентность

Workflow `.github/workflows/night-coordinator.yml` использует группу `night-devops`. Гарантировано не работает параллельно с другими ночными воркфлоу.

## Файлы

- `runner.py` — точка входа, импортирует `shared.hygiene`, оркеструет
- `README.md` — для разработчика
