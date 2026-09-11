from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from louvorja_slides.consensus import (
    ConsensusCandidate,
    build_phase1_consensus,
    build_consensus_from_candidates,
    format_consensus_report,
    group_phrases,
    normalize_text,
    parse_vtt_words,
    segment_candidate_phrases,
)
from louvorja_slides.engines import AudioToDocumentConfig
from louvorja_slides.slja import Slide
from louvorja_slides.transcription import Transcript, TranscribedWord


def _candidate(
    name: str,
    words: list[tuple[str, float, float]],
    *,
    duration: float = 10.0,
) -> ConsensusCandidate:
    return ConsensusCandidate(
        name=name,
        transcript=Transcript(
            words=[
                TranscribedWord(text=text, start=start, end=end, source=name)
                for text, start, end in words
            ],
            detected_language="pt",
            duration_seconds=duration,
        ),
    )


def _timed_words(
    text: str,
    *,
    start: float = 1.0,
    step: float = 0.35,
) -> list[tuple[str, float, float]]:
    return [
        (token, start + index * step, start + index * step + step * 0.7)
        for index, token in enumerate(text.split())
    ]


class ConsensusTest(unittest.TestCase):
    def test_normalize_text_removes_accents_case_and_punctuation(self) -> None:
        self.assertEqual(
            normalize_text("Água, PÃO!  Cristo?"),
            "agua pao cristo",
        )

    def test_segments_candidate_by_musical_pause(self) -> None:
        candidate = _candidate(
            "medium-original",
            [
                ("alfa", 1.0, 1.2),
                ("beta", 1.3, 1.5),
                ("gama", 2.3, 2.5),
                ("delta", 2.6, 2.8),
            ],
        )

        phrases = segment_candidate_phrases(candidate)

        self.assertEqual([phrase.text for phrase in phrases], ["alfa beta", "gama delta"])

    def test_groups_phrases_by_time_and_normalized_similarity(self) -> None:
        left = segment_candidate_phrases(
            _candidate(
                "medium-original",
                [("alfa", 1.0, 1.2), ("beta", 1.3, 1.6)],
            )
        )[0]
        right = segment_candidate_phrases(
            _candidate(
                "medium-denoise",
                [("álfa", 1.1, 1.3), ("beta", 1.4, 1.7)],
            )
        )[0]
        later = segment_candidate_phrases(
            _candidate(
                "turbo-original",
                [("omega", 8.0, 8.2), ("final", 8.3, 8.5)],
            )
        )[0]

        groups = group_phrases([later, right, left])

        self.assertEqual(len(groups), 2)
        self.assertEqual({phrase.candidate_name for phrase in groups[0]}, {"medium-original", "medium-denoise"})

    def test_short_outlier_does_not_win_against_supported_phrase(self) -> None:
        result = build_consensus_from_candidates(
            [
                _candidate(
                    "medium-original",
                    [
                        ("alfa", 1.0, 1.2),
                        ("beta", 1.3, 1.5),
                        ("gama", 1.6, 1.8),
                        ("delta", 1.9, 2.1),
                    ],
                ),
                _candidate(
                    "medium-denoise",
                    [
                        ("álfa", 1.0, 1.2),
                        ("beta", 1.3, 1.5),
                        ("gama", 1.6, 1.8),
                        ("delta", 1.9, 2.1),
                    ],
                ),
                _candidate("turbo-original", [("alfa", 1.1, 1.4)]),
            ],
            title="Teste",
        )

        self.assertNotEqual(result.decisions[0].winner.candidate_name, "turbo-original")
        self.assertEqual(
            normalize_text(" ".join(word.text for word in result.transcript.words)),
            "alfa beta gama delta",
        )

    def test_falls_back_to_best_whole_candidate_when_phrase_stitching_is_risky(self) -> None:
        result = build_consensus_from_candidates(
            [
                _candidate(
                    "turbo-vocals",
                    _timed_words("vocal limpo canta frase certa agora"),
                ),
                _candidate(
                    "medium-original",
                    _timed_words("ruido confuso inventa outra letra agora"),
                ),
                _candidate(
                    "medium-denoise",
                    _timed_words("texto distante mistura palavras sem apoio"),
                ),
            ],
            title="Teste",
        )

        self.assertEqual(result.selection_mode, "whole-candidate")
        self.assertEqual(result.fallback_source, "turbo-vocals")
        self.assertIn("low-confidence", result.fallback_reason)
        self.assertEqual(
            normalize_text(" ".join(word.text for word in result.transcript.words)),
            "vocal limpo canta frase certa agora",
        )

    def test_whole_candidate_fallback_rejects_too_short_vocal_candidate(self) -> None:
        result = build_consensus_from_candidates(
            [
                _candidate("turbo-vocals", [("curto", 1.0, 1.2)]),
                _candidate(
                    "medium-original",
                    _timed_words("frase principal com texto suficiente para escolher"),
                ),
                _candidate(
                    "medium-denoise",
                    _timed_words("ruido ruido ruido ruido ruido ruido"),
                ),
            ],
            title="Teste",
        )

        self.assertEqual(result.selection_mode, "whole-candidate")
        self.assertEqual(result.fallback_source, "medium-original")
        self.assertGreater(len(result.transcript.words), 1)

    def test_report_truncates_phrase_snippets(self) -> None:
        result = build_consensus_from_candidates(
            [
                _candidate(
                    "medium-original",
                    [
                        ("um", 1.0, 1.1),
                        ("dois", 1.2, 1.3),
                        ("tres", 1.4, 1.5),
                        ("quatro", 1.6, 1.7),
                        ("cinco", 1.8, 1.9),
                        ("seis", 2.0, 2.1),
                        ("sete", 2.2, 2.3),
                        ("oito", 2.4, 2.5),
                    ],
                )
            ],
            title="Teste",
        )

        report = format_consensus_report(result)

        self.assertIn("um dois tres quatro cinco seis ...", report)

    def test_report_explains_whole_candidate_fallback(self) -> None:
        result = build_consensus_from_candidates(
            [
                _candidate(
                    "turbo-vocals",
                    _timed_words("vocal limpo canta frase certa agora"),
                ),
                _candidate(
                    "medium-original",
                    _timed_words("ruido confuso inventa outra letra agora"),
                ),
                _candidate(
                    "medium-denoise",
                    _timed_words("texto distante mistura palavras sem apoio"),
                ),
            ],
            title="Teste",
        )

        report = format_consensus_report(result)

        self.assertIn("## Selection", report)
        self.assertIn("Mode: whole-candidate", report)
        self.assertIn("Fallback source: `turbo-vocals`", report)

    def test_report_includes_transcription_and_slide_mapping_for_validation(self) -> None:
        result = build_consensus_from_candidates(
            [
                _candidate(
                    "medium-original",
                    [
                        ("alfa", 1.0, 1.2),
                        ("beta", 1.3, 1.5),
                        ("gama", 4.0, 4.2),
                        ("delta", 4.3, 4.5),
                    ],
                )
            ],
            title="Teste",
        )

        report = format_consensus_report(
            result,
            slides=[
                Slide(lines=("alfa", "beta"), start_seconds=1.0),
                Slide(lines=("gama", "delta"), start_seconds=4.0),
            ],
        )

        self.assertIn("## Generated Transcription", report)
        self.assertIn("alfa beta gama delta", report)
        self.assertIn("## Generated Slide Mapping", report)
        self.assertIn("alfa\nbeta\n\ngama\ndelta", report)

    def test_parse_vtt_words_removes_repeated_caption_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "caption.pt.vtt"
            path.write_text(
                "\n".join(
                    [
                        "WEBVTT",
                        "",
                        "00:00:01.000 --> 00:00:02.000",
                        "<c>alfa beta</c>",
                        "",
                        "00:00:02.000 --> 00:00:03.000",
                        "beta gama",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            words = parse_vtt_words(path)

        self.assertEqual([word.text for word in words], ["alfa beta", "gama"])
        self.assertEqual(words[0].start, 1.0)
        self.assertEqual(words[1].end, 3.0)

    def test_phase1_generation_reports_unavailable_source_and_uses_caption(self) -> None:
        calls: list[tuple[str, str, str]] = []

        class FakeRunResult:
            returncode = 0
            stderr = ""

        def fake_run(command: list[str], **kwargs: object) -> FakeRunResult:
            del kwargs
            Path(command[-1]).write_bytes(b"denoise")
            return FakeRunResult()

        class FakeEngine:
            name = "fake"

            def transcribe(
                self,
                audio_path: Path,
                config: AudioToDocumentConfig,
            ) -> SimpleNamespace:
                model = config.whisper_model or "default"
                calls.append((Path(audio_path).name, model, config.vocal_separation))
                if model == "large-v3-turbo" and config.vocal_separation == "htdemucs_ft":
                    raise RuntimeError("separator unavailable")
                return SimpleNamespace(
                    transcript=Transcript(
                        words=[
                            TranscribedWord("alfa", 1.0, 1.2),
                            TranscribedWord("beta", 1.35, 1.55),
                        ],
                        detected_language="pt",
                        duration_seconds=5.0,
                    )
                )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            caption_path = tmp_path / "song.pt.vtt"
            audio_path.write_bytes(b"audio")
            caption_path.write_text(
                "\n".join(
                    [
                        "WEBVTT",
                        "",
                        "00:00:01.000 --> 00:00:02.000",
                        "alfa beta",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = build_phase1_consensus(
                audio_path=audio_path,
                engine=FakeEngine(),
                base_config=AudioToDocumentConfig(
                    cache=False,
                    cache_root=tmp_path / ".cache",
                    language="pt",
                ),
                title="Teste",
                youtube_caption_path=caption_path,
                run=fake_run,
            )

        self.assertIn(("phase1-denoise.wav", "medium", "none"), calls)
        self.assertEqual(
            calls[:2],
            [
                ("song.mp3", "large-v3-turbo", "htdemucs_ft"),
                ("song.mp3", "medium", "htdemucs_ft"),
            ],
        )
        self.assertIn("youtube-caption", {candidate.name for candidate in result.candidates})
        self.assertIn("turbo-vocals", {source.name for source in result.unavailable_sources})

    def test_phase1_generation_fails_clearly_when_all_sources_fail(self) -> None:
        class FakeRunResult:
            returncode = 1
            stderr = "ffmpeg missing"

        class FailingEngine:
            name = "fake"

            def transcribe(
                self,
                audio_path: Path,
                config: AudioToDocumentConfig,
            ) -> SimpleNamespace:
                del audio_path, config
                raise RuntimeError("whisper missing")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            audio_path.write_bytes(b"audio")

            with self.assertRaisesRegex(ValueError, "turbo-vocals: whisper missing"):
                build_phase1_consensus(
                    audio_path=audio_path,
                    engine=FailingEngine(),
                    base_config=AudioToDocumentConfig(
                        cache=False,
                        cache_root=tmp_path / ".cache",
                    ),
                    run=lambda *args, **kwargs: FakeRunResult(),
                )


if __name__ == "__main__":
    unittest.main()
