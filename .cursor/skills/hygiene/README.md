# /hygiene

Daily repo hygiene routine for the Wookiee project.

## What it does

Scans for common drift, fixes safe stuff automatically, opens PRs for ambiguous decisions, and pings Telegram only when human attention is needed.

| Bucket | Examples |
|---|---|
| auto | unpushed plans/specs, iCloud dupes, pycache leaks, gitignore violations, skill registry drift, cross-platform skill sync, empty dirs |
| ask-user | orphan imports, orphan docs, broken doc links, missing READMEs, stale branches, structure deviations, obsolete tracked files |
| security | leaked secrets in tracked files, `.env` accidentally tracked, `.env.example` containing real-looking values |

## How to invoke

```bash
/hygiene                   # full run
/hygiene --dry-run         # scan + classify only
/hygiene --check security-scan   # one check only
```

## Production schedule

Runs automatically at **00:00 São Paulo (UTC-3)** every day via GitHub Actions (`.github/workflows/hygiene-daily.yml`). Triggerable on-demand via `Actions → Hygiene Daily → Run workflow`.

## Notifications

- **Cloudflare Pages**: every run produces an article (`https://wookiee-hygiene-YYYY-MM-DD.pages.dev`).
- **Telegram (`@matveevos_head_bot`)**: alerts ONLY when ask_count > 0 OR security_count > 0. Clean runs → silent (just Cloudflare).

## Files

- `SKILL.md` — main skill (7-phase orchestrator).
- `prompts/detect.md` — exact scan commands per check.
- `prompts/classify.md` — bucket-routing rules.
- `prompts/publish.md` — Cloudflare + Telegram templates.
- `../hygiene-config.yaml` — config (cron, whitelists, defaults).

## Spec & rationale

`docs/superpowers/specs/2026-04-27-hygiene-skill-design.md`
