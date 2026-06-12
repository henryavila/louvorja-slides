from __future__ import annotations

import unittest

from louvorja_slides.quality import (
    QualityThresholds,
    QualityViolation,
    analyze_slide_quality,
    analyze_transcript_quality,
    enforce_quality,
)
from louvorja_slides.slja import Slide
from louvorja_slides.transcription import Transcript, TranscribedWord


class QualityAnalysisTest(unittest.TestCase):
    def test_slide_quality_flags_excessive_auxiliary_lyrics(self) -> None:
        slides = [
            Slide(
                lines=("Uma frase principal", "Outra frase principal"),
                start_seconds=10.0,
                aux_text="trecho extra que deveria virar outro slide",
            ),
            Slide(lines=("Fim",), start_seconds=20.0),
        ]

        report = analyze_slide_quality(slides, QualityThresholds(max_aux_word_ratio=0.10))

        self.assertFalse(report.acceptable)
        self.assertIn("auxiliary lyric word ratio", report.messages[0])

    def test_repetition_markers_do_not_count_as_auxiliary_lyrics(self) -> None:
        slides = [
            Slide(lines=("Santo",), start_seconds=1.0, aux_text="(3x)"),
            Slide(lines=("Digno",), start_seconds=8.0, aux_text="(2x)"),
        ]

        report = analyze_slide_quality(slides)

        self.assertTrue(report.acceptable)
        self.assertEqual(report.auxiliary_word_count, 0)

    def test_slide_quality_flags_long_main_lines(self) -> None:
        slides = [
            Slide(lines=("Esta linha principal ficou longa demais",), start_seconds=1.0),
            Slide(lines=("curta",), start_seconds=8.0),
        ]

        report = analyze_slide_quality(slides, QualityThresholds(max_line_over_target_ratio=0.10))

        self.assertFalse(report.acceptable)
        self.assertIn("main line over target ratio", "\n".join(report.messages))

    def test_transcript_quality_flags_sparse_word_timestamps(self) -> None:
        words = [
            TranscribedWord(text=f"w{index}", start=1.0, end=1.0)
            for index in range(20)
        ]
        transcript = Transcript(words=words, detected_language="pt", duration_seconds=30.0)

        report = analyze_transcript_quality(
            transcript,
            QualityThresholds(max_zero_duration_word_ratio=0.05, min_positive_gap_ratio=0.75),
        )

        self.assertFalse(report.acceptable)
        self.assertIn("zero-duration word ratio", "\n".join(report.messages))
        self.assertIn("positive timestamp gap ratio", "\n".join(report.messages))

    def test_aligned_transcript_with_positive_gaps_passes_timestamp_quality(self) -> None:
        transcript = Transcript(
            words=[
                TranscribedWord("Fala", 1.00, 1.20, source="mms_align"),
                TranscribedWord("comigo", 1.32, 1.70, source="mms_align"),
                TranscribedWord("Senhor", 2.10, 2.50, source="mms_align"),
            ],
            detected_language="pt",
            duration_seconds=3.0,
        )

        report = analyze_transcript_quality(transcript)

        self.assertTrue(report.acceptable, report.messages)

    def test_zero_lyric_slides_fail_the_quality_gate(self) -> None:
        report = analyze_slide_quality([])

        self.assertFalse(report.acceptable)
        self.assertIn("no lyric slides", "\n".join(report.messages))

        with self.assertRaisesRegex(QualityViolation, "no lyric slides"):
            enforce_quality(slides=[], mode="fail")

    def test_positive_gap_threshold_is_configurable(self) -> None:
        transcript = Transcript(
            words=[
                TranscribedWord("Fala", 1.00, 1.20),
                TranscribedWord("comigo", 1.24, 1.40),
                TranscribedWord("Senhor", 1.44, 1.60),
            ],
            detected_language="pt",
            duration_seconds=3.0,
        )

        strict = analyze_transcript_quality(
            transcript,
            QualityThresholds(min_positive_gap_ratio=0.5, min_gap_seconds=0.05),
        )
        lenient = analyze_transcript_quality(
            transcript,
            QualityThresholds(min_positive_gap_ratio=0.5, min_gap_seconds=0.03),
        )

        self.assertFalse(strict.acceptable)
        self.assertEqual(strict.positive_gap_count, 0)
        self.assertTrue(lenient.acceptable, lenient.messages)
        self.assertEqual(lenient.positive_gap_count, 2)

    def test_enforce_quality_raises_with_combined_context(self) -> None:
        slides = [
            Slide(
                lines=("Linha principal muito longa para cantar lendo",),
                start_seconds=1.0,
                aux_text="trecho extra",
            )
        ]

        with self.assertRaises(QualityViolation) as caught:
            enforce_quality(slides=slides, mode="fail")

        self.assertIn("quality gate failed", str(caught.exception))
        self.assertIn("Run again with --quality-gate warn", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
