from pathlib import Path
from unittest.mock import MagicMock, call, patch

from services.telemost_recorder.transcribe import (
    TranscriptSegment,
    _CHUNK_SECS,
    _get_duration,
    _transcribe_chunk,
    transcribe_audio,
)


def test_transcript_segment_dataclass():
    seg = TranscriptSegment(speaker="Speaker 0", start_ms=1000, end_ms=2000, text="Привет")
    assert seg.speaker == "Speaker 0"
    assert seg.start_ms == 1000
    assert seg.end_ms == 2000
    assert seg.text == "Привет"


def test_get_duration_parses_ffprobe_output(tmp_path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"fake")
    mock_result = MagicMock()
    mock_result.stdout = "87.420000\n"
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        dur = _get_duration(audio)
    assert dur == 87.42
    cmd = mock_run.call_args[0][0]
    assert "ffprobe" in cmd
    assert str(audio) in cmd


def test_transcribe_chunk_returns_segment():
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"result": "Добрый день команда"}
    with patch("requests.post", return_value=mock_resp):
        seg = _transcribe_chunk(b"audiodata", offset_ms=5000)
    assert seg is not None
    assert seg.text == "Добрый день команда"
    assert seg.start_ms == 5000
    assert seg.end_ms == 5000 + _CHUNK_SECS * 1000
    assert seg.speaker == "Speaker 0"


def test_transcribe_chunk_empty_result_returns_none():
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"result": ""}
    with patch("requests.post", return_value=mock_resp):
        seg = _transcribe_chunk(b"audiodata", offset_ms=0)
    assert seg is None


def test_transcribe_chunk_whitespace_result_returns_none():
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"result": "   "}
    with patch("requests.post", return_value=mock_resp):
        seg = _transcribe_chunk(b"audiodata", offset_ms=0)
    assert seg is None


def test_transcribe_chunk_http_error_returns_none():
    mock_resp = MagicMock()
    mock_resp.ok = False
    with patch("requests.post", return_value=mock_resp):
        seg = _transcribe_chunk(b"audiodata", offset_ms=0)
    assert seg is None


def test_transcribe_audio_two_chunks(tmp_path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"fake")

    # duration = 40s → 2 chunks: [0-25], [25-40]
    mock_ffprobe = MagicMock()
    mock_ffprobe.stdout = "40.0\n"
    mock_ffmpeg = MagicMock()

    def fake_run(cmd, **kwargs):
        if "ffprobe" in cmd:
            return mock_ffprobe
        return mock_ffmpeg

    responses = [
        MagicMock(ok=True, json=lambda: {"result": "Привет мир"}),
        MagicMock(ok=True, json=lambda: {"result": "Пока мир"}),
    ]
    with patch("subprocess.run", side_effect=fake_run), \
         patch("os.unlink"), \
         patch("tempfile.mkstemp", return_value=(0, "/tmp/fake.ogg")), \
         patch("os.close"), \
         patch("pathlib.Path.read_bytes", return_value=b"chunkdata"), \
         patch("requests.post", side_effect=responses), \
         patch("time.sleep"):
        segments = transcribe_audio(audio)

    assert len(segments) == 2
    assert segments[0].text == "Привет мир"
    assert segments[0].start_ms == 0
    assert segments[1].text == "Пока мир"
    assert segments[1].start_ms == _CHUNK_SECS * 1000


def test_transcribe_audio_skips_silent_chunks(tmp_path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"fake")

    mock_ffprobe = MagicMock()
    mock_ffprobe.stdout = "40.0\n"
    mock_ffmpeg = MagicMock()

    def fake_run(cmd, **kwargs):
        if "ffprobe" in cmd:
            return mock_ffprobe
        return mock_ffmpeg

    responses = [
        MagicMock(ok=True, json=lambda: {"result": ""}),   # silent chunk
        MagicMock(ok=True, json=lambda: {"result": "Текст"}),
    ]
    with patch("subprocess.run", side_effect=fake_run), \
         patch("os.unlink"), \
         patch("tempfile.mkstemp", return_value=(0, "/tmp/fake.ogg")), \
         patch("os.close"), \
         patch("pathlib.Path.read_bytes", return_value=b"chunkdata"), \
         patch("requests.post", side_effect=responses), \
         patch("time.sleep"):
        segments = transcribe_audio(audio)

    assert len(segments) == 1
    assert segments[0].text == "Текст"
    assert segments[0].start_ms == _CHUNK_SECS * 1000


def test_transcribe_audio_exact_chunk_one_chunk(tmp_path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"fake")

    mock_ffprobe = MagicMock()
    mock_ffprobe.stdout = f"{_CHUNK_SECS}.0\n"
    mock_ffmpeg = MagicMock()

    def fake_run(cmd, **kwargs):
        if "ffprobe" in cmd:
            return mock_ffprobe
        return mock_ffmpeg

    with patch("subprocess.run", side_effect=fake_run), \
         patch("os.unlink"), \
         patch("tempfile.mkstemp", return_value=(0, "/tmp/fake.ogg")), \
         patch("os.close"), \
         patch("pathlib.Path.read_bytes", return_value=b"chunkdata"), \
         patch("requests.post", return_value=MagicMock(ok=True, json=lambda: {"result": "Тест"})), \
         patch("time.sleep"):
        segments = transcribe_audio(audio)

    assert len(segments) == 1
    assert segments[0].start_ms == 0
