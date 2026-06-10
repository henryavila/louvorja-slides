from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

from louvorja_slides.slja import (
    Slide,
    extract_lyric_slides,
    format_timestamp,
    render_lja,
    write_slja,
)


def _word(text: str, start: float, end: float | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        timestamp=SimpleNamespace(start=start, end=end if end is not None else start + 0.5),
    )


def _line(text: str, start: float) -> SimpleNamespace:
    return SimpleNamespace(
        line_type="lyric",
        text=text,
        word_alignments=[_word(text.split()[0], start)],
    )


class SljaExporterTest(unittest.TestCase):
    def test_format_timestamp_floors_seconds_so_cues_do_not_start_late(self) -> None:
        self.assertEqual(format_timestamp(0), "00:00:00")
        self.assertEqual(format_timestamp(65.9), "00:01:05")
        self.assertEqual(format_timestamp(3661.2), "01:01:01")

    def test_extract_lyric_slides_groups_lines_and_uses_first_word_time(self) -> None:
        doc = SimpleNamespace(
            sections=[
                SimpleNamespace(
                    lines=[
                        _line("Primeira linha", 8.7),
                        _line("Segunda linha", 11.2),
                        _line("Terceira linha", 14.9),
                    ]
                )
            ]
        )

        slides = extract_lyric_slides(doc, lines_per_slide=2)

        self.assertEqual(
            slides,
            [
                Slide(lines=("Primeira linha", "Segunda linha"), start_seconds=8.7),
                Slide(lines=("Terceira linha",), start_seconds=14.9),
            ],
        )

    def test_render_lja_uses_louvorja_fields_cp1252_and_crlf(self) -> None:
        data = render_lja(
            slides=[Slide(lines=("És tudo", "Não temas"), start_seconds=12.4)],
            title="Canção teste",
            audio_name="song.mp3",
            version="25.0.test",
        )

        text = data.decode("cp1252")

        self.assertIn("[Geral]\r\n", text)
        self.assertIn("slides=2\r\n", text)
        self.assertIn("versao=25.0.test\r\n", text)
        self.assertIn("audio=audio\\song.mp3\r\n", text)
        self.assertIn("[Slide:1]\r\n", text)
        self.assertIn("tipo=CAPA\r\n", text)
        self.assertIn("letra=Canção teste\r\n", text)
        self.assertIn("[Slide:2]\r\n", text)
        self.assertIn("tipo=LETRA\r\n", text)
        self.assertIn("letra=És tudo|Não temas\r\n", text)
        self.assertIn("tempo=00:00:12\r\n", text)
        self.assertNotIn("\n[Geral]\n", text)

    def test_write_slja_embeds_audio_and_slides_lja(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            out_path = tmp_path / "song.slja"
            audio_path.write_bytes(b"fake mp3 bytes")

            write_slja(
                audio_path=audio_path,
                output_path=out_path,
                slides=[Slide(lines=("Fala comigo",), start_seconds=3.0)],
                title="Fala comigo",
            )

            with zipfile.ZipFile(out_path) as archive:
                self.assertEqual(set(archive.namelist()), {"slides.lja", "audio\\song.mp3"})
                self.assertEqual(archive.read("audio\\song.mp3"), b"fake mp3 bytes")
                text = archive.read("slides.lja").decode("cp1252")

            self.assertIn("audio=audio\\song.mp3\r\n", text)
            self.assertIn("letra=Fala comigo\r\n", text)


if __name__ == "__main__":
    unittest.main()
