from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import audio_to_slja
from louvorja_slides.transcription import Transcript, TranscribedWord


class AudioToSljaLocalFlowTest(unittest.TestCase):
    def test_audio_to_slja_uses_local_transcript_and_embeds_audio(self) -> None:
        transcript = Transcript(
            words=[
                TranscribedWord("Fala", 7.0, 7.4),
                TranscribedWord("comigo", 7.5, 8.0),
            ],
            detected_language="pt",
            duration_seconds=30.0,
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            output_path = tmp_path / "song.slja"
            audio_path.write_bytes(b"audio bytes")

            with patch("audio_to_slja.transcribe_audio_local", return_value=transcript):
                exit_code = audio_to_slja.main(
                    [str(audio_path), "--output", str(output_path), "--title", "Fala comigo"]
                )

            self.assertEqual(exit_code, 0)
            with zipfile.ZipFile(output_path) as archive:
                self.assertIn("audio\\song.mp3", archive.namelist())
                text = archive.read("slides.lja").decode("cp1252")

        self.assertIn("letra=Fala comigo", text)
        self.assertIn("tempo=00:00:07", text)


if __name__ == "__main__":
    unittest.main()
