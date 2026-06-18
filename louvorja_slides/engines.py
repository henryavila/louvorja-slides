from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from louvorja_slides.document import transcript_to_document
from louvorja_slides.transcription import Transcript


@dataclass(frozen=True)
class AudioToDocumentConfig:
    language: str = "pt"
    cache: bool = True
    cache_root: Path = Path(".louvorja-cache")
    title: str | None = None
    force_mock: bool = False
    backend: str | None = None
    whisper_model: str | None = None
    vocal_separation: str = "htdemucs_ft"
    alignment: str = "none"


@runtime_checkable
class AudioToDocumentEngine(Protocol):
    name: str

    def transcribe(self, audio_path: Path, config: AudioToDocumentConfig) -> Any: ...


class LocalEngine:
    name = "local"

    def __init__(
        self,
        transcribe_fn: Callable[[Path, AudioToDocumentConfig], Transcript] | None = None,
    ) -> None:
        self._transcribe_fn = transcribe_fn

    def transcribe(self, audio_path: Path, config: AudioToDocumentConfig) -> Any:
        if config.force_mock:
            raise ValueError(
                "--device mock is not supported; the local engine always runs "
                "the real pipeline."
            )
        if self._transcribe_fn is not None:
            transcript = self._transcribe_fn(audio_path, config)
        else:
            from louvorja_slides.local_pipeline import LocalPipelineConfig, transcribe_audio_local

            transcript = transcribe_audio_local(
                audio_path,
                config=LocalPipelineConfig(
                    language=config.language,
                    cache=config.cache,
                    cache_root=config.cache_root,
                    whisper_model=config.whisper_model or "large-v3",
                    vocal_separation=config.vocal_separation,
                    alignment=config.alignment,
                    device=config.backend,
                ),
            )
        return transcript_to_document(transcript, title=config.title or audio_path.stem)


def select_engine(
    engine: str = "auto",
    *,
    platform_system: str | None = None,
    platform_release: str | None = None,
) -> AudioToDocumentEngine:
    del platform_system, platform_release  # The local engine is cross-platform.
    normalized = engine.lower()
    if normalized in {"auto", "local"}:
        return LocalEngine()
    if normalized == "titan":
        raise ValueError(
            "engine 'titan' was removed; titan-chordpro-lib is reference-only, "
            "not a runtime dependency. Use --engine local."
        )
    raise ValueError("engine must be one of: auto, local")
