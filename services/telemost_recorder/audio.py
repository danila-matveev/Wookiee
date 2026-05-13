import logging
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from services.telemost_recorder.config import AUDIO_BITRATE, MAX_RECORDING_MINUTES, TELEMOST_CAPTURE

logger = logging.getLogger(__name__)

# Threshold for free disk space before starting ffmpeg.
# Opus @ 64 kbps ≈ 460 MB/h; 1 GB gives ~2h of headroom, which comfortably
# covers MAX_RECORDING_MINUTES (default 240 → 4h, but most meetings <1h)
# plus tmp/segment buffers. Below this we refuse to start rather than
# fill the disk mid-recording and crash the host.
_MIN_FREE_DISK_BYTES = 1 * 1024 * 1024 * 1024  # 1 GB


class AudioCaptureError(RuntimeError):
    """Raised when audio capture cannot start (e.g. low disk)."""


def _pa_state(label: str) -> None:
    """Log PulseAudio sinks + sink-inputs + clients for diagnostics."""
    try:
        sinks = subprocess.run(
            ["pactl", "list", "short", "sinks"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
        si = subprocess.run(
            ["pactl", "list", "short", "sink-inputs"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
        clients = subprocess.run(
            ["pactl", "list", "short", "clients"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
        logger.warning("PA[%s] sinks: %s", label, sinks.replace("\n", " | ") or "(none)")
        logger.warning("PA[%s] sink-inputs: %s", label, si.replace("\n", " | ") or "(none)")
        logger.warning("PA[%s] clients: %s", label, clients.replace("\n", " | ") or "(none)")
    except Exception as e:
        logger.warning("PA[%s] probe failed: %s", label, e)


@dataclass
class AudioCapture:
    meeting_id: str
    output_dir: Path
    _sink_module_id: Optional[int] = field(default=None, init=False, repr=False)
    _ffmpeg_proc: Optional[subprocess.Popen] = field(default=None, init=False, repr=False)
    _sink_name: str = field(default="", init=False, repr=False)

    @property
    def audio_path(self) -> Path:
        return self.output_dir / "audio.opus"

    def start(self) -> bool:
        """Start recording. Returns False if capture disabled or not on Linux.

        Raises:
            AudioCaptureError: if free disk space in ``output_dir.parent``
                is below the 1 GB safety threshold.
        """
        if not TELEMOST_CAPTURE or platform.system() != "Linux":
            return False

        # Disk safety check: refuse to start ffmpeg if there isn't enough
        # headroom for a long meeting. Cheaper than discovering a full disk
        # halfway through an hour-long recording.
        disk_target = self.output_dir if self.output_dir.exists() else self.output_dir.parent
        free = shutil.disk_usage(str(disk_target)).free
        if free < _MIN_FREE_DISK_BYTES:
            free_mb = free // (1024 * 1024)
            msg = (
                f"Not enough disk space at {disk_target}: "
                f"{free_mb} MB free, need at least 1 GB"
            )
            logger.error(msg)
            raise AudioCaptureError(msg)

        self._sink_name = f"telemost_{self.meeting_id[:8]}"
        result = subprocess.run(
            [
                "pactl", "load-module", "module-null-sink",
                f"sink_name={self._sink_name}",
                "sink_properties=device.description=TelemostCapture",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"PulseAudio sink creation failed: {result.stderr}")
        self._sink_module_id = int(result.stdout.strip())

        # Make our sink the default so new streams go here.
        # set-default-sink is sometimes ignored by Chromium (it caches the sink at
        # client connect time). Belt-and-suspenders: also export PULSE_SINK so any
        # subprocess (Chromium) that reads it pins its output to our sink explicitly.
        subprocess.run(["pactl", "set-default-sink", self._sink_name], capture_output=True)
        os.environ["PULSE_SINK"] = self._sink_name
        _pa_state("after-create-sink")

        # Move any existing sink-inputs (Chromium WebRTC streams) to our sink
        inputs = subprocess.run(
            ["pactl", "list", "short", "sink-inputs"],
            capture_output=True, text=True,
        )
        for line in inputs.stdout.strip().splitlines():
            if line.strip():
                input_id = line.split()[0]
                subprocess.run(
                    ["pactl", "move-sink-input", input_id, self._sink_name],
                    capture_output=True,
                )

        self._ffmpeg_proc = subprocess.Popen(
            [
                "ffmpeg", "-y",
                "-f", "pulse", "-i", f"{self._sink_name}.monitor",
                "-c:a", "libopus",
                "-b:a", AUDIO_BITRATE,
                "-ar", "48000",
                "-ac", "1",
                "-t", str(MAX_RECORDING_MINUTES * 60),
                str(self.audio_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True

    def reroute_streams(self) -> None:
        """Move any sink-inputs not yet on our sink. Call periodically during meeting."""
        if not self._sink_name or platform.system() != "Linux":
            return
        _pa_state("reroute-tick")
        inputs = subprocess.run(
            ["pactl", "list", "short", "sink-inputs"],
            capture_output=True, text=True,
        )
        for line in inputs.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split()
            input_id, sink_id = parts[0], parts[1] if len(parts) > 1 else ""
            sinks = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                capture_output=True, text=True,
            )
            our_sink_id = None
            for sline in sinks.stdout.strip().splitlines():
                sp = sline.split()
                if len(sp) >= 2 and sp[1] == self._sink_name:
                    our_sink_id = sp[0]
                    break
            if our_sink_id and sink_id != our_sink_id:
                subprocess.run(
                    ["pactl", "move-sink-input", input_id, self._sink_name],
                    capture_output=True,
                )

    def stop(self) -> Optional[Path]:
        """Stop recording. Returns audio path if file is non-empty, else None.

        ffmpeg can ignore SIGTERM if PulseAudio crashed mid-recording (its
        pulse input becomes a stuck I/O). We bound the shutdown: SIGTERM →
        wait 10s → SIGKILL → wait 2s. Logging a warning lets us see in
        Telegram alerts when ffmpeg refused to terminate cleanly.
        """
        if self._ffmpeg_proc is not None:
            self._ffmpeg_proc.terminate()
            try:
                self._ffmpeg_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning(
                    "ffmpeg didn't terminate in 10s, sending SIGKILL"
                )
                self._ffmpeg_proc.kill()
                try:
                    self._ffmpeg_proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    logger.exception(
                        "ffmpeg ignored SIGKILL after 2s — leaking PID %s",
                        getattr(self._ffmpeg_proc, "pid", "?"),
                    )
            self._ffmpeg_proc = None

        if self._sink_module_id is not None:
            subprocess.run(
                ["pactl", "unload-module", str(self._sink_module_id)],
                capture_output=True,
            )
            self._sink_module_id = None

        if self.audio_path.exists() and self.audio_path.stat().st_size > 0:
            return self.audio_path
        return None
