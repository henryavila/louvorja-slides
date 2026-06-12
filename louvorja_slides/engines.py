from __future__ import annotations

import platform
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


class MacTitanEngine:
    name = "titan"

    def __init__(self, transcribe_fn: Callable[..., Any] | None = None) -> None:
        self._transcribe_fn = transcribe_fn

    def transcribe(self, audio_path: Path, config: AudioToDocumentConfig) -> Any:
        transcribe = self._transcribe_fn or _load_titan_transcribe()
        kwargs: dict[str, Any] = {
            "language": config.language,
            "cache": config.cache,
            "force_mock": config.force_mock,
            "backend": config.backend,
        }
        if config.cache and config.cache_root is not None:
            kwargs["cache_root"] = config.cache_root
        if config.whisper_model is not None:
            kwargs["transcription_model_id"] = config.whisper_model
        return transcribe(audio_path, **kwargs)


class LocalLinuxEngine:
    name = "local"

    def __init__(
        self,
        transcribe_fn: Callable[[Path, AudioToDocumentConfig], Transcript] | None = None,
    ) -> None:
        self._transcribe_fn = transcribe_fn

    def transcribe(self, audio_path: Path, config: AudioToDocumentConfig) -> Any:
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
                ),
            )
        return transcript_to_document(transcript, title=config.title or audio_path.stem)


def select_engine(
    engine: str = "auto",
    *,
    platform_system: str | None = None,
    platform_release: str | None = None,
) -> AudioToDocumentEngine:
    normalized = engine.lower()
    if normalized == "local":
        return LocalLinuxEngine()
    if normalized == "titan":
        return MacTitanEngine()
    if normalized != "auto":
        raise ValueError("engine must be one of: auto, local, titan")

    system = platform_system or platform.system()
    release = platform_release or platform.release()
    if system == "Darwin":
        return MacTitanEngine()
    if system == "Linux" or _is_wsl_release(release):
        return LocalLinuxEngine()
    raise RuntimeError(
        f"unsupported platform {system!r}; pass `--engine local` or `--engine titan`"
    )


def _load_titan_transcribe() -> Callable[..., Any]:
    try:
        from titan_chordpro.orchestrator import transcribe
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "titan-chordpro-lib is not installed. On macOS, install the optional "
            "Titan dependency with `pip install -e ../titan-chordpro-lib[mac]`."
        ) from exc
    return transcribe


def _is_wsl_release(release: str) -> bool:
    lowered = release.lower()
    return "microsoft" in lowered or "wsl" in lowered
