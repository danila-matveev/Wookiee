"""Telegram digest renderer for the nighttime DevOps agent.

Shared module used by both /night-coordinator (Wave A3) and /heartbeat (Wave B4).
All messages — plain Russian, no jargon, no emoji except a single moon glyph
at the start of the heartbeat. Pure-text fallback if rendering fails.

Bot: @wookiee_alerts_bot (the existing shared alerts bot).
Env vars (set in GH Actions secrets):
    TELEGRAM_ALERTS_BOT_TOKEN
    HYGIENE_TELEGRAM_CHAT_ID

See plan §5 for canonical message templates.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Iterable

import requests

from shared.hygiene.schemas import HeartbeatSummary, QueueItem

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
DEFAULT_TIMEOUT = 10
# Telegram hard cap is 4096; we keep most messages well under 1000.
MAX_TG_LEN = 4000
# Heartbeat extra-tight cap per spec (≤500 chars).
MAX_HEARTBEAT_LEN = 500

# Markdown special chars Telegram requires to be escaped in MarkdownV2.
# We use legacy `Markdown` parse mode (less strict) to keep messages readable
# in plain Russian. Only `_`, `*`, `[`, `]`, `` ` `` need handling, and only
# when they appear in user-data segments. Code blocks (triple backticks) are
# allowed verbatim for the /hygiene-resolve copy-paste hint.
_MD_ESCAPE = re.compile(r"([_*\[\]`])")

# Forbidden jargon. Plain check; if present outside parentheses → warn.
# Note: "PR" is whitelisted per plan §5.7 ("Нет английских терминов кроме `PR`").
_FORBIDDEN_JARGON = (
    "commit",
    "коммит",
    "merge",
    "branch",
    "ветка",
    "rebase",
    "stash",
    "diff",
    "hotfix",
)


def _escape_markdown(text: str) -> str:
    """Escape Telegram legacy-Markdown special chars in free text."""
    return _MD_ESCAPE.sub(r"\\\1", text)


def _validate_plain_language(text: str) -> list[str]:
    """Check for forbidden tech jargon. Returns list of violations.

    Per plan §5.7: PR, Claude Code, getattr, filenames OK.
    Other jargon (commit, merge, branch, ветка, коммит) — warn-only.

    Allowed contexts (false-positive guard):
    - inside parentheses (clarification): "(merge запрос)" → skip
    - inside backticks/code: `git merge` → skip
    """
    violations: list[str] = []
    # Strip backtick-quoted content (code) and parenthesised content (clarification).
    stripped = re.sub(r"`[^`]*`", "", text)
    stripped = re.sub(r"\([^)]*\)", "", stripped)
    lower = stripped.lower()
    for term in _FORBIDDEN_JARGON:
        # Use word-boundary-ish check (Cyrillic-safe).
        # \b doesn't behave well with Cyrillic, so check spacing manually.
        pattern = re.compile(rf"(?:^|[\s.,;:!?'\"])({re.escape(term)})(?:$|[\s.,;:!?'\"])", re.IGNORECASE)
        if pattern.search(lower):
            violations.append(term)
    return violations


def _check_language(text: str) -> None:
    """Log warnings if jargon slipped through. Never raises (per spec)."""
    violations = _validate_plain_language(text)
    if violations:
        logger.warning(
            "telegram_digest: plain-language violations detected: %s. "
            "Message will still be sent. Fix the renderer.",
            ", ".join(sorted(set(violations))),
        )


def send_digest(content: str, level: str = "info", chat_id: str | None = None) -> None:
    """Send a Telegram message via @wookiee_alerts_bot.

    Args:
        content: The message body. Plain Russian, optional simple Markdown.
        level: "info" | "warn" | "error" — used only for log severity.
        chat_id: Override target chat id. Default: env HYGIENE_TELEGRAM_CHAT_ID.

    Raises:
        RuntimeError on missing env or Telegram API failure. Caller decides
        retry/swallow.
    """
    token = os.environ.get("TELEGRAM_ALERTS_BOT_TOKEN")
    target_chat = chat_id or os.environ.get("HYGIENE_TELEGRAM_CHAT_ID")
    if not token or not target_chat:
        raise RuntimeError(
            "telegram_digest: missing TELEGRAM_ALERTS_BOT_TOKEN or HYGIENE_TELEGRAM_CHAT_ID env"
        )

    if len(content) > MAX_TG_LEN:
        logger.warning("telegram_digest: message %d chars, truncating to %d", len(content), MAX_TG_LEN)
        content = content[: MAX_TG_LEN - 3] + "..."

    _check_language(content)

    log_fn = {"info": logger.info, "warn": logger.warning, "error": logger.error}.get(level, logger.info)
    log_fn("telegram_digest: sending %d-char message to chat %s", len(content), target_chat)

    try:
        resp = requests.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json={
                "chat_id": target_chat,
                "text": content,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"telegram_digest: HTTP error: {e}") from e

    if resp.status_code != 200:
        raise RuntimeError(
            f"telegram_digest: Telegram API returned {resp.status_code}: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def render_needs_human_digest(queue_items: list[QueueItem]) -> str:
    """Render the 'human attention needed' message in plain Russian.

    Matches plan §5.2 (1 item), §5.3 (3 items), §5.4 (many).
    """
    n = len(queue_items)
    if n == 0:
        return "За ночь всё чисто — делать нечего."

    date_label = _today_ru()
    header = f"За ночь {date_label} прошёлся по репо. Большую часть починил сам, осталось {_word_questions(n)} на твоё решение."
    parts = [header, ""]

    if n == 1:
        item = queue_items[0]
        parts.append(f"— {item.question_ru}")
        parts.append("")
        parts.append("Когда удобно — открой Claude Code и вставь:")
        parts.append("")
        parts.append("    /hygiene-resolve")
        parts.append("")
        default = item.default_after_7d or "безопасный дефолт"
        parts.append(
            f"Если не ответишь — через 7 дней сам применю «{default}», это безопасный путь."
        )
    elif n <= 5:
        for i, item in enumerate(queue_items, 1):
            parts.append(f"{i}) {item.question_ru}")
        parts.append("")
        parts.append("Все можно решить разом одной командой. Открой Claude Code и вставь:")
        parts.append("")
        parts.append("    /hygiene-resolve")
        parts.append("")
        defaults = ", ".join(it.default_after_7d or "—" for it in queue_items)
        parts.append(
            f"Если не ответишь — через 7 дней применю безопасные дефолты ({defaults}), ничего не сломаю."
        )
    else:
        parts.append(
            f"Накопилось {n} вопросов — это много, лучше разобрать вместе. Открой Claude Code и вставь:"
        )
        parts.append("")
        parts.append("    /hygiene-resolve")
        parts.append("")
        parts.append("Самые важные:")
        for item in queue_items[:3]:
            parts.append(f"  • {item.question_ru}")

    return "\n".join(parts)


def render_heartbeat(summary: HeartbeatSummary) -> str:
    """Render the daily heartbeat. Plain Russian, ≤500 chars.

    Style matches the existing /hygiene message that the owner liked:
      🧹 За ночь убрался в репозитории Wookiee.
      <empty line>
      Сам починил: X — описание.
      Оставил тебе на ревью: Y — описание.
      <empty line>
      Покрытие тестами: NN% (без изменений).
      PR #NNN — статус.
    """
    if summary.failure:
        return _truncate(
            "Ночью что-то сломалось.\n\n"
            f"Что не получилось: {summary.failure}\n"
            f"Это значит: фиксы не применил, репо не тронул. Завтра попробую ещё раз.",
            MAX_HEARTBEAT_LEN,
        )

    zero_activity = (
        summary.fixes_applied == 0
        and summary.needs_human_count == 0
        and (summary.pr_number is None or summary.pr_status in (None, "merged"))
    )
    if zero_activity:
        if summary.coverage_pct is not None:
            return _truncate(
                f"За ночь {summary.date_str} всё чисто — делать нечего.\n\n"
                f"Покрытие тестами: {int(round(summary.coverage_pct))}%.",
                MAX_HEARTBEAT_LEN,
            )
        return _truncate(
            f"За ночь {summary.date_str} всё чисто — делать нечего.",
            MAX_HEARTBEAT_LEN,
        )

    lines = [f"За ночь {summary.date_str} прошёлся по репо."]
    lines.append("")

    if summary.fixes_applied > 0:
        examples = ", ".join(summary.fixes_examples[:3]) if summary.fixes_examples else ""
        if examples:
            lines.append(
                f"Сам починил: {_word_things(summary.fixes_applied)} — {examples}."
            )
        else:
            lines.append(f"Сам починил: {_word_things(summary.fixes_applied)}.")

    if summary.needs_human_count > 0:
        lines.append(
            f"Оставил тебе на ревью: {_word_points(summary.needs_human_count)}. "
            "Когда удобно — вставь /hygiene-resolve в Claude Code, спрошу пару вопросов и доделаю."
        )

    bottom: list[str] = []

    if summary.coverage_pct is not None:
        delta = summary.coverage_delta_pp
        if delta is None or abs(delta) < 0.05:
            change = "без изменений"
        elif delta > 0:
            change = f"+{delta:.1f} п.п."
        else:
            change = f"{delta:.1f} п.п."
        bottom.append(
            f"Покрытие тестами: {int(round(summary.coverage_pct))}% ({change})."
        )

    if summary.pr_number and summary.pr_status:
        status_ru = {
            "merged": "уже смерджился",
            "open": "ещё открыт, ждёт CI",
            "failed": "не прошёл CI",
        }.get(summary.pr_status, summary.pr_status)
        bottom.append(f"PR #{summary.pr_number} — {status_ru}.")

    if bottom:
        lines.append("")
        lines.extend(bottom)

    return _truncate("\n".join(lines), MAX_HEARTBEAT_LEN)


def render_failure_alert(failed_skill: str, error: str) -> str:
    """Render a failure alert when a cron job dies. Per plan §5.5."""
    date_label = _today_ru()
    skill_ru = {
        "hygiene": "проверка гигиены",
        "code-quality-scan": "сканер кода",
        "test-coverage-check": "проверка покрытия тестами",
        "night-coordinator": "ночной координатор",
        "heartbeat": "вечерняя сводка",
    }.get(failed_skill, failed_skill)

    # Trim verbose error to ~200 chars
    short_error = error.strip().splitlines()[0][:200] if error else "без подробностей"

    return (
        f"Ночью что-то сломалось.\n"
        f"\n"
        f"Что не получилось: {skill_ru}.\n"
        f"Причина: {short_error}\n"
        f"\n"
        f"Это значит: репо не тронул, фиксы не применял. Завтра попробую ещё раз.\n"
        f"Если повторится 3 ночи подряд — приходи разбираться, что-то фундаментально съезжает."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RU_MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def _today_ru() -> str:
    from datetime import date
    today = date.today()
    return f"{today.day} {_RU_MONTHS[today.month]}"


def _word_things(n: int) -> str:
    """Pluralize 'штука' in Russian."""
    n10 = n % 10
    n100 = n % 100
    if n10 == 1 and n100 != 11:
        return f"{n} штуку"
    if 2 <= n10 <= 4 and not (12 <= n100 <= 14):
        return f"{n} штуки"
    return f"{n} штук"


def _word_questions(n: int) -> str:
    n10 = n % 10
    n100 = n % 100
    if n10 == 1 and n100 != 11:
        return f"{n} вопрос"
    if 2 <= n10 <= 4 and not (12 <= n100 <= 14):
        return f"{n} вопроса"
    return f"{n} вопросов"


def _word_points(n: int) -> str:
    n10 = n % 10
    n100 = n % 100
    if n10 == 1 and n100 != 11:
        return f"{n} пункт"
    if 2 <= n10 <= 4 and not (12 <= n100 <= 14):
        return f"{n} пункта"
    return f"{n} пунктов"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


# Make linter happy about Iterable not being used externally.
_ = Iterable
