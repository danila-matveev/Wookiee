---
description: Создать PR с auto-merge — Claude закрывает задачу, GitHub мерджит после CI
---

Создай Pull Request для текущей feature-ветки с включённым auto-merge.

## Шаги

1. Проверь что ты НЕ на main — если на main, выйди с ошибкой и подскажи создать feature-ветку
2. Если есть uncommitted — закоммить с описательным сообщением (одна строка subject + опционально body)
3. Запушь ветку: `git push -u origin $(git branch --show-current)`
4. Создай PR через `gh pr create --title "..." --body "..."` с:
   - Title: чёткий summary (< 70 символов)
   - Body: ## Summary, ## Test plan, Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
5. Включи auto-merge: `gh pr merge <num> --auto --squash --delete-branch`
6. Верни пользователю URL PR'а с комментарием «GitHub смерджит сам когда CI зелёный, можно идти дальше»

## Важно

- Не жди merge, не блокируй пользователя — auto-merge сам сработает
- Если CI красный — PR не смерджится, GitHub отправит уведомление
- Эта команда — единственный способ legitimately залить работу в main
