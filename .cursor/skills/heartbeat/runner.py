"""Thin entry-point that delegates to scripts.nightly.heartbeat."""

from scripts.nightly.heartbeat import main

if __name__ == "__main__":
    raise SystemExit(main())
