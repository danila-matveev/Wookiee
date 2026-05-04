---
name: notebooklm
description: Complete API for Google NotebookLM — create notebooks, add sources, generate podcasts/videos/quizzes/mindmaps, download results. Activates on explicit /notebooklm or intent like "create a podcast about X", "summarize these URLs into a notebook".
triggers:
  - /notebooklm
metadata:
  category: publishing
  status: deprecated
  note: Installed via `notebooklm skill install` (notebooklm-py package). See ~/.claude/skills/notebooklm/SKILL.md for full skill content.
---

# NotebookLM Automation

> **Статус:** deprecated (0 запусков). Скилл установлен через `pip install notebooklm-py && notebooklm skill install`.
> Этот файл — заглушка для project-level registry. Полное содержимое скилла — в `~/.claude/skills/notebooklm/SKILL.md`.

## Быстрый старт

```bash
pip install notebooklm-py
notebooklm skill install   # установит полный SKILL.md в ~/.claude/skills/notebooklm/
notebooklm login           # Google OAuth
```

## Основные команды

| Команда | Описание |
|---------|----------|
| `notebooklm create "Title"` | Создать ноутбук |
| `notebooklm source add <url>` | Добавить источник |
| `notebooklm generate audio "..."` | Генерация подкаста |
| `notebooklm download audio ./out.mp3` | Скачать аудио |
| `notebooklm list` | Список ноутбуков |
