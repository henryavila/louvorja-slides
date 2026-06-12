from __future__ import annotations

import importlib.util
import unittest
from unittest.mock import MagicMock

import numpy as np

from louvorja_slides.alignment import (
    AlignmentError,
    MmsForcedAligner,
    attach_spans_to_words,
    build_mms_targets,
    collapse_alignment_path,
    refine_transcript_from_spans,
    refine_words_from_spans,
    sanitize_for_mms,
)
from louvorja_slides.transcription import Transcript, TranscribedWord


class AlignmentTest(unittest.TestCase):
    def test_sanitize_for_mms_removes_diacritics_punctuation_and_spaces(self) -> None:
        self.assertEqual(sanitize_for_mms("Coração,"), "coracao")
        self.assertEqual(sanitize_for_mms("Não temas!"), "naotemas")

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

    def test_refine_transcript_from_spans_returns_phonemes(self) -> None:
        transcript = Transcript(
            words=[TranscribedWord("Fala", 10.0, 11.0, source="whisper")],
            detected_language="pt",
            duration_seconds=20.0,
        )
        spans = [
            {"text": "f", "word_idx": 0, "start_frame": 50, "end_frame": 54},
            {"text": "a", "word_idx": 0, "start_frame": 55, "end_frame": 70},
        ]

        refined = refine_transcript_from_spans(transcript, spans, frame_seconds=0.02)

        self.assertEqual(refined.words[0].start, 1.0)
        self.assertEqual(refined.words[0].end, 1.42)
        self.assertEqual(refined.words[0].source, "mms_align")
        self.assertEqual(len(refined.phonemes or []), 2)
        self.assertEqual((refined.phonemes or [])[0].symbol, "f")
        self.assertEqual((refined.phonemes or [])[0].parent_word_idx, 0)

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
                {"text": "f", "word_idx": 0, "start_frame": 60, "end_frame": 80}
            ]
        )

        refined = aligner.align_transcript(
            transcript,
            samples=np.zeros(16000, dtype=np.float32),
            language="pt",
        )

        self.assertEqual(refined.words[0].source, "mms_align")

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch not installed")
    def test_generate_emissions_short_audio_uses_single_forward(self) -> None:
        import torch

        fake_emissions = torch.zeros(1, 500, 32)
        fake_model = MagicMock(return_value=(fake_emissions, None))
        aligner = MmsForcedAligner(model=fake_model, tokenizer=object(), blank_id=0)

        result = aligner.generate_emissions(torch.zeros(10 * 16000))

        self.assertEqual(fake_model.call_count, 1)
        self.assertEqual(tuple(result.shape), (1, 500, 32))

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch not installed")
    def test_generate_emissions_long_audio_chunks_and_stitches(self) -> None:
        import torch

        def fake_forward(batch):
            return torch.zeros(batch.shape[0], 1700, 32), None

        fake_model = MagicMock(side_effect=fake_forward)
        aligner = MmsForcedAligner(model=fake_model, tokenizer=object(), blank_id=0)

        result = aligner.generate_emissions(
            torch.zeros(90 * 16000),
            window_seconds=30.0,
            context_seconds=2.0,
            batch_size=1,
        )

        self.assertEqual(fake_model.call_count, 3)
        self.assertEqual(tuple(result.shape), (1, 4500, 32))

    def test_build_mms_targets_preserves_original_word_indices(self) -> None:
        class FakeTokenizer:
            def __init__(self) -> None:
                self.calls: list[list[str]] = []

            def __call__(self, words: list[str]) -> list[list[int]]:
                self.calls.append(words)
                return [[{"nao": 10, "musica": 12, "temas": 20}[words[0]]]]

        tokenizer = FakeTokenizer()
        words = [
            TranscribedWord("Não", 0.0, 0.1),
            TranscribedWord("[Música]", 0.2, 0.3),
            TranscribedWord("temas", 0.4, 0.5),
        ]

        tokens_per_word, target_tokens = build_mms_targets(words, tokenizer)

        self.assertEqual(tokenizer.calls, [["nao"], ["musica"], ["temas"]])
        self.assertEqual(tokens_per_word, [[10], [12], [20]])
        self.assertEqual(target_tokens, [10, 12, 20])

    def test_build_mms_targets_skips_only_rejected_words(self) -> None:
        class PartiallyRejectingTokenizer:
            def __call__(self, words: list[str]) -> list[list[int]]:
                if words == ["ruim"]:
                    raise KeyError(words[0])
                return [[{"fala": 10, "senhor": 20}[words[0]]]]

        tokens_per_word, target_tokens = build_mms_targets(
            [
                TranscribedWord("Fala", 0.0, 0.5),
                TranscribedWord("ruim", 0.5, 1.0),
                TranscribedWord("Senhor", 1.0, 1.5),
            ],
            PartiallyRejectingTokenizer(),
        )

        self.assertEqual(tokens_per_word, [[10], [], [20]])
        self.assertEqual(target_tokens, [10, 20])

    def test_build_mms_targets_reports_when_all_words_are_rejected(self) -> None:
        class RejectingTokenizer:
            def __call__(self, words: list[str]) -> list[list[int]]:
                raise KeyError(words[0])

        with self.assertRaisesRegex(AlignmentError, "rejected all sanitized words"):
            build_mms_targets([TranscribedWord("Fala", 0.0, 0.5)], RejectingTokenizer())

    def test_collapse_alignment_path_skips_blanks_and_groups_runs(self) -> None:
        spans = collapse_alignment_path([0, 1, 1, 0, 2, 2, 2], blank_id=0)

        self.assertEqual(
            spans,
            [
                {"_tok": 1, "start_frame": 1, "end_frame": 2},
                {"_tok": 2, "start_frame": 4, "end_frame": 6},
            ],
        )

    def test_attach_spans_to_words_preserves_empty_word_offsets(self) -> None:
        class FakeTokenizer:
            def decode(self, tokens: list[int]) -> str:
                return {10: "f", 20: "t"}[tokens[0]]

        spans = [
            {"_tok": 10, "start_frame": 1, "end_frame": 2},
            {"_tok": 20, "start_frame": 7, "end_frame": 8},
        ]

        attached = attach_spans_to_words(spans, [[10], [], [20]], FakeTokenizer())

        self.assertEqual([span["word_idx"] for span in attached], [0, 2])
        self.assertEqual([span["text"] for span in attached], ["f", "t"])

    def test_attach_spans_to_words_uses_labels_without_decode_api(self) -> None:
        spans = [
            {"_tok": 24, "start_frame": 1, "end_frame": 2},
            {"_tok": 3, "start_frame": 7, "end_frame": 8},
        ]
        labels = [""] * 29
        labels[3] = "e"
        labels[24] = "f"

        attached = attach_spans_to_words(
            spans,
            [[24, 3]],
            tokenizer=object(),
            labels=labels,
        )

        self.assertEqual([span["text"] for span in attached], ["f", "e"])


if __name__ == "__main__":
    unittest.main()
