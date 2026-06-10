from __future__ import annotations

import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import audio_to_slja
from louvorja_slides.local_pipeline import LocalPipelineConfig
from louvorja_slides.transcription import Transcript, TranscribedWord


def _fake_transcript() -> Transcript:
    return Transcript(
        words=[
            TranscribedWord("Fala", 7.4, 7.8),
            TranscribedWord("comigo", 7.9, 8.4),
        ],
        detected_language="pt",
        duration_seconds=30.0,
    )


class CliTest(unittest.TestCase):
    def test_main_transcribes_audio_and_writes_slja(self) -> None:
        calls = []

        def fake_transcribe(audio_path: Path, *, config: LocalPipelineConfig) -> Transcript:
            calls.append((audio_path, config))
            return _fake_transcript()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            output_path = tmp_path / "out.slja"
            audio_path.write_bytes(b"audio bytes")

            with (
                patch("audio_to_slja.transcribe_audio_local", side_effect=fake_transcribe),
                redirect_stdout(StringIO()),
            ):
                exit_code = audio_to_slja.main(
                    [
                        str(audio_path),
                        "--output",
                        str(output_path),
                        "--title",
                        "Titulo final",
                        "--whisper-model",
                        "medium",
                        "--vocal-separation",
                        "none",
                        "--alignment",
                        "none",
                        "--cache-dir",
                        str(tmp_path / "cache"),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], audio_path)
            self.assertEqual(calls[0][1].language, "pt")
            self.assertEqual(calls[0][1].whisper_model, "medium")
            self.assertEqual(calls[0][1].vocal_separation, "none")
            self.assertEqual(calls[0][1].alignment, "none")
            self.assertEqual(calls[0][1].cache_root, tmp_path / "cache")

            with zipfile.ZipFile(output_path) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {
                        "slides.lja",
                        "audio\\song.mp3",
                        "imagens\\Capa.jpg",
                        "imagens\\slides.jpg",
                    },
                )
                text = archive.read("slides.lja").decode("cp1252")

            self.assertIn("letra=Titulo final\r\n", text)
            self.assertIn("letra=Fala comigo\r\n", text)
            self.assertIn("tempo=00:00:07\r\n", text)

    def test_cli_requires_explicit_flag_to_disable_quality_stages(self) -> None:
        parser = audio_to_slja.build_parser()
        args = parser.parse_args(
            ["song.mp3", "--vocal-separation", "none", "--alignment", "none"]
        )

        self.assertEqual(args.vocal_separation, "none")
        self.assertEqual(args.alignment, "none")

    def test_cli_defaults_to_quality_first_local_config(self) -> None:
        parser = audio_to_slja.build_parser()
        args = parser.parse_args(["song.mp3"])

        self.assertEqual(args.whisper_model, "large-v3")
        self.assertEqual(args.vocal_separation, "htdemucs_ft")
        self.assertEqual(args.alignment, "mms")


if __name__ == "__main__":
    unittest.main()
