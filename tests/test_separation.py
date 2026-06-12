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
        def missing_factory(**kwargs: object) -> object:
            raise ModuleNotFoundError("No module named 'onnxruntime'")

        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "song.mp3"
            audio.write_bytes(b"audio")

            with self.assertRaisesRegex(SeparationUnavailableError, "onnxruntime"):
                separate_vocals(
                    audio,
                    audio_id="abc123",
                    cache_root=Path(tmp),
                    separator_factory=missing_factory,
                )

    def test_separate_vocals_loads_htdemucs_model_before_separating(self) -> None:
        events: list[tuple[str, str]] = []
        produced: list[Path] = []

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
                produced.append(output)
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
            self.assertEqual(result.name, "vocals-htdemucs_ft.wav")
            self.assertEqual(result.read_bytes(), b"vocals")
            self.assertFalse(produced[0].exists(), "stem is moved, not copied")
            self.assertFalse(
                produced[0].parent.exists(),
                "intermediate stems are deleted after the vocal stem is cached",
            )

    def test_separate_vocals_cache_is_scoped_per_model(self) -> None:
        events: list[str] = []

        class FakeSeparator:
            def __init__(self, output_dir: str, output_format: str, log_level: int) -> None:
                self.output_dir = Path(output_dir)

            def load_model(self, model_filename: str) -> None:
                events.append("load")

            def separate(self, audio_file_path: str) -> list[str]:
                events.append("separate")
                output = self.output_dir / "song_(Vocals)_other.wav"
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"other vocals")
                return [str(output)]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cached_default = root / "abc123" / "vocals-htdemucs_ft.wav"
            cached_default.parent.mkdir(parents=True)
            cached_default.write_bytes(b"default vocals")
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")

            result = separate_vocals(
                audio,
                audio_id="abc123",
                cache_root=root,
                model_filename="other.yaml",
                separator_factory=FakeSeparator,
            )

            self.assertEqual(events, ["load", "separate"])
            self.assertEqual(result.name, "vocals-other.wav")
            self.assertEqual(result.read_bytes(), b"other vocals")

    def test_legacy_vocals_cache_is_not_reused_for_non_default_model(self) -> None:
        events: list[str] = []

        class FakeSeparator:
            def __init__(self, output_dir: str, output_format: str, log_level: int) -> None:
                self.output_dir = Path(output_dir)

            def load_model(self, model_filename: str) -> None:
                events.append("load")

            def separate(self, audio_file_path: str) -> list[str]:
                events.append("separate")
                output = self.output_dir / "song_(Vocals)_other.wav"
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"other vocals")
                return [str(output)]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "abc123" / "vocals.wav"
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b"legacy default vocals")
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")

            result = separate_vocals(
                audio,
                audio_id="abc123",
                cache_root=root,
                model_filename="other.yaml",
                separator_factory=FakeSeparator,
            )

            self.assertEqual(events, ["load", "separate"])
            self.assertEqual(result.name, "vocals-other.wav")

    def test_separate_vocals_calls_factory_once_and_propagates_type_errors(self) -> None:
        calls: list[dict[str, object]] = []

        def broken_factory(**kwargs: object) -> object:
            calls.append(kwargs)
            raise TypeError("real construction bug")

        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "song.mp3"
            audio.write_bytes(b"audio")

            with self.assertRaisesRegex(TypeError, "real construction bug"):
                separate_vocals(
                    audio,
                    audio_id="abc123",
                    cache_root=Path(tmp),
                    separator_factory=broken_factory,
                )

        self.assertEqual(len(calls), 1)

    def test_separate_vocals_supports_factory_without_output_format(self) -> None:
        class OldSeparator:
            def __init__(self, output_dir: str, log_level: int) -> None:
                self.output_dir = Path(output_dir)

            def load_model(self, model_filename: str) -> None:
                pass

            def separate(self, audio_file_path: str) -> list[str]:
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
                separator_factory=OldSeparator,
            )

            self.assertEqual(result.name, "vocals-htdemucs_ft.wav")

    def test_interrupted_separation_leaves_no_cache_marker(self) -> None:
        class ExplodingSeparator:
            def __init__(self, output_dir: str, output_format: str, log_level: int) -> None:
                self.output_dir = Path(output_dir)

            def load_model(self, model_filename: str) -> None:
                pass

            def separate(self, audio_file_path: str) -> list[str]:
                partial = self.output_dir / "song_(Vocals)_htdemucs_ft.wav"
                partial.parent.mkdir(parents=True, exist_ok=True)
                partial.write_bytes(b"par")
                raise RuntimeError("interrupted mid-separation")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")

            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                separate_vocals(
                    audio,
                    audio_id="abc123",
                    cache_root=root,
                    separator_factory=ExplodingSeparator,
                )

            self.assertFalse((root / "abc123" / "vocals-htdemucs_ft.wav").exists())
            self.assertFalse((root / "abc123" / "vocals.wav").exists())


if __name__ == "__main__":
    unittest.main()
