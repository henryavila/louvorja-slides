from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from louvorja_slides.transcription import (
    LocalWhisperTranscriber,
    Transcript,
    TranscribedPhoneme,
    TranscribedWord,
)


class TranscriptionModelsTest(unittest.TestCase):
    def test_transcript_rejects_empty_word_list(self) -> None:
        with self.assertRaisesRegex(ValueError, "no transcribed words"):
            Transcript(words=[], detected_language="pt", duration_seconds=10.0)

    def test_transcript_rejects_inverted_word_timestamp(self) -> None:
        with self.assertRaisesRegex(ValueError, "end"):
            TranscribedWord(text="Fala", start=2.0, end=1.0)

    def test_transcript_sorts_words_by_start_time(self) -> None:
        transcript = Transcript(
            words=[
                TranscribedWord(text="comigo", start=2.0, end=2.4),
                TranscribedWord(text="Fala", start=1.0, end=1.4),
            ],
            detected_language="pt",
            duration_seconds=3.0,
        )

        self.assertEqual([word.text for word in transcript.words], ["Fala", "comigo"])

    def test_transcript_json_roundtrip(self) -> None:
        transcript = Transcript(
            words=[TranscribedWord(text="Fala", start=1.0, end=1.4, source="whisper")],
            detected_language="pt",
            duration_seconds=3.0,
        )

        self.assertEqual(Transcript.from_dict(transcript.to_dict()), transcript)

    def test_transcript_preserves_optional_phonemes_in_json(self) -> None:
        transcript = Transcript(
            words=[TranscribedWord(text="Fala", start=1.0, end=1.4, source="whisper")],
            detected_language="pt",
            duration_seconds=3.0,
            phonemes=[
                TranscribedPhoneme(
                    symbol="f",
                    start=1.0,
                    end=1.1,
                    parent_word_idx=0,
                    source="mms_align",
                )
            ],
        )

        self.assertEqual(Transcript.from_dict(transcript.to_dict()), transcript)


class LocalWhisperTest(unittest.TestCase):
    def test_transcriber_uses_quality_whisper_arguments(self) -> None:
        calls: list[dict[str, object]] = []

        class FakeModel:
            def transcribe(
                self, samples: np.ndarray, **kwargs: object
            ) -> list[SimpleNamespace]:
                calls.append(kwargs)
                return [SimpleNamespace(t0=100, t1=160, text="Fala")]

        transcriber = LocalWhisperTranscriber(model=FakeModel(), model_id="large-v3")

        transcript = transcriber.transcribe_samples(
            samples=np.zeros(16000, dtype=np.float32),
            sample_rate=16000,
            duration_seconds=1.0,
            language="pt",
        )

        self.assertEqual(transcript.words[0].text, "Fala")
        self.assertEqual(transcript.words[0].start, 1.0)
        self.assertEqual(transcript.words[0].end, 1.6)
        self.assertEqual(calls[0]["token_timestamps"], True)
        self.assertEqual(calls[0]["max_len"], 1)
        self.assertEqual(calls[0]["split_on_word"], True)
        self.assertEqual(calls[0]["entropy_thold"], 2.2)
        self.assertEqual(calls[0]["no_speech_thold"], 0.7)
        self.assertEqual(calls[0]["language"], "pt")

    def test_transcriber_reports_model_detected_language_when_not_requested(self) -> None:
        detect_calls: list[int] = []

        class FakeModel:
            def transcribe(
                self, samples: np.ndarray, **kwargs: object
            ) -> list[SimpleNamespace]:
                return [SimpleNamespace(t0=100, t1=160, text="Holy")]

            def auto_detect_language(
                self, samples: np.ndarray
            ) -> tuple[tuple[str, float], dict[str, float]]:
                detect_calls.append(1)
                return ("en", 0.93), {"en": 0.93, "pt": 0.05}

        transcriber = LocalWhisperTranscriber(model=FakeModel(), model_id="large-v3")

        transcript = transcriber.transcribe_samples(
            samples=np.zeros(16000, dtype=np.float32),
            sample_rate=16000,
            duration_seconds=1.0,
            language=None,
        )

        self.assertEqual(transcript.detected_language, "en")
        self.assertEqual(detect_calls, [1])

    def test_transcriber_skips_language_detection_when_language_is_requested(self) -> None:
        detect_calls: list[int] = []

        class FakeModel:
            def transcribe(
                self, samples: np.ndarray, **kwargs: object
            ) -> list[SimpleNamespace]:
                return [SimpleNamespace(t0=100, t1=160, text="Fala")]

            def auto_detect_language(
                self, samples: np.ndarray
            ) -> tuple[tuple[str, float], dict[str, float]]:
                detect_calls.append(1)
                return ("en", 0.93), {"en": 0.93}

        transcriber = LocalWhisperTranscriber(model=FakeModel(), model_id="large-v3")

        transcript = transcriber.transcribe_samples(
            samples=np.zeros(16000, dtype=np.float32),
            sample_rate=16000,
            duration_seconds=1.0,
            language="pt",
        )

        self.assertEqual(transcript.detected_language, "pt")
        self.assertEqual(detect_calls, [])

    def test_transcriber_filters_bracketed_non_lyric_tokens(self) -> None:
        class FakeModel:
            def transcribe(
                self, samples: np.ndarray, **kwargs: object
            ) -> list[SimpleNamespace]:
                return [
                    SimpleNamespace(t0=0, t1=100, text="[Música]"),
                    SimpleNamespace(t0=100, t1=200, text="Santo"),
                    SimpleNamespace(t0=200, t1=300, text="[BLANK_AUDIO]"),
                ]

        transcriber = LocalWhisperTranscriber(model=FakeModel(), model_id="large-v3")

        transcript = transcriber.transcribe_samples(
            samples=np.zeros(16000, dtype=np.float32),
            sample_rate=16000,
            duration_seconds=3.0,
            language="pt",
        )

        self.assertEqual([word.text for word in transcript.words], ["Santo"])

    def test_transcriber_filters_punctuation_only_music_tokens(self) -> None:
        class FakeModel:
            def transcribe(
                self, samples: np.ndarray, **kwargs: object
            ) -> list[SimpleNamespace]:
                return [
                    SimpleNamespace(t0=0, t1=100, text="♪"),
                    SimpleNamespace(t0=100, t1=200, text="Fala"),
                    SimpleNamespace(t0=200, t1=300, text="?"),
                ]

        transcriber = LocalWhisperTranscriber(model=FakeModel(), model_id="large-v3")

        transcript = transcriber.transcribe_samples(
            samples=np.zeros(16000, dtype=np.float32),
            sample_rate=16000,
            duration_seconds=3.0,
            language="pt",
        )

        self.assertEqual([word.text for word in transcript.words], ["Fala"])


if __name__ == "__main__":
    unittest.main()
