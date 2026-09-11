from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from louvorja_slides.slja import Slide, write_slja
from scripts import phase_gate_consensus


class PhaseGateTest(unittest.TestCase):
    def test_replay_phase_preserves_old_process_and_writes_comparisons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch_root = _make_batch(Path(tmp), video_count=2)
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = phase_gate_consensus.main(
                    [
                        "--batch-root",
                        str(batch_root),
                        "--metadata-jsonl",
                        str(batch_root / "metadata.jsonl"),
                        "--phase",
                        "1",
                        "--mode",
                        "replay-existing-candidates",
                        "--expected-count",
                        "2",
                        "--run-id",
                        "run-a",
                    ]
                )

            self.assertEqual(exit_code, 0)
            run_dir = batch_root / "phase-history" / "phase-1" / "run-a"
            self.assertTrue((run_dir / "baseline-old-process" / "asr-experiment-report.md").exists())
            self.assertTrue((run_dir / "baseline-old-process" / "input-metadata.jsonl").exists())
            self.assertTrue((run_dir / "baseline-old-process" / "video-1" / "best.slja").exists())
            self.assertTrue((run_dir / "baseline-old-process" / "video-2" / "medium-denoise.slja").exists())
            self.assertTrue((run_dir / "phase-output" / "video-1" / "best-consensus.slja").exists())
            self.assertTrue((run_dir / "phase-output" / "video-1" / "comparison.md").exists())

            report = json.loads((run_dir / "phase-gate-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["processed_count"], 2)
            self.assertEqual(report["summary"]["complete_comparisons"], 2)
            self.assertTrue(report["summary"]["full_set_complete"])
            self.assertIn("total_video_elapsed_seconds", report["summary"])
            self.assertIsNotNone(report["comparisons"][0]["effort"]["elapsed_seconds"])
            effort = json.loads((run_dir / "phase-effort-report.json").read_text(encoding="utf-8"))
            self.assertEqual(len(effort["videos"]), 2)
            self.assertIn("video-level phase execution", effort["summary"]["instrumentation_scope"])
            self.assertTrue((run_dir / "phase-effort-report.md").exists())
            self.assertIn("REPORT", stdout.getvalue())

    def test_limited_run_keeps_history_but_does_not_pass_full_set_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch_root = _make_batch(Path(tmp), video_count=2)

            with redirect_stdout(StringIO()):
                exit_code = phase_gate_consensus.main(
                    [
                        "--batch-root",
                        str(batch_root),
                        "--metadata-jsonl",
                        str(batch_root / "metadata.jsonl"),
                        "--phase",
                        "1",
                        "--mode",
                        "replay-existing-candidates",
                        "--expected-count",
                        "2",
                        "--limit",
                        "1",
                        "--run-id",
                        "run-limited",
                    ]
                )

            self.assertEqual(exit_code, 0)
            run_dir = batch_root / "phase-history" / "phase-1" / "run-limited"
            report = json.loads((run_dir / "phase-gate-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["processed_count"], 1)
            self.assertFalse(report["summary"]["full_set_complete"])
            self.assertFalse(report["summary"]["phase_gate_pass"])

    def test_existing_run_id_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch_root = _make_batch(Path(tmp), video_count=1)
            args = [
                "--batch-root",
                str(batch_root),
                "--metadata-jsonl",
                str(batch_root / "metadata.jsonl"),
                "--phase",
                "1",
                "--mode",
                "replay-existing-candidates",
                "--expected-count",
                "1",
                "--run-id",
                "same-run",
            ]

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(phase_gate_consensus.main(args), 0)
                self.assertEqual(phase_gate_consensus.main(args), 1)

    def test_summary_rejects_slide_explosion_even_when_hard_lines_improve(self) -> None:
        comparison = _comparison(
            "video-slide-explosion",
            baseline=_metrics(slide_count=10, line_count=20, over_hard=4),
            phase=_metrics(slide_count=31, line_count=62, over_hard=0),
        )

        summary = phase_gate_consensus.phase_gate_summary(
            phase="1",
            mode="execute",
            expected_count=1,
            discovered_count=1,
            comparisons=[comparison],
        )

        self.assertTrue(summary["hard_line_non_regression"])
        self.assertFalse(summary["slide_count_gate_pass"])
        self.assertFalse(summary["line_count_gate_pass"])
        self.assertFalse(summary["phase_gate_pass"])
        self.assertIn("slide count ratio", "\n".join(summary["gate_failures"]))

    def test_summary_allows_valid_wrap_equivalent_layout_growth(self) -> None:
        comparison = _comparison(
            "video-hard-wrapped-baseline",
            baseline=_metrics(
                slide_count=7,
                line_count=12,
                over_hard=8,
                text_words=360,
                hard_wrapped_line_count=38,
                hard_wrapped_slide_count=19,
            ),
            phase=_metrics(
                slide_count=19,
                line_count=38,
                over_hard=0,
                text_words=227,
            ),
        )

        summary = phase_gate_consensus.phase_gate_summary(
            phase="1",
            mode="execute",
            expected_count=1,
            discovered_count=1,
            comparisons=[comparison],
        )

        self.assertTrue(summary["slide_count_gate_pass"])
        self.assertTrue(summary["line_count_gate_pass"])
        self.assertTrue(summary["phase_gate_pass"])
        self.assertEqual(summary["baseline_total_comparable_slides"], 19)
        self.assertEqual(summary["baseline_total_comparable_lines"], 38)

    def test_summary_scales_layout_allowance_for_more_generated_words(self) -> None:
        comparison = _comparison(
            "video-more-words",
            baseline=_metrics(
                slide_count=6,
                line_count=9,
                over_hard=2,
                text_words=44,
            ),
            phase=_metrics(
                slide_count=16,
                line_count=32,
                over_hard=0,
                text_words=129,
            ),
        )

        summary = phase_gate_consensus.phase_gate_summary(
            phase="1",
            mode="execute",
            expected_count=1,
            discovered_count=1,
            comparisons=[comparison],
        )

        self.assertTrue(summary["slide_count_gate_pass"])
        self.assertTrue(summary["line_count_gate_pass"])
        self.assertTrue(summary["phase_gate_pass"])

    def test_summary_rejects_fast_transition_regression(self) -> None:
        comparison = _comparison(
            "video-fast",
            baseline=_metrics(slide_count=10, line_count=20, over_hard=4),
            phase=_metrics(
                slide_count=12,
                line_count=22,
                over_hard=0,
                fast_transitions=5,
            ),
        )

        summary = phase_gate_consensus.phase_gate_summary(
            phase="1",
            mode="execute",
            expected_count=1,
            discovered_count=1,
            comparisons=[comparison],
        )

        self.assertTrue(summary["hard_line_non_regression"])
        self.assertFalse(summary["fast_transition_gate_pass"])
        self.assertFalse(summary["phase_gate_pass"])
        self.assertIn("fast transition", "\n".join(summary["gate_failures"]))

    def test_summary_allows_isolated_fast_transition_when_ratio_stays_low(self) -> None:
        comparison = _comparison(
            "video-isolated-fast",
            baseline=_metrics(slide_count=120, line_count=240),
            phase=_metrics(
                slide_count=121,
                line_count=242,
                fast_transitions=1,
            ),
        )

        summary = phase_gate_consensus.phase_gate_summary(
            phase="1",
            mode="execute",
            expected_count=1,
            discovered_count=1,
            comparisons=[comparison],
        )

        self.assertTrue(summary["fast_transition_gate_pass"])
        self.assertTrue(summary["phase_gate_pass"])

    def test_summary_rejects_auxiliary_word_regression(self) -> None:
        comparison = _comparison(
            "video-aux",
            baseline=_metrics(
                slide_count=10,
                line_count=20,
                over_hard=4,
                aux_words=0,
                text_words=120,
            ),
            phase=_metrics(
                slide_count=12,
                line_count=22,
                over_hard=0,
                aux_words=18,
                text_words=120,
            ),
        )

        summary = phase_gate_consensus.phase_gate_summary(
            phase="1",
            mode="execute",
            expected_count=1,
            discovered_count=1,
            comparisons=[comparison],
        )

        self.assertTrue(summary["hard_line_non_regression"])
        self.assertFalse(summary["aux_word_gate_pass"])
        self.assertFalse(summary["phase_gate_pass"])
        self.assertIn("auxiliary word", "\n".join(summary["gate_failures"]))

    def test_summary_rejects_per_video_target_line_regression(self) -> None:
        comparison = _comparison(
            "video-target",
            baseline=_metrics(slide_count=10, line_count=20, over_hard=4),
            phase=_metrics(
                slide_count=12,
                line_count=20,
                over_hard=0,
                over_target=7,
            ),
        )

        summary = phase_gate_consensus.phase_gate_summary(
            phase="1",
            mode="execute",
            expected_count=1,
            discovered_count=1,
            comparisons=[comparison],
        )

        self.assertTrue(summary["hard_line_non_regression"])
        self.assertFalse(summary["target_line_gate_pass"])
        self.assertFalse(summary["phase_gate_pass"])
        self.assertIn("over-target line", "\n".join(summary["gate_failures"]))

    def test_summary_rejects_reference_lyrics_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            audio_path.write_bytes(b"audio")
            reference_path = tmp_path / "video-ref.txt"
            reference_path.write_text("alfa beta gama delta\n", encoding="utf-8")
            baseline_path = tmp_path / "baseline.slja"
            phase_path = tmp_path / "phase.slja"
            _write_archive_slides(
                audio_path=audio_path,
                output_path=baseline_path,
                title="Video Ref",
                slides=[Slide(lines=("alfa beta", "gama delta"), start_seconds=1.0)],
            )
            _write_archive_slides(
                audio_path=audio_path,
                output_path=phase_path,
                title="Video Ref",
                slides=[Slide(lines=("omega zeta",), start_seconds=1.0)],
            )
            comparison = phase_gate_consensus.VideoComparison(
                video_id="video-ref",
                title="Video Ref",
                baseline_best=phase_gate_consensus.archive_metrics(baseline_path),
                phase_output=phase_gate_consensus.archive_metrics(phase_path),
                baseline_candidates={},
                reference_lyrics_path=str(reference_path),
                baseline_reference=phase_gate_consensus.lyric_reference_metrics(
                    reference_path,
                    baseline_path,
                ),
                phase_reference=phase_gate_consensus.lyric_reference_metrics(
                    reference_path,
                    phase_path,
                ),
            )

            summary = phase_gate_consensus.phase_gate_summary(
                phase="1",
                mode="execute",
                expected_count=1,
                discovered_count=1,
                comparisons=[comparison],
            )

        self.assertFalse(summary["reference_lyrics_gate_pass"])
        self.assertFalse(summary["phase_gate_pass"])
        self.assertEqual(summary["reference_lyrics_count"], 1)
        self.assertIn("reference lyrics", "\n".join(summary["gate_failures"]))

    def test_summary_passes_when_secondary_metrics_stay_within_thresholds(self) -> None:
        comparison = _comparison(
            "video-ok",
            baseline=_metrics(slide_count=10, line_count=20, over_hard=4),
            phase=_metrics(slide_count=12, line_count=22, over_hard=0),
        )

        summary = phase_gate_consensus.phase_gate_summary(
            phase="1",
            mode="execute",
            expected_count=1,
            discovered_count=1,
            comparisons=[comparison],
        )

        self.assertTrue(summary["phase_gate_pass"])
        self.assertEqual(summary["gate_failures"], [])

    def test_report_lists_secondary_gate_failures(self) -> None:
        comparison = _comparison(
            "video-slide-explosion",
            baseline=_metrics(slide_count=10, line_count=20, over_hard=4),
            phase=_metrics(slide_count=31, line_count=62, over_hard=0),
        )
        summary = phase_gate_consensus.phase_gate_summary(
            phase="1",
            mode="execute",
            expected_count=1,
            discovered_count=1,
            comparisons=[comparison],
        )

        report = phase_gate_consensus.format_phase_gate_report(summary, [comparison])

        self.assertIn("## Gate Checks", report)
        self.assertIn("slide count ratio", report)
        self.assertIn("Line-count gate pass: False", report)

    def test_phase_report_includes_output_content_by_video(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            audio_path.write_bytes(b"audio")
            baseline_path = tmp_path / "baseline.slja"
            phase_path = tmp_path / "phase.slja"
            _write_archive_slides(
                audio_path=audio_path,
                output_path=baseline_path,
                title="Video Audit",
                slides=[
                    Slide(lines=("base alfa", "base beta"), start_seconds=1.0),
                    Slide(lines=("base gama",), start_seconds=5.0),
                ],
            )
            _write_archive_slides(
                audio_path=audio_path,
                output_path=phase_path,
                title="Video Audit",
                slides=[
                    Slide(lines=("phase alfa", "phase beta"), start_seconds=1.0),
                    Slide(lines=("phase gama",), start_seconds=5.0),
                ],
            )
            comparison = _comparison(
                "video-audit",
                baseline=phase_gate_consensus.archive_metrics(baseline_path),
                phase=phase_gate_consensus.archive_metrics(phase_path),
            )
            summary = phase_gate_consensus.phase_gate_summary(
                phase="1",
                mode="execute",
                expected_count=1,
                discovered_count=1,
                comparisons=[comparison],
            )

            report = phase_gate_consensus.format_phase_gate_report(summary, [comparison])

            self.assertIn("## Output Content By Video", report)
            self.assertIn("### video-audit", report)
            self.assertIn("phase alfa\nphase beta\n\nphase gama", report)
            self.assertIn("base alfa\nbase beta\n\nbase gama", report)

    def test_phase_report_keeps_reference_lyrics_out_of_output_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            audio_path.write_bytes(b"audio")
            reference_path = tmp_path / "video-ref.txt"
            reference_path.write_text("expected alfa beta\n", encoding="utf-8")
            baseline_path = tmp_path / "baseline.slja"
            phase_path = tmp_path / "phase.slja"
            _write_archive_slides(
                audio_path=audio_path,
                output_path=baseline_path,
                title="Video Ref",
                slides=[Slide(lines=("baseline wrong",), start_seconds=1.0)],
            )
            _write_archive_slides(
                audio_path=audio_path,
                output_path=phase_path,
                title="Video Ref",
                slides=[Slide(lines=("phase wrong",), start_seconds=1.0)],
            )
            comparison = phase_gate_consensus.VideoComparison(
                video_id="video-ref",
                title="Video Ref",
                baseline_best=phase_gate_consensus.archive_metrics(baseline_path),
                phase_output=phase_gate_consensus.archive_metrics(phase_path),
                baseline_candidates={},
                reference_lyrics_path=str(reference_path),
                baseline_reference=phase_gate_consensus.lyric_reference_metrics(
                    reference_path,
                    baseline_path,
                ),
                phase_reference=phase_gate_consensus.lyric_reference_metrics(
                    reference_path,
                    phase_path,
                ),
            )
            summary = phase_gate_consensus.phase_gate_summary(
                phase="1",
                mode="execute",
                expected_count=1,
                discovered_count=1,
                comparisons=[comparison],
            )

            report = phase_gate_consensus.format_phase_gate_report(summary, [comparison])

        self.assertIn("## Expected Reference Lyrics By Video (Not Generated)", report)
        self.assertIn("expected alfa beta", report)
        output_section = report.split("## Output Content By Video", maxsplit=1)[1]
        output_section = output_section.split("## Artifact Layout", maxsplit=1)[0]
        self.assertNotIn("expected alfa beta", output_section)
        self.assertIn("phase wrong", output_section)
        self.assertIn("baseline wrong", output_section)

    def test_video_comparison_includes_baseline_phase_and_candidate_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            audio_path.write_bytes(b"audio")
            baseline_path = tmp_path / "baseline.slja"
            phase_path = tmp_path / "phase.slja"
            candidate_path = tmp_path / "candidate.slja"
            _write_archive_slides(
                audio_path=audio_path,
                output_path=baseline_path,
                title="Video Audit",
                slides=[
                    Slide(lines=("base alfa", "base beta"), start_seconds=1.0),
                    Slide(lines=("base gama",), start_seconds=5.0),
                ],
            )
            _write_archive_slides(
                audio_path=audio_path,
                output_path=phase_path,
                title="Video Audit",
                slides=[
                    Slide(lines=("phase alfa", "phase beta"), start_seconds=1.0),
                    Slide(lines=("phase gama",), start_seconds=5.0),
                ],
            )
            _write_archive_slides(
                audio_path=audio_path,
                output_path=candidate_path,
                title="Video Audit",
                slides=[
                    Slide(lines=("cand alfa", "cand beta"), start_seconds=1.0),
                    Slide(lines=("cand gama",), start_seconds=5.0),
                ],
            )
            comparison = phase_gate_consensus.VideoComparison(
                video_id="video-audit",
                title="Video Audit",
                baseline_best=phase_gate_consensus.archive_metrics(baseline_path),
                phase_output=phase_gate_consensus.archive_metrics(phase_path),
                baseline_candidates={
                    "medium-original": phase_gate_consensus.archive_metrics(candidate_path)
                },
            )
            output_dir = tmp_path / "out"

            phase_gate_consensus.write_video_comparison(output_dir, comparison)

            report = (output_dir / "comparison.md").read_text(encoding="utf-8")
            self.assertIn("## Baseline Best Content", report)
            self.assertIn("base alfa\nbase beta\n\nbase gama", report)
            self.assertIn("## Phase Output Content", report)
            self.assertIn("phase alfa\nphase beta\n\nphase gama", report)
            self.assertIn("### medium-original", report)
            self.assertIn("cand alfa\ncand beta\n\ncand gama", report)

    def test_video_comparison_labels_reference_as_not_generated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            audio_path.write_bytes(b"audio")
            reference_path = tmp_path / "reference.txt"
            reference_path.write_text("expected text\n", encoding="utf-8")
            baseline_path = tmp_path / "baseline.slja"
            phase_path = tmp_path / "phase.slja"
            _write_archive_slides(
                audio_path=audio_path,
                output_path=baseline_path,
                title="Video Audit",
                slides=[Slide(lines=("baseline text",), start_seconds=1.0)],
            )
            _write_archive_slides(
                audio_path=audio_path,
                output_path=phase_path,
                title="Video Audit",
                slides=[Slide(lines=("phase text",), start_seconds=1.0)],
            )
            comparison = phase_gate_consensus.VideoComparison(
                video_id="video-audit",
                title="Video Audit",
                baseline_best=phase_gate_consensus.archive_metrics(baseline_path),
                phase_output=phase_gate_consensus.archive_metrics(phase_path),
                baseline_candidates={},
                reference_lyrics_path=str(reference_path),
                baseline_reference=phase_gate_consensus.lyric_reference_metrics(
                    reference_path,
                    baseline_path,
                ),
                phase_reference=phase_gate_consensus.lyric_reference_metrics(
                    reference_path,
                    phase_path,
                ),
            )
            output_dir = tmp_path / "out"

            phase_gate_consensus.write_video_comparison(output_dir, comparison)

            report = (output_dir / "comparison.md").read_text(encoding="utf-8")
            self.assertIn("## Expected Reference Lyrics Content (Not Generated)", report)
            self.assertIn("evaluation-only", report)
            self.assertIn("expected text", report)
            self.assertIn("## Phase Output Content", report)
            self.assertIn("phase text", report)

def _make_batch(root: Path, *, video_count: int) -> Path:
    batch_root = root / "batch"
    downloads = batch_root / "downloads"
    experiment = batch_root / "experiment"
    batch_root.mkdir()
    metadata_lines: list[str] = []
    for index in range(1, video_count + 1):
        video_id = f"video-{index}"
        title = f"Video {index}"
        metadata_lines.append(
            json.dumps({"id": video_id, "title": title, "duration": 12.0})
        )
        video_downloads = downloads / video_id
        video_downloads.mkdir(parents=True)
        audio_path = video_downloads / f"{video_id}.mp3"
        audio_path.write_bytes(b"audio")
        baseline_video_dir = experiment / video_id
        baseline_video_dir.mkdir(parents=True)
        _write_archive(
            audio_path=audio_path,
            output_path=baseline_video_dir / "best.slja",
            title=title,
            text=f"alfa {index} beta",
        )
        _write_archive(
            audio_path=audio_path,
            output_path=baseline_video_dir / "medium-original.slja",
            title=title,
            text=f"alfa {index} beta",
        )
        _write_archive(
            audio_path=audio_path,
            output_path=baseline_video_dir / "medium-denoise.slja",
            title=title,
            text=f"alfa {index} beta",
        )
    (batch_root / "metadata.jsonl").write_text(
        "\n".join(metadata_lines) + "\n",
        encoding="utf-8",
    )
    (experiment / "asr-experiment-report.md").write_text(
        "# Old report\n",
        encoding="utf-8",
    )
    return batch_root


def _write_archive(
    *,
    audio_path: Path,
    output_path: Path,
    title: str,
    text: str,
) -> None:
    write_slja(
        audio_path=audio_path,
        output_path=output_path,
        slides=[Slide(lines=(text,), start_seconds=1.0)],
        title=title,
    )


def _write_archive_slides(
    *,
    audio_path: Path,
    output_path: Path,
    title: str,
    slides: list[Slide],
) -> None:
    write_slja(
        audio_path=audio_path,
        output_path=output_path,
        slides=slides,
        title=title,
    )


def _metrics(
    *,
    slide_count: int,
    line_count: int,
    over_hard: int = 0,
    over_target: int = 0,
    aux_words: int = 0,
    fast_transitions: int = 0,
    text_words: int = 120,
    median_line_chars: float = 20.0,
    hard_wrapped_line_count: int = 0,
    hard_wrapped_slide_count: int = 0,
) -> phase_gate_consensus.ArchiveMetrics:
    return phase_gate_consensus.ArchiveMetrics(
        path="/tmp/test.slja",
        slide_count=slide_count,
        line_count=line_count,
        over_hard=over_hard,
        over_target=over_target,
        aux_words=aux_words,
        fast_transitions=fast_transitions,
        text_words=text_words,
        median_line_chars=median_line_chars,
        hard_wrapped_line_count=hard_wrapped_line_count,
        hard_wrapped_slide_count=hard_wrapped_slide_count,
    )


def _comparison(
    video_id: str,
    *,
    baseline: phase_gate_consensus.ArchiveMetrics,
    phase: phase_gate_consensus.ArchiveMetrics,
) -> phase_gate_consensus.VideoComparison:
    return phase_gate_consensus.VideoComparison(
        video_id=video_id,
        title=video_id,
        baseline_best=baseline,
        phase_output=phase,
        baseline_candidates={},
    )


if __name__ == "__main__":
    unittest.main()
