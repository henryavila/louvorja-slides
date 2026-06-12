from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from louvorja_slides.audio import AudioDecodeError, decode_audio_16k_mono


def _write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes((np.array([0, 1000, -1000], dtype=np.int16)).tobytes())


class AudioDecodeTest(unittest.TestCase):
    def test_decode_audio_uses_ffmpeg_and_returns_float32_samples(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
            calls.append(command)
            _write_wav(Path(command[-1]))
            return SimpleNamespace(returncode=0, stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "song.mp3"
            audio_path.write_bytes(b"fake")

            decoded = decode_audio_16k_mono(audio_path, run=fake_run, ffmpeg_exe="ffmpeg")

        self.assertEqual(decoded.sample_rate, 16000)
        self.assertEqual(decoded.samples.dtype, np.float32)
        self.assertEqual(len(decoded.samples), 3)
        self.assertIn("-ar", calls[0])
        self.assertIn("16000", calls[0])
        self.assertIn("-ac", calls[0])
        self.assertIn("1", calls[0])

    def test_decode_audio_raises_clear_error_on_ffmpeg_failure(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(returncode=1, stderr="bad audio")

        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "song.mp4"
            audio_path.write_bytes(b"fake")

            with self.assertRaisesRegex(AudioDecodeError, "bad audio"):
                decode_audio_16k_mono(audio_path, run=fake_run, ffmpeg_exe="ffmpeg")


if __name__ == "__main__":
    unittest.main()
