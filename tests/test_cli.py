from __future__ import annotations

import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import audio_to_slja
from louvorja_slides.engines import AudioToDocumentConfig
from louvorja_slides.slja import Slide


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
    def test_main_selects_engine_transcribes_audio_and_writes_slja(self) -> None:
        calls: list[tuple[str, Path, AudioToDocumentConfig]] = []

        class FakeEngine:
            def transcribe(
                self, audio_path: Path, config: AudioToDocumentConfig
            ) -> SimpleNamespace:
                calls.append(("transcribe", audio_path, config))
                return _fake_doc()

        def fake_select_engine(engine_name: str) -> FakeEngine:
            calls.append(("select", Path(engine_name), AudioToDocumentConfig()))
            return FakeEngine()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            output_path = tmp_path / "out.slja"
            audio_path.write_bytes(b"audio bytes")

            with (
                patch("audio_to_slja.select_engine", side_effect=fake_select_engine),
                redirect_stdout(StringIO()),
            ):
                exit_code = audio_to_slja.main(
                    [
                        str(audio_path),
                        "--output",
                        str(output_path),
                        "--title",
                        "Titulo final",
                        "--engine",
                        "local",
                        "--device",
                        "cpu",
                        "--whisper-model",
                        "medium",
                        "--no-cache",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(calls[0][0], "select")
            self.assertEqual(str(calls[0][1]), "local")
            self.assertEqual(calls[1][0], "transcribe")
            self.assertEqual(calls[1][1], audio_path)
            self.assertEqual(calls[1][2].language, "pt")
            self.assertEqual(calls[1][2].cache, False)
            self.assertEqual(calls[1][2].force_mock, False)
            self.assertEqual(calls[1][2].backend, "cpu")
            self.assertEqual(calls[1][2].whisper_model, "medium")
            self.assertEqual(calls[1][2].title, "Titulo final")

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

    def test_main_fails_before_writing_when_quality_gate_rejects_output(self) -> None:
        class FakeEngine:
            def transcribe(
                self, audio_path: Path, config: AudioToDocumentConfig
            ) -> SimpleNamespace:
                return _fake_doc()

        writes: list[Path] = []
        bad_slides = [
            Slide(
                lines=("Linha principal longa demais para leitura",),
                start_seconds=1.0,
                aux_text="trecho extra que deveria virar outro slide",
            )
        ]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            output_path = tmp_path / "out.slja"
            audio_path.write_bytes(b"audio bytes")
            stderr = StringIO()

            with (
                patch("audio_to_slja.select_engine", return_value=FakeEngine()),
                patch("audio_to_slja.extract_lyric_slides", return_value=bad_slides),
                patch("audio_to_slja.write_slja", side_effect=lambda **kwargs: writes.append(kwargs["output_path"])),
                redirect_stderr(stderr),
            ):
                exit_code = audio_to_slja.main(
                    [str(audio_path), "--output", str(output_path), "--engine", "local"]
                )

        self.assertEqual(exit_code, 1)
        self.assertEqual(writes, [])
        self.assertIn("quality gate failed", stderr.getvalue())

    def test_main_can_warn_and_write_when_quality_gate_rejects_output(self) -> None:
        class FakeEngine:
            def transcribe(
                self, audio_path: Path, config: AudioToDocumentConfig
            ) -> SimpleNamespace:
                return _fake_doc()

        writes: list[Path] = []
        bad_slides = [
            Slide(
                lines=("Linha principal longa demais para leitura",),
                start_seconds=1.0,
                aux_text="trecho extra que deveria virar outro slide",
            )
        ]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            output_path = tmp_path / "out.slja"
            audio_path.write_bytes(b"audio bytes")
            stderr = StringIO()

            with (
                patch("audio_to_slja.select_engine", return_value=FakeEngine()),
                patch("audio_to_slja.extract_lyric_slides", return_value=bad_slides),
                patch("audio_to_slja.write_slja", side_effect=lambda **kwargs: writes.append(kwargs["output_path"])),
                redirect_stderr(stderr),
                redirect_stdout(StringIO()),
            ):
                exit_code = audio_to_slja.main(
                    [
                        str(audio_path),
                        "--output",
                        str(output_path),
                        "--engine",
                        "local",
                        "--quality-gate",
                        "warn",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(writes, [output_path])
        self.assertIn("quality gate failed", stderr.getvalue())

    def test_main_validates_existing_slja_without_transcribing(self) -> None:
        lja = "\r\n".join(
            [
                "[Geral]",
                "slides=3",
                "url_musica=audio\\song.mp3",
                "",
                "[Slide:1]",
                "tipo=CAPA",
                "letra=Titulo",
                "tempo=0",
                "",
                "[Slide:2]",
                "tipo=LETRA",
                "letra=Declarado guerra contra o enganador",
                "tempo=576000",
                "",
                "[Slide:3]",
                "tipo=LETRA",
                "letra=",
                "tempo=960000",
                "",
            ]
        ).encode("cp1252")

        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "song.slja"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("slides.lja", lja)
            stdout = StringIO()
            stderr = StringIO()

            with (
                patch("audio_to_slja.select_engine") as select_engine,
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                exit_code = audio_to_slja.main(
                    [str(archive_path), "--quality-gate", "warn"]
                )

        self.assertEqual(exit_code, 0)
        select_engine.assert_not_called()
        self.assertIn("SLJA quality:", stdout.getvalue())
        self.assertIn("quality gate failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
