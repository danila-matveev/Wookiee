import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from services.telemost_recorder.config import AUDIO_BITRATE, MAX_RECORDING_MINUTES, TELEMOST_CAPTURE


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
        """Start recording. Returns False if capture disabled or not on Linux."""
        if not TELEMOST_CAPTURE or platform.system() != "Linux":
            return False

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

        # Make our sink the default so new streams go here
        subprocess.run(["pactl", "set-default-sink", self._sink_name], capture_output=True)

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
        """Stop recording. Returns audio path if file is non-empty, else None."""
        if self._ffmpeg_proc is not None:
            self._ffmpeg_proc.terminate()
            try:
                self._ffmpeg_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._ffmpeg_proc.kill()
                self._ffmpeg_proc.wait()
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
