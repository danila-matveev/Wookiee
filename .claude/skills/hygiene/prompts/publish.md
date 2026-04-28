# Hygiene — Publish (Phase 5 + 6 templates)

## Cloudflare article template

Render to `/tmp/hygiene-report-$RUN_ID.md`, then publish via `cloudflare-pub`.

```markdown
# Wookiee Hygiene Run — {YYYY-MM-DD}

**Status:** {clean | N auto-fixed | N need review | security flag}
**Run ID:** `{RUN_ID}`
**Triggered by:** {github_actions | manual | workflow_dispatch}
**Duration:** {DURATION}s
**Tokens used:** ~{TOKENS}

---

## Summary

| Bucket | Count |
|---|---|
| Auto-fixed | {auto_count} |
| Needs review | {ask_count} |
| Security flags | {security_count} |
| Skipped | {skip_count} |

PR: [{pr_branch}]({pr_url}) — {merged | open — needs review | not opened}

---

## Auto-fixed

(Only present if auto_count > 0.)

For each auto finding (grouped by check):

### `{check}` — {N items}

- `{path}` — {reason}. Action: {auto_action_command}.

---

## Needs review

(Only present if ask_count > 0.)

For each ask finding:

### `{check}`: {short label}

**Paths:**
- `{path1}`
- `{path2}`

**Reason:** {reason}
**Suggested action:** {suggested_action}
**Evidence:** {evidence}

---

## Security flags

(Only present if security_count > 0.)

For each security finding:

### 🚨 `{check}` — {severity}

- Path: `{path}`
- Reason: {reason}
- Telegram alert sent at: {timestamp}

(Secret values are never published — only paths.)

---

## Stats

- Phase durations: scan={t1}s, classify={t2}s, act={t3}s, pr={t4}s, publish={t5}s.
- Cron run number: {N} (counted from `tool_runs`).
- Repo state hash (post-run): `{git rev-parse HEAD}`.
```

## Telegram message templates

### Security alert (sent immediately during Phase 3c)

```
🚨 Wookiee Hygiene SECURITY [{YYYY-MM-DD}]
Check: {check}
Path: {path}
Reason: {reason}
Action required: review immediately.
```

### Run summary (Phase 6, only if ask_count > 0 OR security_count > 0)

```
🧹 Wookiee Hygiene {YYYY-MM-DD}
Auto-fixed: {auto_count}
Needs review: {ask_count}
Security flags: {security_count}

Full report: {cloudflare_url}
PR: {pr_url}
```

### Abort alert (cost cap or precondition fail)

```
⚠️ Wookiee Hygiene ABORTED [{YYYY-MM-DD}]
Reason: {reason}
Partial state: {what got done before abort}

Investigate: {cloudflare_url or "no report"}
```

## Constants for templating

| Variable | Source |
|---|---|
| `{YYYY-MM-DD}` | `date -u +%Y-%m-%d` |
| `{RUN_ID}` | `date -u +%Y%m%dT%H%M%SZ` (set at start of run, propagated everywhere) |
| `{cloudflare_url}` | output of `cloudflare-pub` Permanent URL |
| `{pr_url}` | output of `gh pr view --json url` |
| `{auto_count}/{ask_count}/{security_count}/{skip_count}` | from classify Phase 2 |
| `{DURATION}` | `date +%s` end - start |
| `{TOKENS}` | from Anthropic API response usage block |

## Important formatting rules

- Always use Markdown headings (Cloudflare-pub renders them).
- No raw HTML — `cloudflare-pub` strips/escapes some tags.
- Code blocks use triple-backtick + language hint.
- Telegram messages: plain text, no Markdown (Telegram interprets some chars).
- Truncate any field longer than 500 chars to "…(truncated, see Cloudflare report)".
