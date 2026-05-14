import logging
import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.telemost_recorder.audio import AudioCapture, AudioCaptureError


def test_audio_path_property(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    assert cap.audio_path == tmp_path / "audio.opus"


def test_start_returns_false_when_capture_disabled(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    with patch("services.telemost_recorder.audio.TELEMOST_CAPTURE", False):
        result = cap.start()
    assert result is False


def test_start_returns_false_on_macos(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    with patch("services.telemost_recorder.audio.TELEMOST_CAPTURE", True), \
         patch("platform.system", return_value="Darwin"):
        result = cap.start()
    assert result is False


def test_stop_without_start_returns_none(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    result = cap.stop()
    assert result is None


def test_stop_returns_none_when_audio_file_missing(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    mock_proc = MagicMock()
    cap._ffmpeg_proc = mock_proc
    result = cap.stop()
    mock_proc.terminate.assert_called_once()
    assert result is None


def test_stop_returns_path_when_audio_file_exists(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    audio_file = tmp_path / "audio.opus"
    audio_file.write_bytes(b"fake opus data")
    mock_proc = MagicMock()
    mock_sink_id = 5
    cap._ffmpeg_proc = mock_proc
    cap._sink_module_id = mock_sink_id
    with patch("subprocess.run") as mock_run:
        result = cap.stop()
    mock_run.assert_called_once_with(
        ["pactl", "unload-module", "5"],
        capture_output=True,
    )
    assert result == audio_file


def test_stop_kills_ffmpeg_after_terminate_timeout(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """If ffmpeg ignores SIGTERM for 10s, stop() must SIGKILL it and log a warning.

    Bug scenario: pulseaudio crashed mid-recording → ffmpeg's pulse input becomes
    a zombie I/O that ignores SIGTERM → the recorder container previously hung
    until the 4-hour hard limit. We now kill after wait(timeout=10) raises.
    """
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    fake_proc = MagicMock()
    call_count = {"n": 0}

    def wait_side_effect(timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # First wait(timeout=10) — simulate hung ffmpeg
            raise subprocess.TimeoutExpired("ffmpeg", timeout)
        # Second wait after kill — succeeds quickly
        return 0

    fake_proc.wait.side_effect = wait_side_effect
    cap._ffmpeg_proc = fake_proc

    with caplog.at_level(logging.WARNING, logger="services.telemost_recorder.audio"):
        cap.stop()  # must not raise

    fake_proc.terminate.assert_called_once()
    fake_proc.kill.assert_called_once()
    assert any(
        "kill" in r.message.lower() for r in caplog.records
    ), f"expected a kill-warning log, got {[r.message for r in caplog.records]}"


def test_stop_logs_when_sigkill_also_ignored(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """If even SIGKILL leaves the process hanging within 2s, log and move on.

    Belt-and-suspenders: we still return so that the recorder container can
    exit normally; an orphaned ffmpeg PID is a much smaller blast radius than
    a 4-hour-stuck container.
    """
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)
    fake_proc = MagicMock()
    fake_proc.wait.side_effect = subprocess.TimeoutExpired("ffmpeg", 10)
    cap._ffmpeg_proc = fake_proc

    with caplog.at_level(logging.ERROR, logger="services.telemost_recorder.audio"):
        cap.stop()  # must still not raise

    fake_proc.terminate.assert_called_once()
    fake_proc.kill.assert_called_once()


def _fake_disk_usage(free_bytes: int):
    """Build a fake shutil.disk_usage result with the given free bytes."""
    def _du(path):
        return type("DU", (), {"free": free_bytes, "total": 10**10, "used": 10**9})()
    return _du


def test_start_on_linux_creates_sink_and_ffmpeg(tmp_path: Path) -> None:
    cap = AudioCapture(meeting_id="test-id-123", output_dir=tmp_path)
    mock_pactl = MagicMock()
    mock_pactl.returncode = 0
    mock_pactl.stdout = "42\n"
    mock_ffmpeg = MagicMock()

    with patch("services.telemost_recorder.audio.TELEMOST_CAPTURE", True), \
         patch("platform.system", return_value="Linux"), \
         patch(
             "services.telemost_recorder.audio.shutil.disk_usage",
             _fake_disk_usage(10 * 1024 * 1024 * 1024),  # 10 GB free
         ), \
         patch("subprocess.run", return_value=mock_pactl) as mock_run, \
         patch("subprocess.Popen", return_value=mock_ffmpeg) as mock_popen:
        result = cap.start()

    assert result is True
    assert cap._sink_module_id == 42
    assert cap._ffmpeg_proc is mock_ffmpeg
    # First pactl call loads the null sink
    first_call_args = mock_run.call_args_list[0][0][0]
    assert "module-null-sink" in first_call_args
    assert "telemost_test-id" in " ".join(first_call_args)
    # Subsequent calls set default sink and move existing inputs
    all_calls = [c[0][0] for c in mock_run.call_args_list]
    assert any("set-default-sink" in c for c in all_calls)


def test_start_raises_when_low_disk(tmp_path: Path) -> None:
    """If free disk space is below 1 GB, start() must raise AudioCaptureError."""
    cap = AudioCapture(meeting_id="abc123", output_dir=tmp_path)

    with patch("services.telemost_recorder.audio.TELEMOST_CAPTURE", True), \
         patch("platform.system", return_value="Linux"), \
         patch(
             "services.telemost_recorder.audio.shutil.disk_usage",
             _fake_disk_usage(500 * 1024 * 1024),  # 500 MB free
         ), \
         patch("subprocess.run") as mock_run, \
         patch("subprocess.Popen") as mock_popen:
        with pytest.raises(AudioCaptureError, match="disk space"):
            cap.start()

    # Must abort before touching PulseAudio / ffmpeg.
    mock_run.assert_not_called()
    mock_popen.assert_not_called()
