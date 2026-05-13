"""Unit tests for telemost cleanup worker sweep logic.

Only exercises the synchronous helper — the run_forever loop is a thin
wrapper around asyncio.to_thread + sleep and is verified manually.
"""
import os
import time
from pathlib import Path

from services.telemost_recorder_api.workers.cleanup_worker import _sweep_sync


def test_sweep_removes_old_folders(tmp_path: Path):
    old = tmp_path / "old-meeting"
    old.mkdir()
    (old / "audio.opus").write_bytes(b"...")
    new = tmp_path / "new-meeting"
    new.mkdir()
    (new / "audio.opus").write_bytes(b"...")

    # Backdate the old folder past the retention cutoff.
    old_time = time.time() - (40 * 86400)
    os.utime(old, (old_time, old_time))

    removed = _sweep_sync(tmp_path, max_age_days=30)

    assert removed == 1
    assert not old.exists()
    assert new.exists()


def test_sweep_handles_missing_dir(tmp_path: Path):
    removed = _sweep_sync(tmp_path / "nonexistent", max_age_days=30)
    assert removed == 0


def test_sweep_ignores_files_at_top_level(tmp_path: Path):
    """Stray files (not directories) in DATA_DIR must not be touched."""
    stray = tmp_path / "stray.txt"
    stray.write_text("hello")
    old_time = time.time() - (40 * 86400)
    os.utime(stray, (old_time, old_time))

    removed = _sweep_sync(tmp_path, max_age_days=30)

    assert removed == 0
    assert stray.exists()


def test_sweep_keeps_fresh_folders(tmp_path: Path):
    fresh = tmp_path / "fresh-meeting"
    fresh.mkdir()
    removed = _sweep_sync(tmp_path, max_age_days=30)
    assert removed == 0
    assert fresh.exists()
