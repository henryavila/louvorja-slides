from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from louvorja_slides.alignment import MmsForcedAligner
from louvorja_slides.audio import decode_audio_16k_mono
from louvorja_slides.cache import audio_sha256, cache_key, cache_path, load_json, save_json
from louvorja_slides.separation import separate_vocals
from louvorja_slides.transcription import LocalWhisperTranscriber, Transcript

_CACHE_SCHEMA_VERSION = 3


@dataclass(frozen=True)
class LocalPipelineConfig:
    language: str = "pt"
    cache: bool = True
    cache_root: Path = Path(".louvorja-cache")
    whisper_model: str = "large-v3"
    vocal_separation: str = "htdemucs_ft"
    alignment: str = "none"


def transcribe_audio_local(
    audio_path: Path,
    *,
    config: LocalPipelineConfig | None = None,
    separate_vocals_fn: Any = separate_vocals,
    decode_fn: Any = decode_audio_16k_mono,
    transcriber: Any | None = None,
    aligner: Any | None = None,
) -> Transcript:
    cfg = config or LocalPipelineConfig()
    audio_path = Path(audio_path)
    audio_id = audio_sha256(audio_path)
    raw_variant = _variant(
        stage="raw",
        language=cfg.language,
        whisper_model=cfg.whisper_model,
        vocal_separation=cfg.vocal_separation,
        alignment="none",
    )
    aligned_variant = _variant(
        stage="aligned",
        language=cfg.language,
        whisper_model=cfg.whisper_model,
        vocal_separation=cfg.vocal_separation,
        alignment=cfg.alignment,
    )

    if cfg.cache and cfg.alignment != "none":
        cached_aligned = load_json(
            cache_path(cfg.cache_root, audio_id, "transcript", aligned_variant)
        )
        if cached_aligned is not None:
            return Transcript.from_dict(cached_aligned)

    selected_audio = audio_path
    if cfg.vocal_separation != "none":
        selected_audio = separate_vocals_fn(
            audio_path,
            audio_id=audio_id,
            cache_root=cfg.cache_root,
        )

    decoded = decode_fn(selected_audio)
    raw_transcript = _load_cached_transcript(cfg, audio_id, raw_variant)
    if raw_transcript is None:
        whisper = transcriber or LocalWhisperTranscriber(model_id=cfg.whisper_model)
        raw_transcript = whisper.transcribe_samples(
            samples=decoded.samples,
            sample_rate=decoded.sample_rate,
            duration_seconds=decoded.duration_seconds,
            language=cfg.language,
        )
        if cfg.cache:
            save_json(
                cache_path(cfg.cache_root, audio_id, "transcript", raw_variant),
                raw_transcript.to_dict(),
            )

    if cfg.alignment == "none":
        return raw_transcript

    mms = aligner or MmsForcedAligner()
    aligned = mms.align_transcript(
        raw_transcript,
        samples=decoded.samples,
        language=cfg.language,
    )
    if cfg.cache:
        save_json(
            cache_path(cfg.cache_root, audio_id, "transcript", aligned_variant),
            aligned.to_dict(),
        )
    return aligned


def _load_cached_transcript(
    cfg: LocalPipelineConfig,
    audio_id: str,
    variant: str,
) -> Transcript | None:
    if not cfg.cache:
        return None
    cached = load_json(cache_path(cfg.cache_root, audio_id, "transcript", variant))
    return Transcript.from_dict(cached) if cached is not None else None


def _variant(**values: object) -> str:
    return cache_key(
        {
            "schema": _CACHE_SCHEMA_VERSION,
            "sample_rate": 16000,
            "whisper_token_timestamps": True,
            "whisper_max_len": 1,
            "whisper_split_on_word": True,
            "whisper_entropy_thold": 2.2,
            "whisper_no_speech_thold": 0.7,
            **values,
        }
    )
