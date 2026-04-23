"""Pre-publish gate for /funnel-report output.

Validates that `docs/reports/{START}_{END}_funnel.md` matches the SKILL.md
contract: per-model WB toggles, OZON block (or explicit disclaimer), I-b halo,
XIII recommendations, minimum size, no simplified-template banned patterns.

Exit codes:
    0 — all checks passed, safe to publish to Notion
    1 — one or more checks failed, DO NOT publish

Usage:
    python3 scripts/funnel_report/validate_output.py docs/reports/2026-04-13_2026-04-19_funnel.md \\
        --depth week \\
        [--min-wb-toggles 10] [--min-ozon-toggles 5] [--min-size-kb 25]

Hooked from .claude/skills/funnel-report/SKILL.md Stage 5.2.1 before publication.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


DEFAULT_MIN_SIZE_KB = {"day": 10, "week": 25, "month": 60}
DEFAULT_MIN_WB_TOGGLES = {"day": 5, "week": 10, "month": 10}
DEFAULT_MIN_OZON_TOGGLES = {"day": 3, "week": 5, "month": 5}

BANNED_PATTERNS = [
    (r"^##\s*III\.\s*Воронка\s*(по\s*моделям)?\s*\(топ[\s-]*\d+\)", "simplified-template 'III. Воронка (топ-N)'"),
    (r"^##\s*IV\.\s*Модельные\s*CRO\s*\(сводка\)", "simplified-template 'IV. Модельные CRO (сводка)'"),
    (r"^##\s*V\.\s*Трафик-каналы", "simplified-template 'V. Трафик-каналы'"),
    (r"^##\s*VI\.\s*Итог\s*(по\s*воронке)?", "simplified-template 'VI. Итог (по воронке)'"),
]

# Accept toggle headers with or without ▶ (U+25B6) — SKILL.md and synthesizer.md
# use both forms. Also accept `{toggle="true"}` suffix variant documented in §5.1.
WB_TOGGLE_RE = re.compile(r"^##\s*(?:▶\s*)?Модель:\s+\S", re.MULTILINE)
OZON_TOGGLE_RE = re.compile(r"^##\s*(?:▶\s*)?OZON:\s+\S", re.MULTILINE)
OZON_OVERVIEW_RE = re.compile(
    r"^##\s*(?:▶\s*)?OZON\b[^\n]*обзор\s+канала", re.MULTILINE | re.IGNORECASE,
)
# Broad disclaimer: "OZON" within 80 chars of a failure keyword in any form.
OZON_DISCLAIMER_RE = re.compile(
    r"OZON[\s\S]{0,80}?"
    r"(недоступн|не\s+собр|не\s+верн|не\s+получ|пропущен|skipped|missing|not\s+available|ошибк|fail)",
    re.IGNORECASE,
)
HALO_SECTION_RE = re.compile(r"^##\s*(?:I-b|II)\.\s*Halo", re.MULTILINE | re.IGNORECASE)
SECTION_I_RE = re.compile(r"^##\s*I\.", re.MULTILINE)
SECTION_XIII_RE = re.compile(r"^##\s*XIII\.", re.MULTILINE)


def validate(
    md_path: Path,
    depth: str,
    min_wb_toggles: int,
    min_ozon_toggles: int,
    min_size_kb: int,
    strict_ozon: bool,
) -> tuple[bool, list[str], float]:
    """Return (passed, failures, size_kb). On pass, failures is empty."""
    failures: list[str] = []

    if not md_path.exists():
        return False, [f"file not found: {md_path}"], 0.0

    content = md_path.read_text(encoding="utf-8")
    size_kb = len(content.encode("utf-8")) / 1024

    # 1. Size threshold
    if size_kb < min_size_kb:
        failures.append(
            f"size {size_kb:.1f} KB < threshold {min_size_kb} KB (depth={depth}) — "
            f"likely orchestrator skipped model-analyst/synthesizer"
        )

    # 2. Section I.
    if not SECTION_I_RE.search(content):
        failures.append("missing section: '## I.' (brand overview)")

    # 3. Section XIII.
    if not SECTION_XIII_RE.search(content):
        failures.append("missing section: '## XIII.' (recommendations)")

    # 4. Halo I-b.
    if not HALO_SECTION_RE.search(content):
        failures.append("missing halo section: '## I-b.' (склейки WB)")

    # 5. WB per-model toggles
    wb_count = len(WB_TOGGLE_RE.findall(content))
    if wb_count < min_wb_toggles:
        failures.append(
            f"WB per-model toggles {wb_count} < min {min_wb_toggles} "
            f"— expected pattern '## ▶ Модель: {{Name}}'"
        )

    # 6. OZON block
    ozon_count = len(OZON_TOGGLE_RE.findall(content))
    ozon_overview_present = bool(OZON_OVERVIEW_RE.search(content))
    ozon_disclaimer_present = bool(OZON_DISCLAIMER_RE.search(content))

    if strict_ozon:
        if not ozon_overview_present:
            failures.append("missing OZON overview toggle: '## ▶ OZON — обзор канала'")
        if ozon_count < min_ozon_toggles:
            failures.append(
                f"OZON per-model toggles {ozon_count} < min {min_ozon_toggles} "
                f"— expected pattern '## ▶ OZON: {{Name}}'"
            )
    else:
        if ozon_count < min_ozon_toggles and not ozon_disclaimer_present:
            failures.append(
                f"OZON toggles {ozon_count} < {min_ozon_toggles} and no disclaimer "
                f"('OZON данные недоступны' / 'OZON не собрано') — choose one"
            )

    # 7. Banned simplified-template patterns
    for pattern, label in BANNED_PATTERNS:
        if re.search(pattern, content, re.MULTILINE):
            failures.append(f"banned simplified-template pattern found: {label}")

    # 8. Defense-in-depth: tiny report with zero WB toggles is always a regression,
    #    even if somehow banned patterns are absent (orchestrator could invent new ones).
    if wb_count == 0 and size_kb < 15:
        failures.append(
            f"catastrophic regression: 0 WB toggles + size {size_kb:.1f} KB < 15 KB "
            f"— orchestrator did not run Model Analyst subagent"
        )

    return len(failures) == 0, failures, size_kb


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate /funnel-report output before Notion publication")
    parser.add_argument("md_path", help="Path to docs/reports/{START}_{END}_funnel.md")
    parser.add_argument("--depth", choices=["day", "week", "month"], default="week")
    parser.add_argument("--min-wb-toggles", type=int, default=None,
                        help="Minimum count of '## ▶ Модель:' sections (default: depth-based)")
    parser.add_argument("--min-ozon-toggles", type=int, default=None,
                        help="Minimum count of '## ▶ OZON:' sections (default: depth-based)")
    parser.add_argument("--min-size-kb", type=int, default=None,
                        help="Minimum MD size in KB (default: depth-based)")
    parser.add_argument("--strict-ozon", action="store_true",
                        help="Require OZON block, do not accept disclaimer")
    args = parser.parse_args()

    min_wb = args.min_wb_toggles if args.min_wb_toggles is not None else DEFAULT_MIN_WB_TOGGLES.get(args.depth, DEFAULT_MIN_WB_TOGGLES["week"])
    min_ozon = args.min_ozon_toggles if args.min_ozon_toggles is not None else DEFAULT_MIN_OZON_TOGGLES.get(args.depth, DEFAULT_MIN_OZON_TOGGLES["week"])
    min_size = args.min_size_kb if args.min_size_kb is not None else DEFAULT_MIN_SIZE_KB.get(args.depth, DEFAULT_MIN_SIZE_KB["week"])

    md_path = Path(args.md_path)
    passed, failures, size_kb = validate(md_path, args.depth, min_wb, min_ozon, min_size, args.strict_ozon)

    if passed:
        print(f"OK  {md_path}  ({size_kb:.1f} KB, depth={args.depth})")
        return 0

    print(f"FAIL  {md_path}  ({size_kb:.1f} KB, depth={args.depth})", file=sys.stderr)
    for f in failures:
        print(f"  - {f}", file=sys.stderr)
    print(
        "\nDO NOT PUBLISH. Fix synthesizer output (likely orchestrator skipped "
        "model-analyst/synthesizer subagents and emitted simplified template).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
