from pathlib import Path
from unittest.mock import MagicMock, patch

from services.telemost_recorder.transcribe import TranscriptSegment, transcribe_audio


def _make_grpc_response(channel_tag: str, text: str, start_ms: int, end_ms: int):
    """Build a minimal mock gRPC StreamingResponse with one final alternative."""
    from yandex.cloud.ai.stt.v3 import stt_pb2

    word = stt_pb2.Word(text=text, start_time_ms=start_ms, end_time_ms=end_ms)
    alt = stt_pb2.Alternative(text=text, words=[word], start_time_ms=start_ms, end_time_ms=end_ms)
    update = stt_pb2.AlternativeUpdate(alternatives=[alt], channel_tag=channel_tag)
    resp = stt_pb2.StreamingResponse()
    resp.final.CopyFrom(update)
    return resp


def test_transcribe_audio_returns_segments(tmp_path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"fakeaudio")

    resp1 = _make_grpc_response("1", "Добрый день", 480, 1200)
    resp2 = _make_grpc_response("2", "Привет", 1300, 1800)

    mock_stub = MagicMock()
    mock_stub.RecognizeFile.return_value = iter([resp1, resp2])

    with patch("services.telemost_recorder.transcribe.stt_service_pb2_grpc.AsyncRecognizerStub",
               return_value=mock_stub), \
         patch("grpc.secure_channel") as mock_channel:
        mock_channel.return_value.__enter__ = lambda s: s
        mock_channel.return_value.__exit__ = MagicMock(return_value=False)
        segments = transcribe_audio(audio)

    assert len(segments) == 2
    assert segments[0].speaker == "Speaker 1"
    assert segments[0].text == "Добрый день"
    assert segments[0].start_ms == 480
    assert segments[1].speaker == "Speaker 2"
    assert segments[1].text == "Привет"


def test_transcribe_audio_sorted_by_start_ms(tmp_path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"fakeaudio")

    # Return segments out of order to verify sorting
    resp1 = _make_grpc_response("1", "Второй", 2000, 2500)
    resp2 = _make_grpc_response("2", "Первый", 100, 500)

    mock_stub = MagicMock()
    mock_stub.RecognizeFile.return_value = iter([resp1, resp2])

    with patch("services.telemost_recorder.transcribe.stt_service_pb2_grpc.AsyncRecognizerStub",
               return_value=mock_stub), \
         patch("grpc.secure_channel") as mock_channel:
        mock_channel.return_value.__enter__ = lambda s: s
        mock_channel.return_value.__exit__ = MagicMock(return_value=False)
        segments = transcribe_audio(audio)

    times = [s.start_ms for s in segments]
    assert times == sorted(times)


def test_transcribe_audio_empty_stream(tmp_path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"fakeaudio")

    mock_stub = MagicMock()
    mock_stub.RecognizeFile.return_value = iter([])

    with patch("services.telemost_recorder.transcribe.stt_service_pb2_grpc.AsyncRecognizerStub",
               return_value=mock_stub), \
         patch("grpc.secure_channel") as mock_channel:
        mock_channel.return_value.__enter__ = lambda s: s
        mock_channel.return_value.__exit__ = MagicMock(return_value=False)
        segments = transcribe_audio(audio)

    assert segments == []


def test_transcribe_audio_skips_empty_text(tmp_path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"fakeaudio")

    resp = _make_grpc_response("0", "   ", 0, 100)

    mock_stub = MagicMock()
    mock_stub.RecognizeFile.return_value = iter([resp])

    with patch("services.telemost_recorder.transcribe.stt_service_pb2_grpc.AsyncRecognizerStub",
               return_value=mock_stub), \
         patch("grpc.secure_channel") as mock_channel:
        mock_channel.return_value.__enter__ = lambda s: s
        mock_channel.return_value.__exit__ = MagicMock(return_value=False)
        segments = transcribe_audio(audio)

    assert segments == []


def test_transcript_segment_dataclass():
    seg = TranscriptSegment(speaker="Speaker 1", start_ms=1000, end_ms=2000, text="Привет")
    assert seg.speaker == "Speaker 1"
    assert seg.start_ms == 1000
