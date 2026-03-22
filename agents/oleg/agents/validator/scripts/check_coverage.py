"""Check that all warning/critical signals are covered by recommendations."""

from __future__ import annotations


def check_coverage(signals: list[dict], recommendations: list[dict]) -> dict:
    """Verify all signals with severity >= warning have a recommendation."""
    covered_ids = {r.get("signal_id") for r in recommendations}

    covered = []
    missed = []
    info_skipped = []

    for signal in signals:
        sid = signal.get("id", "")
        severity = signal.get("severity", "info")

        if sid in covered_ids:
            covered.append(sid)
        elif severity in ("warning", "critical"):
            missed.append(sid)
        else:
            info_skipped.append(sid)

    return {
        "covered": covered,
        "missed": missed,
        "info_skipped": info_skipped,
    }
