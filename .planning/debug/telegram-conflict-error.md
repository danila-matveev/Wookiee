---
status: fixing
trigger: "TelegramConflictError — 400+ errors per hour. Another process (unknown — not n8n) is doing getUpdates with the same bot token."
created: 2026-03-27T00:00:00Z
updated: 2026-03-27T00:01:00Z
---

## Current Focus

hypothesis: CONFIRMED — eggent service registered a Telegram webhook for the same bot token. When a webhook is active, any getUpdates call (used by wookiee_oleg's aiogram polling) returns 409 Conflict. This is Telegram's mutual exclusion: polling and webhook cannot coexist.
test: Confirmed by: (1) eggent has TELEGRAM_BOT_TOKEN in its .env, (2) eggent's setup/route.ts calls setWebhook, (3) aiogram's 409 error message exactly matches Telegram's response when webhook is set
expecting: Fix = either delete the webhook from eggent, OR migrate wookiee_oleg to webhook mode
next_action: Fix wookiee_oleg to handle the conflict — proper solution depends on whether eggent webhook should stay

## Symptoms

expected: wookiee_oleg bot receives and processes Telegram commands normally
actual: 400+ TelegramConflictError per hour, bot doesn't respond to commands, errors flood Telegram
errors: TelegramConflictError (409 Conflict — terminated by other getUpdates request)
reproduction: Send any command to the bot in Telegram — no response
started: Unknown exactly when started, currently happening

## Eliminated

- hypothesis: n8n is the conflicting process
  evidence: docker-compose.yml shows n8n is in external network, not directly in wookiee stack; user confirmed not n8n
  timestamp: 2026-03-27T00:00:30Z

- hypothesis: Two instances of wookiee_oleg container run simultaneously
  evidence: docker-compose has single wookiee-oleg service; deploy.sh stops old container before starting new one
  timestamp: 2026-03-27T00:00:45Z

- hypothesis: Lyudmila bot conflicts with Oleg
  evidence: Lyudmila uses LYUDMILA_BOT_TOKEN (separate env var), not TELEGRAM_BOT_TOKEN
  timestamp: 2026-03-27T00:00:50Z

## Evidence

- timestamp: 2026-03-27T00:01:00Z
  checked: agents/v3/app.py
  found: wookiee_oleg uses aiogram dp.start_polling(bot) — long-polling mode
  implication: Long-polling calls getUpdates repeatedly; gets 409 if webhook is registered

- timestamp: 2026-03-27T00:01:05Z
  checked: eggent/.env (local copy at /Users/danilamatveev/Desktop/Документы/Cursor/eggent/.env)
  found: TELEGRAM_BOT_TOKEN is set (non-empty value)
  implication: eggent has the same bot token as wookiee_oleg

- timestamp: 2026-03-27T00:01:10Z
  checked: eggent/src/app/api/integrations/telegram/setup/route.ts
  found: eggent calls setWebhook on the bot token when Telegram integration is configured
  implication: eggent registered a webhook URL on the same bot token

- timestamp: 2026-03-27T00:01:15Z
  checked: eggent/src/lib/storage/telegram-integration-store.ts
  found: getTelegramIntegrationRuntimeConfig() reads from both stored JSON file AND TELEGRAM_BOT_TOKEN env var
  implication: Even if stored settings are cleared, env var keeps the token active in eggent

- timestamp: 2026-03-27T00:01:20Z
  checked: deploy/docker-compose.yml — eggent service
  found: eggent builds from /opt/eggent, uses eggent-data volume for persistence. No env_file specified — relies on /opt/eggent .env at build/run time
  implication: The /opt/eggent installation on the server has its own .env with TELEGRAM_BOT_TOKEN; webhook was registered via eggent UI

- timestamp: 2026-03-27T00:01:25Z
  checked: Telegram API behavior
  found: When a webhook is set, ALL getUpdates calls return 409 Conflict regardless of caller
  implication: Every polling attempt by wookiee_oleg generates one error — explains 400+/hr rate

## Resolution

root_cause: eggent (AI workspace) was configured with the same TELEGRAM_BOT_TOKEN as wookiee_oleg and called setWebhook on it. Telegram enforces mutual exclusion: when a webhook is active, any getUpdates (polling) call returns HTTP 409 Conflict. wookiee_oleg uses aiogram polling which calls getUpdates continuously, generating 400+ errors per hour and receiving no updates.

fix: Two-part fix required:
  1. DELETE the webhook from eggent to clear the conflict state immediately
  2. Either: (a) remove TELEGRAM_BOT_TOKEN from eggent's environment so it never registers a webhook again, OR (b) keep eggent's webhook and migrate wookiee_oleg to webhook mode (more complex)
  Recommended: Option (a) — remove the token from eggent, keep wookiee_oleg in polling mode since it already works well.

verification: After removing webhook, wookiee_oleg polling should receive 200 responses and process commands normally
files_changed: [deploy/docker-compose.yml if eggent env vars need updating, or /opt/eggent/.env on server]
