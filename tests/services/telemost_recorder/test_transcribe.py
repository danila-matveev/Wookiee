from pathlib import Path
from unittest.mock import MagicMock, call, patch

from yandex.cloud.ai.stt.v3 import stt_pb2
from yandex.cloud.operation import operation_pb2, operation_service_pb2

from services.telemost_recorder.transcribe import (
    TranscriptSegment,
    _parse_streaming_responses,
    transcribe_audio,
)


def _make_streaming_response(channel_tag: str, text: str, start_ms: int, end_ms: int):
    word = stt_pb2.Word(text=text, start_time_ms=start_ms, end_time_ms=end_ms)
    alt = stt_pb2.Alternative(text=text, words=[word], start_time_ms=start_ms, end_time_ms=end_ms)
    update = stt_pb2.AlternativeUpdate(alternatives=[alt], channel_tag=channel_tag)
    resp = stt_pb2.StreamingResponse()
    resp.final.CopyFrom(update)
    return resp


def _make_done_operation(responses: list) -> operation_pb2.Operation:
    response_list = stt_pb2.StreamingResponseList(streaming_responses=responses)
    op = operation_pb2.Operation(id="op-123", done=True)
    op.response.Pack(response_list)
    return op


def _mock_channels(mock_stt_stub, mock_ops_stub):
    """Return a side_effect for grpc.secure_channel that yields the right stub."""
    stt_channel = MagicMock()
    stt_channel.__enter__ = lambda s: s
    stt_channel.__exit__ = MagicMock(return_value=False)

    ops_channel = MagicMock()
    ops_channel.__enter__ = lambda s: s
    ops_channel.__exit__ = MagicMock(return_value=False)

    with patch("services.telemost_recorder.transcribe.stt_service_pb2_grpc.AsyncRecognizerStub",
               return_value=mock_stt_stub), \
         patch("services.telemost_recorder.transcribe.operation_service_pb2_grpc.OperationServiceStub",
               return_value=mock_ops_stub), \
         patch("grpc.secure_channel", side_effect=[stt_channel, ops_channel]), \
         patch("time.sleep"):
        yield


def test_transcribe_audio_returns_segments(tmp_path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"fakeaudio")

    r1 = _make_streaming_response("1", "Добрый день", 480, 1200)
    r2 = _make_streaming_response("2", "Привет", 1300, 1800)
    done_op = _make_done_operation([r1, r2])

    pending_op = operation_pb2.Operation(id="op-123", done=False)

    mock_stt = MagicMock()
    mock_stt.RecognizeFile.return_value = operation_pb2.Operation(id="op-123")
    mock_ops = MagicMock()
    mock_ops.Get.side_effect = [pending_op, done_op]

    from contextlib import contextmanager
    @contextmanager
    def _ctx():
        with patch("services.telemost_recorder.transcribe.stt_service_pb2_grpc.AsyncRecognizerStub",
                   return_value=mock_stt), \
             patch("services.telemost_recorder.transcribe.operation_service_pb2_grpc.OperationServiceStub",
                   return_value=mock_ops), \
             patch("grpc.secure_channel") as mc, \
             patch("time.sleep"):
            ch = MagicMock()
            ch.__enter__ = lambda s: s
            ch.__exit__ = MagicMock(return_value=False)
            mc.return_value = ch
            yield

    with _ctx():
        segments = transcribe_audio(audio)

    assert len(segments) == 2
    assert segments[0].speaker == "Speaker 1"
    assert segments[0].text == "Добрый день"
    assert segments[0].start_ms == 480
    assert segments[1].speaker == "Speaker 2"
    assert segments[1].text == "Привет"


def test_parse_streaming_responses_sorted(tmp_path):
    r1 = _make_streaming_response("0", "Второй", 2000, 2500)
    r2 = _make_streaming_response("0", "Первый", 100, 500)
    segments = _parse_streaming_responses([r1, r2])
    assert [s.start_ms for s in segments] == [100, 2000]


def test_parse_streaming_responses_empty():
    assert _parse_streaming_responses([]) == []


def test_parse_streaming_responses_skips_empty_text():
    resp = _make_streaming_response("0", "   ", 0, 100)
    assert _parse_streaming_responses([resp]) == []


def test_transcript_segment_dataclass():
    seg = TranscriptSegment(speaker="Speaker 1", start_ms=1000, end_ms=2000, text="Привет")
    assert seg.speaker == "Speaker 1"
    assert seg.start_ms == 1000
