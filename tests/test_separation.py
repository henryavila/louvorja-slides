from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from louvorja_slides.separation import SeparationUnavailableError, separate_vocals


class SeparationTest(unittest.TestCase):
    def test_separate_vocals_returns_existing_cached_vocal_stem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cached = root / "abc123" / "vocals.wav"
            cached.parent.mkdir(parents=True)
            cached.write_bytes(b"wav")
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")

            result = separate_vocals(audio, audio_id="abc123", cache_root=root)

        self.assertEqual(result, cached)

    def test_separate_vocals_fails_clearly_when_dependency_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "song.mp3"
            audio.write_bytes(b"audio")

            with self.assertRaisesRegex(SeparationUnavailableError, "audio-separator"):
                separate_vocals(
                    audio,
                    audio_id="abc123",
                    cache_root=Path(tmp),
                    separator_factory=lambda *args, **kwargs: (_ for _ in ()).throw(
                        ImportError("missing")
                    ),
                )

    def test_separate_vocals_loads_htdemucs_model_before_separating(self) -> None:
        events = []

        class FakeSeparator:
            def __init__(self, output_dir: str, output_format: str, log_level: int) -> None:
                self.output_dir = Path(output_dir)

            def load_model(self, model_filename: str) -> None:
                events.append(("load", model_filename))

            def separate(self, audio_file_path: str) -> list[str]:
                events.append(("separate", audio_file_path))
                output = self.output_dir / "song_(Vocals)_htdemucs_ft.wav"
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"vocals")
                return [str(output)]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")

            result = separate_vocals(
                audio,
                audio_id="abc123",
                cache_root=root,
                separator_factory=FakeSeparator,
            )

        self.assertEqual(events[0], ("load", "htdemucs_ft.yaml"))
        self.assertEqual(events[1][0], "separate")
        self.assertEqual(result.name, "vocals.wav")


if __name__ == "__main__":
    unittest.main()
