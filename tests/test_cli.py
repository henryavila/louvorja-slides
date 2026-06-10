from __future__ import annotations

import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import audio_to_slja


def _fake_doc() -> SimpleNamespace:
    return SimpleNamespace(
        metadata=SimpleNamespace(title="Doc title", artist=None),
        sections=[
            SimpleNamespace(
                lines=[
                    SimpleNamespace(
                        line_type="lyric",
                        text="Fala comigo",
                        word_alignments=[
                            SimpleNamespace(timestamp=SimpleNamespace(start=7.4, end=8.0))
                        ],
                    )
                ]
            )
        ],
    )


class CliTest(unittest.TestCase):
    def test_main_transcribes_audio_and_writes_slja(self) -> None:
        calls = []

        def fake_transcribe(audio_path: Path, **kwargs: object) -> SimpleNamespace:
            calls.append((audio_path, kwargs))
            return _fake_doc()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            output_path = tmp_path / "out.slja"
            audio_path.write_bytes(b"audio bytes")

            with (
                patch("audio_to_slja.load_transcribe", return_value=fake_transcribe),
                redirect_stdout(StringIO()),
            ):
                exit_code = audio_to_slja.main(
                    [
                        str(audio_path),
                        "--output",
                        str(output_path),
                        "--title",
                        "Titulo final",
                        "--device",
                        "mock",
                        "--no-cache",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], audio_path)
            self.assertEqual(
                calls[0][1],
                {
                    "language": "pt",
                    "cache": False,
                    "force_mock": True,
                    "backend": None,
                },
            )

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


if __name__ == "__main__":
    unittest.main()
