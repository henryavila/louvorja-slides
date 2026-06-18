from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from louvorja_slides.alignment import MmsForcedAligner
from louvorja_slides.audio import decode_audio_16k_mono
from louvorja_slides.cache import audio_sha256, cache_key, cache_path, load_json, save_json
from louvorja_slides.separation import separate_vocals
from louvorja_slides.transcription import (
    QUALITY_WHISPER_KWARGS,
    TRANSCRIPTION_FILTER_REVISION,
    LocalWhisperTranscriber,
    Transcript,
)

_CACHE_SCHEMA_VERSION = 3

# Bump when the alignment algorithm changes output for identical inputs, so
# stale aligned transcripts recompute without discarding raw Whisper caches.
# Revision 2: exact per-chunk frame grid + monotonic unalignable-word clamp.
_ALIGNMENT_REVISION = 2

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocalPipelineConfig:
    language: str = "pt"
    cache: bool = True
    cache_root: Path = Path(".louvorja-cache")
    whisper_model: str = "large-v3"
    vocal_separation: str = "htdemucs_ft"
    alignment: str = "none"
    device: str | None = None


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
        alignment_revision=_ALIGNMENT_REVISION,
    )

    if cfg.alignment != "none":
        cached_aligned = _load_cached_transcript(cfg, audio_id, aligned_variant)
        if cached_aligned is not None:
            return cached_aligned

    # Cache checks come before separation/decode so a cache hit costs no
    # ffmpeg decode and no Demucs run.
    decoded = None
    raw_transcript = _load_cached_transcript(cfg, audio_id, raw_variant)
    if raw_transcript is None:
        decoded = _select_and_decode(cfg, audio_path, audio_id, separate_vocals_fn, decode_fn)
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

    if decoded is None:
        decoded = _select_and_decode(cfg, audio_path, audio_id, separate_vocals_fn, decode_fn)
    mms = aligner or MmsForcedAligner(device=cfg.device)
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


def _select_and_decode(
    cfg: LocalPipelineConfig,
    audio_path: Path,
    audio_id: str,
    separate_vocals_fn: Any,
    decode_fn: Any,
) -> Any:
    selected_audio = audio_path
    if cfg.vocal_separation != "none":
        selected_audio = separate_vocals_fn(
            audio_path,
            audio_id=audio_id,
            cache_root=cfg.cache_root,
        )
    return decode_fn(selected_audio)


def _load_cached_transcript(
    cfg: LocalPipelineConfig,
    audio_id: str,
    variant: str,
) -> Transcript | None:
    if not cfg.cache:
        return None
    path = cache_path(cfg.cache_root, audio_id, "transcript", variant)
    try:
        cached = load_json(path)
        return Transcript.from_dict(cached) if cached is not None else None
    except (KeyError, TypeError, ValueError) as exc:
        # json.JSONDecodeError subclasses ValueError, so corrupt files land
        # here too. The entry is regenerable; discard it and recompute.
        _LOGGER.warning("discarding unreadable transcript cache %s: %s", path, exc)
        path.unlink(missing_ok=True)
        return None


def _variant(**values: object) -> str:
    return cache_key(
        {
            "schema": _CACHE_SCHEMA_VERSION,
            "sample_rate": 16000,
            "transcription_filter_revision": TRANSCRIPTION_FILTER_REVISION,
            **{f"whisper_{key}": value for key, value in QUALITY_WHISPER_KWARGS.items()},
            **values,
        }
    )
