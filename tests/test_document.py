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


if __name__ == "__main__":
    unittest.main()
