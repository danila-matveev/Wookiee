"""Thin entry-point that delegates to scripts.nightly.test_coverage_check.

The runtime logic lives in scripts/nightly/test_coverage_check.py per
plan §2.1 (skills are thin shells around scripts/nightly/ helpers).
"""

from scripts.nightly.test_coverage_check import main

if __name__ == "__main__":
    raise SystemExit(main())
