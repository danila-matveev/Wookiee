# Pull Request Workflow

Аргумент: $ARGUMENTS (опционально: "wait" — не мержить автоматически)

## Шаги

1. Прочитай AGENTS.md и agent_docs/guides/dod.md
2. Проверь что все изменения закоммичены
3. Обнови agent_docs/development-history.md
4. Создай PR с описанием по формату:
   - Summary (что сделано и зачем)
   - Test plan (как проверить)
5. Если аргумент "wait" — спроси пользователя перед merge
6. Иначе — merge после успешной проверки