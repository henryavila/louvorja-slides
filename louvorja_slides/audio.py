from __future__ import annotations

import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np


class AudioDecodeError(RuntimeError):
    pass


@dataclass(frozen=True)
class DecodedAudio:
    samples: np.ndarray
    sample_rate: int
    duration_seconds: float


RunFn = Callable[..., Any]


def decode_audio_16k_mono(
    audio_path: Path,
    *,
    run: RunFn = subprocess.run,
    ffmpeg_exe: str | None = None,
) -> DecodedAudio:
    audio_path = Path(audio_path)
    if ffmpeg_exe is None:
        try:
            import imageio_ffmpeg
        except ImportError as exc:
            raise AudioDecodeError(
                "audio decode requires imageio-ffmpeg; install ML dependencies"
            ) from exc
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "decoded.wav"
        command = [
            ffmpeg_exe,
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
        try:
            completed = run(command, capture_output=True, text=True)
        except OSError as exc:
            raise AudioDecodeError(f"ffmpeg failed to start: {exc}") from exc

        if getattr(completed, "returncode", 1) != 0:
            stderr = getattr(completed, "stderr", "")
            raise AudioDecodeError(str(stderr).strip() or "ffmpeg failed to decode audio")

        return _read_wav_float32(wav_path)


def _read_wav_float32(wav_path: Path) -> DecodedAudio:
    with wave.open(str(wav_path), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())

    if channels != 1 or sample_width != 2:
        raise AudioDecodeError("decoded audio must be mono 16-bit PCM")
    if sample_rate != 16000:
        raise AudioDecodeError("decoded audio must be 16000 Hz")

    pcm = np.frombuffer(frames, dtype=np.int16)
    samples = (pcm.astype(np.float32) / 32768.0).copy()
    return DecodedAudio(
        samples=samples,
        sample_rate=sample_rate,
        duration_seconds=float(len(samples)) / float(sample_rate),
    )
