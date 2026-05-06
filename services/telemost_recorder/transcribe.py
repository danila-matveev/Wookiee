from dataclasses import dataclass
from pathlib import Path

import grpc
from yandex.cloud.ai.stt.v3 import stt_pb2, stt_service_pb2_grpc

from services.telemost_recorder.config import SPEECHKIT_API_KEY, YANDEX_FOLDER_ID

_STT_HOST = "stt.api.cloud.yandex.net:443"


@dataclass
class TranscriptSegment:
    speaker: str
    start_ms: int
    end_ms: int
    text: str


def transcribe_audio(audio_path: Path) -> list[TranscriptSegment]:
    """Send audio to SpeechKit v3 via gRPC, return speaker-tagged segments."""
    audio_bytes = audio_path.read_bytes()

    request = stt_pb2.RecognizeFileRequest(
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
    )

    metadata = [
        ("authorization", f"Api-Key {SPEECHKIT_API_KEY}"),
        ("x-folder-id", YANDEX_FOLDER_ID),
    ]

    segments: list[TranscriptSegment] = []
    credentials = grpc.ssl_channel_credentials()

    with grpc.secure_channel(_STT_HOST, credentials) as channel:
        stub = stt_service_pb2_grpc.AsyncRecognizerStub(channel)
        for response in stub.RecognizeFile(request, metadata=metadata):
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
