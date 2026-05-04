#!/bin/bash
# Wrapper для запуска headhunter-mcp-server из Claude Code (.mcp.json).
# Загружает HH_* credentials из Wookiee/.env и стартует Python-сервер из соседней папки.
# Так credentials остаются в .env (gitignored), а .mcp.json не содержит секретов.

set -e

WOOKIEE_DIR="/Users/danilamatveev/Projects/Wookiee"
HH_DIR="/Users/danilamatveev/Projects/headhunter-mcp-server"

if [ -f "$WOOKIEE_DIR/.env" ]; then
  # Экспортируем только HH_* переменные, чтобы не споткнуться о невалидные
  # bash-имена в .env (например, X-Mpstats-TOKEN с дефисом).
  while IFS='=' read -r key value; do
    [ -n "$key" ] && export "$key=$value"
  done < <(grep -E '^HH_[A-Z_]+=' "$WOOKIEE_DIR/.env")
fi

cd "$HH_DIR"
exec ./venv/bin/python server.py
