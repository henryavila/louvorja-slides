from __future__ import annotations

import inspect
import logging
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

_DEFAULT_MODEL_FILENAME = "htdemucs_ft.yaml"


class SeparationUnavailableError(RuntimeError):
    pass


def separate_vocals(
    audio_path: Path,
    *,
    audio_id: str,
    cache_root: Path,
    model_filename: str = _DEFAULT_MODEL_FILENAME,
    separator_factory: Callable[..., Any] | None = None,
) -> Path:
    model_name = Path(model_filename).stem
    cache_dir = Path(cache_root) / audio_id
    cached_vocals = cache_dir / f"vocals-{model_name}.wav"
    if cached_vocals.exists():
        return cached_vocals
    legacy_vocals = cache_dir / "vocals.wav"
    if model_filename == _DEFAULT_MODEL_FILENAME and legacy_vocals.exists():
        return legacy_vocals

    cache_dir.mkdir(parents=True, exist_ok=True)
    # A unique working directory per run keeps concurrent separations of the
    # same audio from clobbering each other's in-flight stems, and guarantees
    # the vocals glob below never picks up a partial stem from a failed run.
    stems_dir = Path(
        tempfile.mkdtemp(prefix=f"stems-{model_name}-", dir=cache_dir)
    )
    try:
        factory = separator_factory or _load_separator_factory()
        factory_kwargs: dict[str, Any] = {
            "output_dir": str(stems_dir),
            "log_level": logging.WARNING,
        }
        if _accepts_keyword(factory, "output_format"):
            factory_kwargs["output_format"] = "WAV"
        try:
            separator = factory(**factory_kwargs)
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
            raise SeparationUnavailableError(
                "audio-separator did not produce a vocals stem"
            )

        # The cached file is the cache-hit marker, so it must appear
        # atomically: a rename never leaves a truncated vocals file behind.
        os.replace(vocals_path, cached_vocals)
    finally:
        shutil.rmtree(stems_dir, ignore_errors=True)
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


def _accepts_keyword(factory: Callable[..., Any], name: str) -> bool:
    try:
        parameters = inspect.signature(factory).parameters
    except (TypeError, ValueError):
        return True
    if name in parameters:
        return True
    return any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


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
