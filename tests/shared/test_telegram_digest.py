"""Tests for shared/telegram_digest.py — Telegram renderer + sender for the night agent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from shared.hygiene.schemas import HeartbeatSummary, QueueItem
from shared.telegram_digest import (
    MAX_HEARTBEAT_LEN,
    _validate_plain_language,
    render_failure_alert,
    render_heartbeat,
    render_needs_human_digest,
    send_digest,
)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def test_validate_plain_language_passes_clean_russian():
    text = "🌙 Ночь 14 мая. Починил 3 штуки, ждёт твоё решение 1 пункт."
    assert _validate_plain_language(text) == []


def test_validate_plain_language_flags_jargon():
    text = "Сделал commit и merge в branch, потом rebase."
    violations = _validate_plain_language(text)
    assert "commit" in violations
    assert "merge" in violations
    assert "branch" in violations
    assert "rebase" in violations


def test_validate_plain_language_allows_jargon_in_parens():
    text = "Открыл запрос на слияние (merge request). Всё ок."
    violations = _validate_plain_language(text)
    # `merge` is inside parens → ignored
    assert violations == []


def test_validate_plain_language_allows_jargon_in_backticks():
    text = "Запусти `git merge` и проверь."
    violations = _validate_plain_language(text)
    assert violations == []


def test_validate_plain_language_allows_pr_acronym():
    # PR is whitelisted per plan §5.7
    text = "PR #234 уже зелёный и автоматически смерджится."
    violations = _validate_plain_language(text)
    # `merge` is not in this sentence; "смерджится" uses different stem and is fine
    assert "PR" not in violations


# ---------------------------------------------------------------------------
# send_digest
# ---------------------------------------------------------------------------


def test_send_digest_raises_without_env(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALERTS_BOT_TOKEN", raising=False)
    monkeypatch.delenv("HYGIENE_TELEGRAM_CHAT_ID", raising=False)
    with pytest.raises(RuntimeError, match="missing"):
        send_digest("test")


def test_send_digest_posts_to_telegram(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALERTS_BOT_TOKEN", "token-xyz")
    monkeypatch.setenv("HYGIENE_TELEGRAM_CHAT_ID", "12345")

    calls: list[dict] = []

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return SimpleNamespace(status_code=200, text="ok")

    monkeypatch.setattr("shared.telegram_digest.requests.post", fake_post)

    send_digest("Привет, мир", level="info")

    assert len(calls) == 1
    assert "/bottoken-xyz/sendMessage" in calls[0]["url"]
    assert calls[0]["json"]["chat_id"] == "12345"
    assert calls[0]["json"]["text"] == "Привет, мир"
    assert calls[0]["json"]["parse_mode"] == "Markdown"


def test_send_digest_raises_on_non_200(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALERTS_BOT_TOKEN", "token-xyz")
    monkeypatch.setenv("HYGIENE_TELEGRAM_CHAT_ID", "12345")

    def fake_post(url, json, timeout):
        return SimpleNamespace(status_code=429, text="rate limited")

    monkeypatch.setattr("shared.telegram_digest.requests.post", fake_post)

    with pytest.raises(RuntimeError, match="429"):
        send_digest("test")


def test_send_digest_truncates_long_messages(monkeypatch, caplog):
    monkeypatch.setenv("TELEGRAM_ALERTS_BOT_TOKEN", "tok")
    monkeypatch.setenv("HYGIENE_TELEGRAM_CHAT_ID", "1")

    captured: list[str] = []

    def fake_post(url, json, timeout):
        captured.append(json["text"])
        return SimpleNamespace(status_code=200, text="ok")

    monkeypatch.setattr("shared.telegram_digest.requests.post", fake_post)

    long_msg = "a" * 5000
    send_digest(long_msg)
    assert len(captured[0]) <= 4000
    assert captured[0].endswith("...")


# ---------------------------------------------------------------------------
# render_needs_human_digest
# ---------------------------------------------------------------------------


def _make_item(
    id: str = "i-1",
    question_ru: str = "Удалить старую доку или оставить?",
    default: str = "archive",
    files: list[str] | None = None,
) -> QueueItem:
    now = datetime.now(timezone.utc)
    return QueueItem(
        id=id,
        source_report=".hygiene/reports/hygiene-2026-05-14.json",
        enqueued_at=now,
        expires_at=now + timedelta(days=7),
        category="orphan-docs",
        files=files or ["docs/old.md"],
        question_ru=question_ru,
        options=["archive", "keep"],
        default_after_7d=default,
        last_surfaced_at=now,
    )


def test_render_needs_human_empty():
    text = render_needs_human_digest([])
    assert "чисто" in text.lower()
    # No technical prefix like "[wookiee night]" — должно быть plain Russian
    assert "[wookiee" not in text.lower()
    assert "за ночь" in text.lower()


def test_render_needs_human_one_item():
    item = _make_item(question_ru="Документ docs/finance-v2-spec.md нигде не используется. Архив или живой?")
    text = render_needs_human_digest([item])
    assert "1 вопрос" in text
    assert "finance-v2-spec.md" in text
    assert "/hygiene-resolve" in text
    assert "7 дней" in text
    assert "archive" in text.lower()


def test_render_needs_human_three_items():
    items = [
        _make_item(id="a", question_ru="Q1?", default="archive"),
        _make_item(id="b", question_ru="Q2?", default="keep"),
        _make_item(id="c", question_ru="Q3?", default="delete"),
    ]
    text = render_needs_human_digest(items)
    assert "3 вопроса" in text
    assert "Q1?" in text and "Q2?" in text and "Q3?" in text
    assert "/hygiene-resolve" in text


def test_render_needs_human_many_items():
    items = [_make_item(id=str(i), question_ru=f"Q{i}?") for i in range(8)]
    text = render_needs_human_digest(items)
    assert "8 вопросов" in text
    assert "много" in text
    assert "/hygiene-resolve" in text


def test_render_needs_human_passes_validator():
    items = [_make_item()]
    text = render_needs_human_digest(items)
    violations = _validate_plain_language(text)
    # Filter out anything coming from sample data
    assert not violations, f"plain-language violations in renderer output: {violations}"


# ---------------------------------------------------------------------------
# render_heartbeat
# ---------------------------------------------------------------------------


def test_render_heartbeat_all_clear():
    summary = HeartbeatSummary(
        date_str="14 мая",
        fixes_applied=0,
        needs_human_count=0,
        coverage_pct=67.0,
        coverage_delta_pp=0.0,
    )
    text = render_heartbeat(summary)
    assert "14 мая" in text
    assert "чисто" in text.lower()
    assert "67%" in text
    assert len(text) <= MAX_HEARTBEAT_LEN


def test_render_heartbeat_with_fixes_and_needs_human():
    summary = HeartbeatSummary(
        date_str="14 мая",
        fixes_applied=3,
        fixes_examples=["битая ссылка", "лишний импорт", "drift зеркала"],
        needs_human_count=1,
        coverage_pct=67.0,
        coverage_delta_pp=0.0,
    )
    text = render_heartbeat(summary)
    assert "14 мая" in text
    assert "3 штуки" in text
    assert "битая ссылка" in text
    assert "1 пункт" in text
    assert "/hygiene-resolve" in text
    assert "67%" in text
    assert "без изменений" in text
    assert len(text) <= MAX_HEARTBEAT_LEN


def test_render_heartbeat_coverage_drop():
    summary = HeartbeatSummary(
        date_str="14 мая",
        fixes_applied=1,
        fixes_examples=["один lint"],
        needs_human_count=0,
        coverage_pct=64.0,
        coverage_delta_pp=-3.0,
    )
    text = render_heartbeat(summary)
    assert "-3.0 п.п." in text


def test_render_heartbeat_coverage_growth():
    summary = HeartbeatSummary(
        date_str="14 мая",
        fixes_applied=1,
        needs_human_count=0,
        coverage_pct=69.0,
        coverage_delta_pp=2.0,
    )
    text = render_heartbeat(summary)
    assert "+2.0 п.п." in text


def test_render_heartbeat_failure_mode():
    summary = HeartbeatSummary(
        date_str="14 мая",
        failure="code-quality-scan превысил лимит токенов",
    )
    text = render_heartbeat(summary)
    assert "сломалось" in text.lower()
    assert "code-quality-scan" in text
    assert "репо не тронул" in text


def test_render_heartbeat_length_cap():
    """≤500 char cap per spec."""
    summary = HeartbeatSummary(
        date_str="14 мая",
        fixes_applied=99,
        fixes_examples=["x" * 100, "y" * 100, "z" * 100],
        needs_human_count=15,
        coverage_pct=67.0,
        coverage_delta_pp=-5.0,
        pr_number=1234,
        pr_status="open",
    )
    text = render_heartbeat(summary)
    assert len(text) <= MAX_HEARTBEAT_LEN


# ---------------------------------------------------------------------------
# render_failure_alert
# ---------------------------------------------------------------------------


def test_render_failure_alert_includes_skill_and_error():
    text = render_failure_alert("code-quality-scan", "превысил лимит токенов 250k")
    assert "сломалось" in text.lower()
    assert "сканер кода" in text  # russified skill name
    assert "лимит токенов" in text
    # No technical prefix
    assert "[wookiee" not in text.lower()


def test_render_failure_alert_unknown_skill_passes_raw():
    text = render_failure_alert("custom-skill", "boom")
    assert "custom-skill" in text


def test_render_failure_alert_handles_empty_error():
    text = render_failure_alert("heartbeat", "")
    assert "без подробностей" in text


def test_render_failure_alert_trims_long_errors():
    long_err = "trace: " + ("x" * 1000)
    text = render_failure_alert("hygiene", long_err)
    # Should not blow up message length too much
    assert len(text) < 1000
