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

        # A 34 s chunk (544,000 samples) through the wav2vec2 conv stack
        # (kernels 10,3,3,3,3,2,2 / strides 5,2,2,2,2,2,2) emits 1699 frames,
        # not the idealized 544000/320 = 1700. The stitcher must still keep
        # exactly window_samples/320 = 1500 frames per chunk on the global
        # 20 ms grid, or timestamps drift one frame per chunk.
        def fake_forward(batch):
            return torch.zeros(batch.shape[0], 1699, 32), None

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

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch not installed")
    def test_generate_emissions_keeps_exact_inner_window_frames(self) -> None:
        import torch

        # Encode each frame's index into its emission value so a wrong crop
        # offset ([0:1500], [99:1599], [199:1699], ...) changes the values,
        # not just the shape.
        def fake_forward(batch):
            frames = torch.arange(1699, dtype=torch.float32).view(1, 1699, 1)
            return frames.expand(batch.shape[0], 1699, 32).clone(), None

        fake_model = MagicMock(side_effect=fake_forward)
        aligner = MmsForcedAligner(model=fake_model, tokenizer=object(), blank_id=0)

        result = aligner.generate_emissions(
            torch.zeros(90 * 16000),
            window_seconds=30.0,
            context_seconds=2.0,
            batch_size=1,
        )

        # 2 s of context = 100 frames; the inner 30 s window keeps frames
        # 100..1599 of every chunk.
        self.assertEqual(float(result[0, 0, 0]), 100.0)
        self.assertEqual(float(result[0, 1499, 0]), 1599.0)
        self.assertEqual(float(result[0, 1500, 0]), 100.0)
        self.assertEqual(float(result[0, 4499, 0]), 1599.0)

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch not installed")
    def test_generate_emissions_raises_when_chunk_frames_are_insufficient(self) -> None:
        import torch

        def fake_forward(batch):
            return torch.zeros(batch.shape[0], 1599, 32), None

        fake_model = MagicMock(side_effect=fake_forward)
        aligner = MmsForcedAligner(model=fake_model, tokenizer=object(), blank_id=0)

        with self.assertRaisesRegex(AlignmentError, "frames"):
            aligner.generate_emissions(
                torch.zeros(90 * 16000),
                window_seconds=30.0,
                context_seconds=2.0,
                batch_size=1,
            )

    def test_refine_words_keeps_unalignable_words_in_monotonic_order(self) -> None:
        words = [
            TranscribedWord("vinte", 10.0, 10.4, source="whisper"),
            TranscribedWord("24", 10.4, 10.8, source="whisper"),
            TranscribedWord("horas", 10.8, 11.2, source="whisper"),
        ]
        spans = [
            {"word_idx": 0, "start_frame": 50, "end_frame": 70},
            {"word_idx": 2, "start_frame": 80, "end_frame": 110},
        ]

        refined = refine_words_from_spans(words, spans, frame_seconds=0.02)

        self.assertEqual([word.text for word in refined], ["vinte", "24", "horas"])
        starts = [word.start for word in refined]
        self.assertEqual(starts, sorted(starts))
        self.assertGreaterEqual(refined[1].start, refined[0].start)
        self.assertLessEqual(refined[1].start, refined[2].start)
        self.assertLessEqual(refined[1].end, refined[2].start)
        self.assertEqual(refined[1].source, "whisper")

    def test_refine_words_clamps_consecutive_unalignable_words(self) -> None:
        words = [
            TranscribedWord("vinte", 10.0, 10.4, source="whisper"),
            TranscribedWord("24", 10.4, 10.6, source="whisper"),
            TranscribedWord("48", 10.6, 10.8, source="whisper"),
            TranscribedWord("horas", 10.8, 11.2, source="whisper"),
        ]
        spans = [
            {"word_idx": 0, "start_frame": 50, "end_frame": 70},
            {"word_idx": 3, "start_frame": 80, "end_frame": 110},
        ]

        refined = refine_words_from_spans(words, spans, frame_seconds=0.02)

        self.assertEqual(
            [word.text for word in refined],
            ["vinte", "24", "48", "horas"],
        )
        keys = [(word.start, word.end) for word in refined]
        self.assertEqual(keys, sorted(keys))
        for word in refined:
            self.assertLessEqual(word.start, word.end)

    def test_refine_words_rejects_non_monotonic_aligned_spans(self) -> None:
        words = [
            TranscribedWord("Fala", 1.0, 1.4, source="whisper"),
            TranscribedWord("comigo", 1.4, 1.8, source="whisper"),
        ]
        spans = [
            {"word_idx": 0, "start_frame": 100, "end_frame": 120},
            {"word_idx": 1, "start_frame": 10, "end_frame": 20},
        ]

        with self.assertRaisesRegex(AlignmentError, "monotonic"):
            refine_words_from_spans(words, spans, frame_seconds=0.02)

    def test_refine_transcript_keeps_word_order_and_phoneme_parents(self) -> None:
        transcript = Transcript(
            words=[
                TranscribedWord("vinte", 10.0, 10.4, source="whisper"),
                TranscribedWord("24", 10.4, 10.8, source="whisper"),
                TranscribedWord("horas", 10.8, 11.2, source="whisper"),
            ],
            detected_language="pt",
            duration_seconds=20.0,
        )
        spans = [
            {"text": "v", "word_idx": 0, "start_frame": 50, "end_frame": 70},
            {"text": "o", "word_idx": 2, "start_frame": 80, "end_frame": 110},
        ]

        refined = refine_transcript_from_spans(transcript, spans, frame_seconds=0.02)

        self.assertEqual(
            [word.text for word in refined.words],
            ["vinte", "24", "horas"],
        )
        phoneme = (refined.phonemes or [])[1]
        self.assertEqual(phoneme.symbol, "o")
        self.assertEqual(refined.words[phoneme.parent_word_idx].text, "horas")

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

    def test_attach_spans_to_words_raises_on_span_count_mismatch(self) -> None:
        spans = [{"_tok": 10, "start_frame": 1, "end_frame": 2}]

        with self.assertRaisesRegex(AlignmentError, "span"):
            attach_spans_to_words(spans, [[10], [20]], tokenizer=object(), labels=["a"])

    def test_attach_spans_to_words_raises_on_token_identity_mismatch(self) -> None:
        spans = [{"_tok": 99, "start_frame": 1, "end_frame": 2}]

        with self.assertRaisesRegex(AlignmentError, "token"):
            attach_spans_to_words(spans, [[10]], tokenizer=object(), labels=["a"])

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch not installed")
    def test_constructor_derives_device_from_injected_model(self) -> None:
        import torch

        model = torch.nn.Linear(1, 1).to("meta")

        aligner = MmsForcedAligner(model=model, tokenizer=object(), blank_id=0)

        self.assertEqual(aligner._device, "meta")

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch not installed")
    def test_load_bundle_honors_explicit_device(self) -> None:
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch

        model = MagicMock()
        model.to.return_value = model
        model.train.return_value = model
        fake_bundle = SimpleNamespace(
            get_model=lambda: model,
            get_tokenizer=lambda: object(),
            get_labels=lambda: ["-"],
        )
        fake_module = SimpleNamespace(MMS_FA=fake_bundle)

        aligner = MmsForcedAligner(device="cpu")
        with (
            patch.dict(sys.modules, {"torchaudio.pipelines": fake_module}),
            patch("torch.cuda.is_available", return_value=True),
        ):
            aligner._load_bundle()

        self.assertEqual(aligner._device, "cpu")
        model.to.assert_called_once_with("cpu")


if __name__ == "__main__":
    unittest.main()
