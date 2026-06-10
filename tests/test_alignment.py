from __future__ import annotations

import unittest

import numpy as np

from louvorja_slides.alignment import AlignmentError, MmsForcedAligner, refine_words_from_spans, sanitize_for_mms
from louvorja_slides.transcription import Transcript, TranscribedWord


class AlignmentTest(unittest.TestCase):
    def test_sanitize_for_mms_removes_diacritics_punctuation_and_spaces(self) -> None:
        self.assertEqual(sanitize_for_mms("Coracao,"), "coracao")
        self.assertEqual(sanitize_for_mms("Nao temas!"), "naotemas")

    def test_refine_words_from_spans_updates_word_boundaries(self) -> None:
        words = [
            TranscribedWord("Fala", 10.0, 11.0, source="whisper"),
            TranscribedWord("comigo", 11.0, 12.0, source="whisper"),
        ]
        spans = [
            {"word_idx": 0, "start_frame": 50, "end_frame": 70},
            {"word_idx": 1, "start_frame": 80, "end_frame": 110},
        ]

        refined = refine_words_from_spans(words, spans, frame_seconds=0.02)

        self.assertEqual(refined[0].start, 1.0)
        self.assertEqual(refined[0].end, 1.42)
        self.assertEqual(refined[0].source, "mms_align")
        self.assertEqual(refined[1].start, 1.6)
        self.assertEqual(refined[1].end, 2.22)


class MmsForcedAlignerTest(unittest.TestCase):
    def test_forced_aligner_raises_when_alignable_words_have_no_spans(self) -> None:
        transcript = Transcript(
            words=[TranscribedWord("Fala", 1.0, 2.0, source="whisper")],
            detected_language="pt",
            duration_seconds=3.0,
        )
        aligner = MmsForcedAligner(run_forced_align=lambda samples, words, language: [])

        with self.assertRaisesRegex(AlignmentError, "no alignment spans"):
            aligner.align_transcript(
                transcript,
                samples=np.zeros(16000, dtype=np.float32),
                language="pt",
            )

    def test_forced_aligner_refines_words_when_spans_exist(self) -> None:
        transcript = Transcript(
            words=[TranscribedWord("Fala", 1.0, 2.0, source="whisper")],
            detected_language="pt",
            duration_seconds=3.0,
        )
        aligner = MmsForcedAligner(
            run_forced_align=lambda samples, words, language: [
                {"word_idx": 0, "start_frame": 60, "end_frame": 80}
            ]
        )

        refined = aligner.align_transcript(
            transcript,
            samples=np.zeros(16000, dtype=np.float32),
            language="pt",
        )

        self.assertEqual(refined.words[0].source, "mms_align")


if __name__ == "__main__":
    unittest.main()
