#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env.local ] || { cp .env.example .env.local; echo "Created .env.local from template — set VITE_API_KEY"; }
pnpm install --frozen-lockfile
pnpm dev
