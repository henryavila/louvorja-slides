from __future__ import annotations

import subprocess
import tempfile
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


class AudioDecodeError(RuntimeError):
    pass


@dataclass(frozen=True)
class DecodedAudio:
    samples: np.ndarray
    sample_rate: int
    duration_seconds: float


def decode_audio_16k_mono(
    audio_path: Path,
    *,
    run: Callable[..., Any] = subprocess.run,
    ffmpeg_exe: str | None = None,
) -> DecodedAudio:
    ffmpeg = ffmpeg_exe or _default_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "decoded.wav"
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(audio_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-acodec",
            "pcm_s16le",
            str(wav_path),
        ]
        result = run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            stderr = str(getattr(result, "stderr", "")).strip()
            raise AudioDecodeError(stderr or f"ffmpeg failed to decode {audio_path}")

        with wave.open(str(wav_path), "rb") as handle:
            sample_rate = handle.getframerate()
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            frames = handle.readframes(handle.getnframes())

        if sample_rate != 16000 or channels != 1 or sample_width != 2:
            raise AudioDecodeError("decoded audio must be 16 kHz mono PCM16")

        int_samples = np.frombuffer(frames, dtype="<i2")
        samples = int_samples.astype(np.float32) / 32768.0
        return DecodedAudio(
            samples=samples,
            sample_rate=sample_rate,
            duration_seconds=float(len(samples)) / float(sample_rate),
        )


def _default_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise AudioDecodeError(
            "imageio-ffmpeg is not installed; install local transcription dependencies"
        ) from exc
    return str(imageio_ffmpeg.get_ffmpeg_exe())
