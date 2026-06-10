from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from louvorja_slides.alignment import MmsForcedAligner
from louvorja_slides.audio import DecodedAudio, decode_audio_16k_mono
from louvorja_slides.cache import audio_sha256, cache_key, cache_path, load_json, save_json
from louvorja_slides.separation import separate_vocals
from louvorja_slides.transcription import LocalWhisperTranscriber, Transcript


DecodeFn = Callable[[Path], DecodedAudio]
SeparateVocalsFn = Callable[..., Path]


@dataclass(frozen=True)
class LocalPipelineConfig:
    language: str = "pt"
    cache_root: Path = Path(".louvorja-cache")
    whisper_model: str = "large-v3"
    vocal_separation: str = "htdemucs_ft"
    alignment: str = "mms"
    separator_model: str = "htdemucs_ft.yaml"
    schema_version: int = 1

    def cache_identity(self, *, stage: str) -> dict[str, object]:
        identity: dict[str, object] = {
            "stage": stage,
            "schema_version": self.schema_version,
            "language": self.language,
            "audio": {"sample_rate": 16000, "channels": 1, "codec": "pcm_s16le"},
            "vocal_separation": self.vocal_separation,
            "separator_model": self.separator_model if self.vocal_separation != "none" else None,
            "whisper_model": self.whisper_model,
            "whisper": {
                "token_timestamps": True,
                "max_len": 1,
                "split_on_word": True,
                "entropy_thold": 2.2,
                "no_speech_thold": 0.7,
            },
        }
        if stage == "aligned":
            identity["alignment"] = self.alignment
            identity["mms"] = {"frame_seconds": 0.02} if self.alignment == "mms" else None
        return identity


def transcribe_audio_local(
    audio_path: Path,
    *,
    config: LocalPipelineConfig | None = None,
    separate_vocals_fn: SeparateVocalsFn = separate_vocals,
    decode_fn: DecodeFn = decode_audio_16k_mono,
    transcriber: Any | None = None,
    aligner: Any | None = None,
) -> Transcript:
    config = config or LocalPipelineConfig()
    audio_path = Path(audio_path)
    audio_id = audio_sha256(audio_path)

    aligned_cache = _cache_file(config, audio_id, "aligned")
    if config.alignment == "mms":
        cached_aligned = load_json(aligned_cache)
        if cached_aligned is not None:
            return Transcript.from_dict(cached_aligned)

    selected_audio = audio_path
    if config.vocal_separation != "none":
        selected_audio = separate_vocals_fn(
            audio_path,
            audio_id=audio_id,
            cache_root=config.cache_root,
            model_filename=config.separator_model,
        )

    raw_cache = _cache_file(config, audio_id, "raw")
    cached_raw = load_json(raw_cache)
    if cached_raw is not None and config.alignment == "none":
        return Transcript.from_dict(cached_raw)

    decoded = decode_fn(selected_audio)
    if cached_raw is not None:
        transcript = Transcript.from_dict(cached_raw)
    else:
        whisper = transcriber or LocalWhisperTranscriber(model_id=config.whisper_model)
        transcript = whisper.transcribe_samples(
            samples=decoded.samples,
            sample_rate=decoded.sample_rate,
            duration_seconds=decoded.duration_seconds,
            language=config.language,
        )
        if not transcript.words:
            raise ValueError(
                "local transcription produced no lyric words; try a larger model or inspect the vocal stem"
            )
        save_json(raw_cache, transcript.to_dict())

    if config.alignment == "none":
        return transcript
    if config.alignment != "mms":
        raise ValueError(f"unsupported alignment mode: {config.alignment}")

    mms = aligner or MmsForcedAligner()
    aligned = mms.align_transcript(
        transcript,
        samples=decoded.samples,
        language=config.language,
    )
    save_json(aligned_cache, aligned.to_dict())
    return aligned


def _cache_file(config: LocalPipelineConfig, audio_id: str, stage: str) -> Path:
    return cache_path(
        config.cache_root,
        audio_id,
        "transcript",
        cache_key(config.cache_identity(stage=stage)),
    )
