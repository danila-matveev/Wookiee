"""Thin entry-point that delegates to scripts.nightly.heartbeat.

The runtime logic lives in scripts/nightly/heartbeat.py per plan §2.1.
"""

from scripts.nightly.heartbeat import main

if __name__ == "__main__":
    raise SystemExit(main())
