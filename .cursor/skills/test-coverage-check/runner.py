"""Thin entry-point that delegates to scripts.nightly.test_coverage_check."""

from scripts.nightly.test_coverage_check import main

if __name__ == "__main__":
    raise SystemExit(main())
