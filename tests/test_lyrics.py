from __future__ import annotations

import unittest

from louvorja_slides.lyrics import (
    align_lyrics_to_transcript,
    parse_lyrics,
    transcript_to_lyrics_document,
)
from louvorja_slides.quality import QualityViolation, enforce_quality
from louvorja_slides.slja import Slide, extract_lyric_slides
from louvorja_slides.transcription import Transcript, TranscribedWord


def _transcript(*words: tuple[str, float, float]) -> Transcript:
    return Transcript(
        words=[
            TranscribedWord(text=text, start=start, end=end, source="asr")
            for text, start, end in words
        ],
        detected_language="pt",
        duration_seconds=max(end for _text, _start, end in words) + 1.0,
    )


class LyricsParsingTest(unittest.TestCase):
    def test_parse_lyrics_preserves_display_text_and_normalizes_for_matching(self) -> None:
        lyrics = parse_lyrics("És tudo!\nNão há outro\n\nCalebe")

        self.assertEqual(
            [token.text for token in lyrics.tokens],
            ["És", "tudo!", "Não", "há", "outro", "Calebe"],
        )
        self.assertEqual(
            [token.normalized for token in lyrics.tokens],
            ["es", "tudo", "nao", "ha", "outro", "calebe"],
        )
        self.assertEqual(lyrics.lines[2].section_index, 1)


class LyricsAlignmentTest(unittest.TestCase):
    def test_exact_match_preserves_expected_casing_accents_and_punctuation(self) -> None:
        source = _transcript(("es", 1.0, 1.2), ("tudo", 1.4, 1.8))

        result = align_lyrics_to_transcript(source, parse_lyrics("És tudo!"))

        self.assertEqual([word.text for word in result.transcript.words], ["És", "tudo!"])
        self.assertEqual(result.report.coverage, 1.0)
        self.assertEqual(result.transcript.words[0].start, 1.0)
        self.assertEqual(result.transcript.words[1].end, 1.8)

    def test_fuzzy_asr_word_maps_to_expected_display_word(self) -> None:
        source = _transcript(("Eu", 1.0, 1.2), ("sou", 1.3, 1.5), ("Caleb", 1.6, 2.0))

        result = align_lyrics_to_transcript(source, parse_lyrics("Eu sou Calebe"))

        self.assertEqual([word.text for word in result.transcript.words], ["Eu", "sou", "Calebe"])
        self.assertEqual(result.report.coverage, 1.0)
        self.assertEqual(result.transcript.words[-1].source, "lyrics_anchor")

    def test_asr_fillers_and_bracket_words_are_skipped(self) -> None:
        source = _transcript(
            ("[Music]", 0.0, 0.5),
            ("oh", 0.6, 0.8),
            ("Fala", 1.0, 1.2),
            ("comigo", 1.3, 1.7),
        )

        result = align_lyrics_to_transcript(source, parse_lyrics("Fala comigo"))

        self.assertEqual([word.text for word in result.transcript.words], ["Fala", "comigo"])
        self.assertEqual(result.report.skipped_asr_word_count, 2)
        self.assertEqual(result.report.coverage, 1.0)

    def test_missing_asr_words_receive_interpolated_monotonic_timings(self) -> None:
        source = _transcript(("Fala", 1.0, 1.2), ("Senhor", 2.0, 2.4))

        result = align_lyrics_to_transcript(source, parse_lyrics("Fala comigo Senhor"))

        words = result.transcript.words
        self.assertEqual([word.text for word in words], ["Fala", "comigo", "Senhor"])
        self.assertEqual(words[1].source, "lyrics_interpolated")
        self.assertGreaterEqual(words[1].start, words[0].end)
        self.assertLessEqual(words[1].end, words[2].start)
        self.assertGreater(words[1].end, words[1].start)

    def test_repeated_lyrics_map_to_later_audio_occurrences_monotonically(self) -> None:
        source = _transcript(
            ("Fala", 1.0, 1.2),
            ("comigo", 1.3, 1.7),
            ("Fala", 8.0, 8.2),
            ("comigo", 8.3, 8.7),
        )

        result = align_lyrics_to_transcript(source, parse_lyrics("Fala comigo\nFala comigo"))

        self.assertEqual(
            [word.start for word in result.transcript.words],
            [1.0, 1.3, 8.0, 8.3],
        )
        self.assertEqual(result.report.coverage, 1.0)

    def test_transcript_to_lyrics_document_preserves_line_hints_for_slide_extraction(self) -> None:
        lyrics = parse_lyrics("Fala comigo\nFala comigo")
        result = align_lyrics_to_transcript(
            _transcript(
                ("Fala", 1.0, 1.2),
                ("comigo", 1.3, 1.7),
                ("Fala", 8.0, 8.2),
                ("comigo", 8.3, 8.7),
            ),
            lyrics,
        )

        doc = transcript_to_lyrics_document(result.transcript, lyrics, title="Teste")
        slides = extract_lyric_slides(doc)

        self.assertEqual(doc.metadata.title, "Teste")
        self.assertEqual(
            slides[0],
            Slide(lines=("Fala comigo",), start_seconds=1.0, aux_text="(2x)"),
        )

    def test_low_alignment_coverage_fails_quality_gate(self) -> None:
        result = align_lyrics_to_transcript(
            _transcript(("Nada", 1.0, 1.2), ("parecido", 1.3, 1.6)),
            parse_lyrics("Fala comigo Senhor"),
        )

        with self.assertRaisesRegex(QualityViolation, "lyrics alignment coverage"):
            enforce_quality(
                slides=[Slide(lines=("Fala comigo",), start_seconds=1.0)],
                transcript=result.transcript,
                lyrics_alignment=result.report,
                mode="fail",
            )


if __name__ == "__main__":
    unittest.main()
