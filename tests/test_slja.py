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
    read_slja,
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


def _aligned_line(text: str, start: float = 0.0) -> SimpleNamespace:
    words = [
        _word(token, start + index * 0.5, start + index * 0.5 + 0.4)
        for index, token in enumerate(text.split())
    ]
    return SimpleNamespace(line_type="lyric", text=text, word_alignments=words)


def _explicit_line(text: str, start: float, line_index: int) -> SimpleNamespace:
    line = _line(text, start)
    line.source_line_index = line_index
    line.source_section_index = 0
    return line


class SljaExporterTest(unittest.TestCase):
    def test_format_timestamp_floors_seconds_so_cues_do_not_start_late(self) -> None:
        self.assertEqual(format_timestamp(0), "00:00:00")
        self.assertEqual(format_timestamp(65.9), "00:01:05")
        self.assertEqual(format_timestamp(3661.2), "01:01:01")

    def test_extract_lyric_slides_uses_layout_rules_and_first_word_time(self) -> None:
        doc = SimpleNamespace(
            sections=[
                SimpleNamespace(
                    lines=[
                        _explicit_line("Primeira linha", 8.7, 0),
                        _explicit_line("Segunda linha", 11.2, 1),
                        _explicit_line("Terceira linha", 14.9, 2),
                    ]
                )
            ]
        )

        slides = extract_lyric_slides(doc, lines_per_slide=2)

        self.assertEqual(
            slides,
            [
                Slide(
                    lines=("Primeira linha", "Segunda linha"),
                    start_seconds=8.7,
                ),
                Slide(lines=("Terceira linha",), start_seconds=14.9),
            ],
        )

    def test_extract_lyric_slides_does_not_freeze_automatic_line_breaks(self) -> None:
        doc = SimpleNamespace(
            sections=[
                SimpleNamespace(
                    lines=[
                        _line("alfa beta", 0.0),
                        _line("gama delta", 1.0),
                        _line("eco foz", 2.0),
                        _line("hino luz", 3.0),
                    ]
                )
            ]
        )

        slides = extract_lyric_slides(doc, lines_per_slide=2)

        self.assertEqual(len(slides), 1)
        self.assertTrue(all(len(line) <= 34 for line in slides[0].lines))

    def test_extract_lyric_slides_preserves_explicit_source_line_breaks(self) -> None:
        doc = SimpleNamespace(
            sections=[
                SimpleNamespace(
                    lines=[
                        _explicit_line("alfa beta", 0.0, 0),
                        _explicit_line("gama delta", 1.0, 1),
                        _explicit_line("eco foz", 2.0, 2),
                    ]
                )
            ]
        )

        slides = extract_lyric_slides(doc, lines_per_slide=2)

        self.assertEqual(
            [slide.lines for slide in slides],
            [("alfa beta", "gama delta"), ("eco foz",)],
        )

    def test_extract_lyric_slides_collapses_repeated_lines_with_count_marker(self) -> None:
        doc = SimpleNamespace(
            sections=[
                SimpleNamespace(
                    lines=[
                        _line("Fala comigo", 1.0),
                        _line("Fala comigo", 7.0),
                        _line("Fala comigo", 13.0),
                    ]
                )
            ]
        )

        slides = extract_lyric_slides(doc)

        self.assertEqual(
            slides,
            [
                Slide(
                    lines=("Fala comigo",),
                    start_seconds=1.0,
                    aux_text="(3x)",
                ),
            ],
        )

    def test_extract_lyric_slides_can_disable_auxiliary_text(self) -> None:
        doc = SimpleNamespace(
            sections=[
                SimpleNamespace(
                    lines=[
                        _aligned_line(
                            "Nao devemos parar nao devemos temer pela tua misericordia"
                        ),
                    ]
                )
            ]
        )

        slides = extract_lyric_slides(
            doc,
            allow_auxiliary=False,
            hard_max_chars_per_line=28,
        )

        self.assertTrue(slides)
        self.assertTrue(all(not slide.aux_text for slide in slides))
        self.assertIn(
            "pela tua misericordia",
            " ".join(line for slide in slides for line in slide.lines),
        )

    def test_render_lja_uses_louvorja_fields_cp1252_and_crlf(self) -> None:
        data = render_lja(
            slides=[
                Slide(
                    lines=("És tudo", "Não temas"),
                    start_seconds=12.4,
                    aux_text="continua",
                )
            ],
            title="Canção teste",
            audio_name="song.mp3",
            version="25.0.test",
        )

        text = data.decode("cp1252")

        self.assertIn("[Geral]\r\n", text)
        self.assertIn("slides=2\r\n", text)
        self.assertIn("versao=25.0.test\r\n", text)
        self.assertIn("url_musica=audio\\song.mp3\r\n", text)
        self.assertIn("audio=1\r\n", text)
        self.assertIn("[Slide:1]\r\n", text)
        self.assertIn("tipo=CAPA\r\n", text)
        self.assertIn("letra=Canção teste\r\n", text)
        self.assertIn("imagem=imagens\\Capa.jpg\r\n", text)
        self.assertIn("imagem_posicao=5\r\n", text)
        self.assertIn("[Slide:2]\r\n", text)
        self.assertIn("tipo=LETRA\r\n", text)
        self.assertIn("letra=És tudo|Não temas\r\n", text)
        self.assertIn("letra_aux=continua\r\n", text)
        self.assertIn("imagem=imagens\\slides.jpg\r\n", text)
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
                self.assertEqual(
                    set(archive.namelist()),
                    {
                        "slides.lja",
                        "audio\\song.mp3",
                        "imagens\\Capa.jpg",
                        "imagens\\slides.jpg",
                    },
                )
                self.assertEqual(archive.read("audio\\song.mp3"), b"fake mp3 bytes")
                self.assertGreater(len(archive.read("imagens\\Capa.jpg")), 1000)
                self.assertGreater(len(archive.read("imagens\\slides.jpg")), 1000)
                text = archive.read("slides.lja").decode("cp1252")

            self.assertIn("url_musica=audio\\song.mp3\r\n", text)
            self.assertIn("audio=1\r\n", text)
            self.assertIn("letra=Fala comigo\r\n", text)
            self.assertIn("imagem=imagens\\Capa.jpg\r\n", text)
            self.assertIn("imagem=imagens\\slides.jpg\r\n", text)

    def test_write_slja_sanitizes_embedded_audio_filename_for_louvorja(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "DVD Adoradores [9yZt5ekdceI].mp3"
            out_path = tmp_path / "song.slja"
            audio_path.write_bytes(b"fake mp3 bytes")

            write_slja(
                audio_path=audio_path,
                output_path=out_path,
                slides=[Slide(lines=("Fala comigo",), start_seconds=3.0)],
                title="Fala comigo",
            )

            with zipfile.ZipFile(out_path) as archive:
                self.assertIn("audio\\DVD_Adoradores_9yZt5ekdceI.mp3", archive.namelist())
                text = archive.read("slides.lja").decode("cp1252")

        self.assertIn(
            "url_musica=audio\\DVD_Adoradores_9yZt5ekdceI.mp3\r\n",
            text,
        )

    def test_read_slja_parses_legacy_numeric_tempo_and_empty_lyric_slide(self) -> None:
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
                "letra=Primeira linha|Segunda linha",
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

            archive = read_slja(archive_path)

        self.assertEqual(archive.title, "Titulo")
        self.assertEqual(archive.audio_member, "audio\\song.mp3")
        self.assertEqual(
            archive.slides,
            (
                Slide(lines=("Primeira linha", "Segunda linha"), start_seconds=3.0),
                Slide(lines=(), start_seconds=5.0),
            ),
        )


if __name__ == "__main__":
    unittest.main()
