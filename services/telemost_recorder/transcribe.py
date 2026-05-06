import time
from dataclasses import dataclass
from pathlib import Path

import grpc
from yandex.cloud.ai.stt.v3 import stt_pb2, stt_service_pb2_grpc
from yandex.cloud.operation import operation_service_pb2, operation_service_pb2_grpc

from services.telemost_recorder.config import SPEECHKIT_API_KEY, YANDEX_FOLDER_ID

_STT_HOST = "stt.api.cloud.yandex.net:443"
_OPS_HOST = "operation.api.cloud.yandex.net:443"
_POLL_INTERVAL = 5
_POLL_TIMEOUT = 1800


@dataclass
class TranscriptSegment:
    speaker: str
    start_ms: int
    end_ms: int
    text: str


def transcribe_audio(audio_path: Path) -> list[TranscriptSegment]:
    """Submit audio to SpeechKit v3 async, poll until done, return segments."""
    audio_bytes = audio_path.read_bytes()
    metadata = [
        ("authorization", f"Api-Key {SPEECHKIT_API_KEY}"),
        ("x-folder-id", YANDEX_FOLDER_ID),
    ]
    credentials = grpc.ssl_channel_credentials()

    # 1. Submit recognition job → Operation
    with grpc.secure_channel(_STT_HOST, credentials) as channel:
        stub = stt_service_pb2_grpc.AsyncRecognizerStub(channel)
        operation = stub.RecognizeFile(
            stt_pb2.RecognizeFileRequest(
                content=audio_bytes,
                recognition_model=stt_pb2.RecognitionModelOptions(
                    audio_format=stt_pb2.AudioFormatOptions(
                        container_audio=stt_pb2.ContainerAudio(
                            container_audio_type=stt_pb2.ContainerAudio.OGG_OPUS,
                        ),
                    ),
                    language_restriction=stt_pb2.LanguageRestrictionOptions(
                        restriction_type=stt_pb2.LanguageRestrictionOptions.WHITELIST,
                        language_code=["ru-RU"],
                    ),
                    audio_processing_type=stt_pb2.RecognitionModelOptions.FULL_DATA,
                ),
                speech_analysis=stt_pb2.SpeechAnalysisOptions(
                    enable_speaker_analysis=True,
                ),
            ),
            metadata=metadata,
        )

    operation_id = operation.id

    # 2. Poll until done
    deadline = time.monotonic() + _POLL_TIMEOUT
    with grpc.secure_channel(_OPS_HOST, credentials) as channel:
        ops_stub = operation_service_pb2_grpc.OperationServiceStub(channel)
        while time.monotonic() < deadline:
            time.sleep(_POLL_INTERVAL)
            op = ops_stub.Get(
                operation_service_pb2.GetOperationRequest(operation_id=operation_id),
                metadata=metadata,
            )
            if op.done:
                break
        else:
            raise TimeoutError(f"SpeechKit operation {operation_id} timed out after {_POLL_TIMEOUT}s")

    if op.HasField("error"):
        raise RuntimeError(f"SpeechKit error {op.error.code}: {op.error.message}")

    # 3. Unpack StreamingResponseList from operation.response
    result = stt_pb2.StreamingResponseList()
    op.response.Unpack(result)

    return _parse_streaming_responses(result.streaming_responses)


def _parse_streaming_responses(responses: list) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for response in responses:
        update = response.final
        if not update.alternatives:
            continue
        for alt in update.alternatives:
            text = alt.text.strip()
            if not text:
                continue
            words = list(alt.words)
            start_ms = words[0].start_time_ms if words else alt.start_time_ms
            end_ms = words[-1].end_time_ms if words else alt.end_time_ms
            speaker_tag = update.channel_tag or "0"
            try:
                speaker_num = int(speaker_tag)
            except (ValueError, TypeError):
                speaker_num = 0
            segments.append(TranscriptSegment(
                speaker=f"Speaker {speaker_num}",
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
            ))
    return sorted(segments, key=lambda s: s.start_ms)
