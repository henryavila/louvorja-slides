from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Callable

from louvorja_slides.cache import cache_key


class SeparationUnavailableError(RuntimeError):
    pass


class SeparationError(RuntimeError):
    pass


SeparatorFactory = Callable[..., Any]


def separate_vocals(
    audio_path: Path,
    *,
    audio_id: str,
    cache_root: Path,
    model_filename: str = "htdemucs_ft.yaml",
    separator_factory: SeparatorFactory | None = None,
) -> Path:
    audio_path = Path(audio_path)
    cache_dir = Path(cache_root) / audio_id / "separation" / _separator_variant(model_filename)
    cached_vocals = cache_dir / "vocals.wav"
    if cached_vocals.exists():
        return cached_vocals

    stems_dir = cache_dir / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)
    factory = separator_factory or _load_separator_factory()

    try:
        separator = factory(
            output_dir=str(stems_dir),
            output_format="WAV",
            log_level=logging.WARNING,
        )
        separator.load_model(model_filename)
        generated = [Path(path) for path in separator.separate(str(audio_path))]
    except ImportError as exc:
        raise SeparationUnavailableError(
            "vocal separation requires audio-separator; install ML dependencies "
            "or run with --vocal-separation none"
        ) from exc
    except Exception as exc:
        raise SeparationError(f"vocal separation failed; bypass with --vocal-separation none: {exc}") from exc

    vocal_stems = [path for path in generated if "vocal" in path.name.lower()]
    if not vocal_stems:
        vocal_stems = [path for path in stems_dir.glob("*") if "vocal" in path.name.lower()]
    if not vocal_stems:
        raise SeparationError(
            "vocal separation did not produce a vocals stem; bypass with --vocal-separation none"
        )

    cached_vocals.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(vocal_stems[0], cached_vocals)
    return cached_vocals


def _load_separator_factory() -> SeparatorFactory:
    try:
        from audio_separator.separator import Separator
    except ImportError as exc:
        raise SeparationUnavailableError(
            "vocal separation requires audio-separator; install ML dependencies "
            "or run with --vocal-separation none"
        ) from exc
    return Separator


def _separator_variant(model_filename: str) -> str:
    return cache_key({"model_filename": model_filename, "schema_version": 1})
