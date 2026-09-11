from __future__ import annotations

import unittest

from louvorja_slides.document import transcript_to_document
from louvorja_slides.slja import extract_lyric_slides
from louvorja_slides.transcription import Transcript, TranscribedWord


class DocumentTest(unittest.TestCase):
    def test_transcript_to_document_is_compatible_with_slja_extractor(self) -> None:
        transcript = Transcript(
            words=[
                TranscribedWord("Fala", 1.0, 1.3),
                TranscribedWord("comigo", 1.4, 1.9),
                TranscribedWord("Santo", 5.0, 5.5),
            ],
            detected_language="pt",
            duration_seconds=10.0,
        )

        doc = transcript_to_document(transcript, title="Minha musica")
        slides = extract_lyric_slides(doc)

        self.assertEqual(doc.metadata.title, "Minha musica")
        self.assertEqual(slides[0].start_seconds, 1.0)
        self.assertIn("Fala", slides[0].lines[0])

    def test_one_word_transcript_does_not_crash_gap_grouping(self) -> None:
        transcript = Transcript(
            words=[TranscribedWord("Santo", 1.0, 1.5)],
            detected_language="pt",
            duration_seconds=3.0,
        )

        doc = transcript_to_document(transcript, title="Santo")

        self.assertEqual(doc.sections[0].lines[0].text, "Santo")

    def test_transcript_to_document_filters_non_lyric_music_tokens(self) -> None:
        transcript = Transcript(
            words=[
                TranscribedWord("♪", 0.0, 10.0),
                TranscribedWord("Fala", 10.0, 10.5),
                TranscribedWord("?", 10.5, 11.0),
                TranscribedWord("comigo", 11.0, 11.5),
            ],
            detected_language="pt",
            duration_seconds=12.0,
        )

        doc = transcript_to_document(transcript)

        self.assertEqual(doc.sections[0].lines[0].text, "Fala comigo")

    def test_transcript_to_document_breaks_likely_musical_phrases(self) -> None:
        transcript = Transcript(
            words=[
                TranscribedWord("Andei", 1.0, 1.5),
                TranscribedWord("tão", 1.5, 2.0),
                TranscribedWord("cego,", 2.0, 2.5),
                TranscribedWord("sem", 2.5, 3.0),
                TranscribedWord("rumo", 3.0, 3.5),
                TranscribedWord("certo", 3.5, 4.0),
                TranscribedWord("Buscando", 4.0, 4.5),
                TranscribedWord("a", 4.5, 5.0),
                TranscribedWord("paz", 5.0, 5.5),
            ],
            detected_language="pt",
            duration_seconds=6.0,
        )

        doc = transcript_to_document(transcript)

        self.assertEqual(
            [line.text for line in doc.sections[0].lines],
            ["Andei tão cego, sem rumo certo", "Buscando a paz"],
        )


if __name__ == "__main__":
    unittest.main()
