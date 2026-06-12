from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any


class SeparationUnavailableError(RuntimeError):
    pass


def separate_vocals(
    audio_path: Path,
    *,
    audio_id: str,
    cache_root: Path,
    model_filename: str = "htdemucs_ft.yaml",
    separator_factory: Callable[..., Any] | None = None,
) -> Path:
    cache_dir = Path(cache_root) / audio_id
    cached_vocals = cache_dir / "vocals.wav"
    if cached_vocals.exists():
        return cached_vocals

    stems_dir = cache_dir / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)
    factory = separator_factory or _load_separator_factory()
    try:
        try:
            separator = factory(
                output_dir=str(stems_dir),
                output_format="WAV",
                log_level=logging.WARNING,
            )
        except TypeError:
            separator = factory(output_dir=str(stems_dir), log_level=logging.WARNING)
    except ImportError as exc:
        missing = getattr(exc, "name", None) or str(exc)
        raise SeparationUnavailableError(
            "audio-separator could not load required dependency "
            f"{missing!r}; install local transcription dependencies or run with "
            "`--vocal-separation none`"
        ) from exc

    separator.load_model(model_filename=model_filename)
    output_paths = separator.separate(str(audio_path))
    vocals_path = _find_vocals_path(stems_dir, output_paths)
    if vocals_path is None:
        raise SeparationUnavailableError("audio-separator did not produce a vocals stem")

    cache_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(vocals_path, cached_vocals)
    return cached_vocals


def _load_separator_factory() -> Callable[..., Any]:
    try:
        from audio_separator.separator import Separator
    except ImportError as exc:
        missing = getattr(exc, "name", None) or str(exc)
        raise SeparationUnavailableError(
            "audio-separator could not load required dependency "
            f"{missing!r}; install local transcription dependencies or run with "
            "`--vocal-separation none`"
        ) from exc
    return Separator


def _find_vocals_path(stems_dir: Path, output_paths: list[str]) -> Path | None:
    candidates: list[Path] = []
    for output_path in output_paths:
        path = Path(output_path)
        if not path.is_absolute():
            path = stems_dir / path
        candidates.append(path)
    candidates.extend(stems_dir.glob("*[Vv]ocals*.wav"))

    for candidate in candidates:
        if "vocals" in candidate.name.lower() and candidate.exists():
            return candidate
    return None
