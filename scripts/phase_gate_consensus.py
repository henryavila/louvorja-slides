#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from louvorja_slides.consensus import (
    CONSENSUS_PHASE1_SOURCES,
    ConsensusCandidate,
    UnavailableConsensusSource,
    build_consensus_from_candidates,
    format_consensus_report,
)
from louvorja_slides.quality import analyze_slide_quality
from louvorja_slides.slja import Slide, read_slja, write_slja
from louvorja_slides.transcription import Transcript, TranscribedWord

_REPETITION_MARKER_RE = re.compile(r"^\(\d+x\)$", re.IGNORECASE)


@dataclass(frozen=True)
class VideoInput:
    video_id: str
    title: str
    duration_seconds: float
    audio_path: Path
    caption_path: Path | None = None


@dataclass(frozen=True)
class ArchiveMetrics:
    path: str
    slide_count: int
    line_count: int
    over_hard: int
    over_target: int
    aux_words: int
    fast_transitions: int
    text_words: int
    median_line_chars: float

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "slide_count": self.slide_count,
            "line_count": self.line_count,
            "over_hard": self.over_hard,
            "over_target": self.over_target,
            "aux_words": self.aux_words,
            "fast_transitions": self.fast_transitions,
            "text_words": self.text_words,
            "median_line_chars": self.median_line_chars,
        }


@dataclass(frozen=True)
class LyricReferenceMetrics:
    path: str
    reference_word_count: int
    output_word_count: int
    edit_distance: int
    word_error_rate: float
    word_similarity: float
    vocabulary_recall: float
    vocabulary_precision: float

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "reference_word_count": self.reference_word_count,
            "output_word_count": self.output_word_count,
            "edit_distance": self.edit_distance,
            "word_error_rate": self.word_error_rate,
            "word_similarity": self.word_similarity,
            "vocabulary_recall": self.vocabulary_recall,
            "vocabulary_precision": self.vocabulary_precision,
        }


@dataclass(frozen=True)
class PhaseGateThresholds:
    max_total_slide_ratio: float = 1.50
    max_video_slide_ratio: float = 2.00
    max_video_slide_delta: int = 4
    max_total_line_ratio: float = 1.75
    max_video_line_ratio: float = 2.50
    max_video_line_delta: int = 8
    max_total_fast_transition_delta: int = 0
    max_phase_fast_transition_ratio: float = 0.05
    max_total_aux_word_delta: int = 10
    max_total_aux_word_delta_ratio: float = 0.50
    max_phase_aux_word_ratio: float = 0.10
    max_phase_over_target_line_ratio: float = 0.30
    min_reference_word_similarity: float = 0.80
    max_reference_similarity_drop: float = 0.02

    def to_dict(self) -> dict[str, object]:
        return {
            "max_total_slide_ratio": self.max_total_slide_ratio,
            "max_video_slide_ratio": self.max_video_slide_ratio,
            "max_video_slide_delta": self.max_video_slide_delta,
            "max_total_line_ratio": self.max_total_line_ratio,
            "max_video_line_ratio": self.max_video_line_ratio,
            "max_video_line_delta": self.max_video_line_delta,
            "max_total_fast_transition_delta": self.max_total_fast_transition_delta,
            "max_phase_fast_transition_ratio": self.max_phase_fast_transition_ratio,
            "max_total_aux_word_delta": self.max_total_aux_word_delta,
            "max_total_aux_word_delta_ratio": self.max_total_aux_word_delta_ratio,
            "max_phase_aux_word_ratio": self.max_phase_aux_word_ratio,
            "max_phase_over_target_line_ratio": self.max_phase_over_target_line_ratio,
            "min_reference_word_similarity": self.min_reference_word_similarity,
            "max_reference_similarity_drop": self.max_reference_similarity_drop,
        }


@dataclass(frozen=True)
class VideoComparison:
    video_id: str
    title: str
    baseline_best: ArchiveMetrics | None
    phase_output: ArchiveMetrics | None
    baseline_candidates: dict[str, ArchiveMetrics]
    command: tuple[str, ...] = ()
    returncode: int | None = None
    error: str = ""
    started_at: str = ""
    finished_at: str = ""
    elapsed_seconds: float | None = None
    cache_bytes_before: int | None = None
    cache_bytes_after: int | None = None
    phase_output_bytes: int | None = None
    reference_lyrics_path: str = ""
    baseline_reference: LyricReferenceMetrics | None = None
    phase_reference: LyricReferenceMetrics | None = None

    @property
    def complete(self) -> bool:
        return self.baseline_best is not None and self.phase_output is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "complete": self.complete,
            "baseline_best": (
                self.baseline_best.to_dict() if self.baseline_best is not None else None
            ),
            "phase_output": (
                self.phase_output.to_dict() if self.phase_output is not None else None
            ),
            "baseline_candidates": {
                name: metrics.to_dict()
                for name, metrics in sorted(self.baseline_candidates.items())
            },
            "delta": _delta_dict(self.baseline_best, self.phase_output),
            "command": list(self.command),
            "returncode": self.returncode,
            "error": self.error,
            "effort": _effort_dict(self),
            "reference_lyrics_path": self.reference_lyrics_path,
            "baseline_reference": (
                self.baseline_reference.to_dict()
                if self.baseline_reference is not None
                else None
            ),
            "phase_reference": (
                self.phase_reference.to_dict()
                if self.phase_reference is not None
                else None
            ),
        }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        run_phase_gate(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a consensus phase gate over the full batch while preserving "
            "old-process artifacts and per-phase history."
        )
    )
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--metadata-jsonl", type=Path, required=True)
    parser.add_argument("--baseline-dir", type=Path, default=None)
    parser.add_argument("--history-root", type=Path, default=None)
    parser.add_argument(
        "--reference-lyrics-dir",
        type=Path,
        default=Path("quality_references/lyrics"),
        help=(
            "Optional directory with expected lyrics named <video_id>.txt. "
            "When present, phase output is gated against those lyrics."
        ),
    )
    parser.add_argument("--phase", choices=("1", "2", "3", "4", "full"), required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--expected-count", type=int, default=11)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--mode",
        choices=("execute", "replay-existing-candidates"),
        default="execute",
        help=(
            "execute runs audio_to_slja.py for the phase; replay-existing-candidates "
            "builds phase 1 consensus from old .slja candidates for analysis only."
        ),
    )
    parser.add_argument(
        "--quality-gate",
        choices=("fail", "warn", "off"),
        default="warn",
        help="Quality gate passed to audio_to_slja.py in execute mode.",
    )
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--script-path", type=Path, default=Path("audio_to_slja.py"))
    parser.add_argument(
        "--extra-cli-arg",
        action="append",
        default=[],
        help="Extra argument appended to each audio_to_slja.py execution.",
    )
    return parser


def run_phase_gate(args: argparse.Namespace) -> Path:
    batch_root = Path(args.batch_root)
    baseline_dir = Path(args.baseline_dir) if args.baseline_dir else batch_root / "experiment"
    history_root = (
        Path(args.history_root) if args.history_root else batch_root / "phase-history"
    )
    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = history_root / f"phase-{args.phase}" / run_id
    if run_dir.exists():
        raise ValueError(f"phase history run already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    all_videos = discover_inputs(batch_root / "downloads", Path(args.metadata_jsonl))
    videos = all_videos[: args.limit] if args.limit else all_videos
    cache_dir = Path(args.cache_dir) if args.cache_dir else batch_root / "phase-cache"
    baseline_snapshot = run_dir / "baseline-old-process"
    phase_output_dir = run_dir / "phase-output"
    baseline_snapshot.mkdir()
    phase_output_dir.mkdir()
    snapshot_old_process_root(
        baseline_dir=baseline_dir,
        metadata_jsonl=Path(args.metadata_jsonl),
        output_dir=baseline_snapshot,
    )

    comparisons: list[VideoComparison] = []
    for video in videos:
        print(f"=== {video.video_id} {video.title} ===", flush=True)
        video_started_at = datetime.now(UTC)
        video_started_monotonic = time.monotonic()
        cache_bytes_before = _tree_size_bytes(cache_dir)
        video_output_dir = phase_output_dir / video.video_id
        copied = snapshot_old_process(
            video=video,
            baseline_dir=baseline_dir,
            output_dir=baseline_snapshot / video.video_id,
        )
        if args.mode == "replay-existing-candidates":
            comparison = replay_phase_from_old_candidates(
                video=video,
                phase=args.phase,
                baseline_snapshot_dir=baseline_snapshot / video.video_id,
                output_dir=video_output_dir,
            )
        else:
            comparison = execute_phase(
                video=video,
                phase=args.phase,
                output_dir=video_output_dir,
                cache_dir=cache_dir,
                python_exe=str(args.python_exe),
                script_path=Path(args.script_path),
                quality_gate=str(args.quality_gate),
                extra_cli_args=tuple(str(item) for item in args.extra_cli_arg),
            )
        video_finished_at = datetime.now(UTC)
        merged = comparison_with_baseline(
            comparison,
            baseline_snapshot_dir=baseline_snapshot / video.video_id,
            copied_sources=copied,
            reference_lyrics_path=reference_lyrics_path(
                video,
                Path(args.reference_lyrics_dir),
            ),
        )
        merged = replace(
            merged,
            started_at=video_started_at.isoformat(),
            finished_at=video_finished_at.isoformat(),
            elapsed_seconds=round(time.monotonic() - video_started_monotonic, 3),
            cache_bytes_before=cache_bytes_before,
            cache_bytes_after=_tree_size_bytes(cache_dir),
            phase_output_bytes=_tree_size_bytes(video_output_dir),
        )
        write_video_comparison(video_output_dir, merged)
        comparisons.append(merged)

    manifest = {
        "run_id": run_id,
        "phase": args.phase,
        "mode": args.mode,
        "created_at": datetime.now(UTC).isoformat(),
        "batch_root": str(batch_root),
        "baseline_dir": str(baseline_dir),
        "history_root": str(history_root),
        "reference_lyrics_dir": str(Path(args.reference_lyrics_dir)),
        "expected_count": args.expected_count,
        "discovered_count": len(all_videos),
        "processed_count": len(videos),
        "limit": args.limit,
        "videos": [video.video_id for video in videos],
    }
    (run_dir / "run-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_phase_gate_reports(
        run_dir=run_dir,
        phase=args.phase,
        mode=args.mode,
        expected_count=int(args.expected_count),
        discovered_count=len(all_videos),
        comparisons=comparisons,
    )
    print(f"REPORT {run_dir / 'phase-gate-report.md'}")
    return run_dir


def discover_inputs(downloads: Path, metadata_jsonl: Path) -> list[VideoInput]:
    metadata: dict[str, dict[str, Any]] = {}
    for line in metadata_jsonl.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            metadata[str(item["id"])] = item

    videos: list[VideoInput] = []
    for video_id, item in metadata.items():
        directory = downloads / video_id
        mp3s = sorted(directory.glob("*.mp3"))
        if not mp3s:
            continue
        videos.append(
            VideoInput(
                video_id=video_id,
                title=str(item.get("title") or video_id),
                duration_seconds=float(item.get("duration") or 0.0),
                audio_path=mp3s[0],
                caption_path=pick_caption(directory),
            )
        )
    return videos


def pick_caption(directory: Path) -> Path | None:
    for pattern in ("*.pt-orig.vtt", "*.pt.vtt", "*.pt-BR.vtt"):
        matches = sorted(directory.glob(pattern))
        if matches:
            return matches[0]
    return None


def snapshot_old_process(
    *,
    video: VideoInput,
    baseline_dir: Path,
    output_dir: Path,
) -> dict[str, Path]:
    source_dir = Path(baseline_dir) / video.video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, Path] = {}
    if not source_dir.exists():
        return copied

    for source_path in sorted(source_dir.glob("*.slja")):
        target = output_dir / source_path.name
        shutil.copy2(source_path, target)
        copied[source_path.stem] = target
    report = source_dir / "consensus-report.md"
    if report.exists():
        shutil.copy2(report, output_dir / report.name)
    return copied


def snapshot_old_process_root(
    *,
    baseline_dir: Path,
    metadata_jsonl: Path,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if metadata_jsonl.exists():
        shutil.copy2(metadata_jsonl, output_dir / "input-metadata.jsonl")
    if not baseline_dir.exists():
        return
    for pattern in ("*.md", "*.json", "*.jsonl", "*.txt"):
        for source_path in sorted(baseline_dir.glob(pattern)):
            if source_path.is_file():
                shutil.copy2(source_path, output_dir / source_path.name)


def replay_phase_from_old_candidates(
    *,
    video: VideoInput,
    phase: str,
    baseline_snapshot_dir: Path,
    output_dir: Path,
) -> VideoComparison:
    output_dir.mkdir(parents=True, exist_ok=True)
    if phase != "1":
        return VideoComparison(
            video_id=video.video_id,
            title=video.title,
            baseline_best=None,
            phase_output=None,
            baseline_candidates={},
            error="replay-existing-candidates is only available for phase 1",
        )

    candidates: list[ConsensusCandidate] = []
    unavailable: list[UnavailableConsensusSource] = []
    source_names = (*CONSENSUS_PHASE1_SOURCES, "youtube-caption")
    for source_name in source_names:
        source_path = baseline_snapshot_dir / f"{source_name}.slja"
        if not source_path.exists():
            unavailable.append(UnavailableConsensusSource(source_name, "old candidate missing"))
            continue
        candidates.append(
            ConsensusCandidate(
                name=source_name,
                transcript=transcript_from_slja(
                    source_path,
                    source=source_name,
                    duration_seconds=video.duration_seconds,
                ),
            )
        )

    if not candidates:
        return VideoComparison(
            video_id=video.video_id,
            title=video.title,
            baseline_best=None,
            phase_output=None,
            baseline_candidates={},
            error="no old candidate archives available for replay",
        )

    result = build_consensus_from_candidates(
        candidates,
        title=video.title,
        language="pt",
        unavailable_sources=unavailable,
        phase=phase,
    )
    output_path = output_dir / "best-consensus.slja"
    write_slja(
        audio_path=video.audio_path,
        output_path=output_path,
        slides=_slides_from_result(result),
        title=video.title,
    )
    report_path = output_dir / "consensus-report.md"
    report_path.write_text(
        format_consensus_report(result, slides=read_slja(output_path).slides),
        encoding="utf-8",
    )
    return VideoComparison(
        video_id=video.video_id,
        title=video.title,
        baseline_best=None,
        phase_output=archive_metrics(output_path),
        baseline_candidates={},
    )


def execute_phase(
    *,
    video: VideoInput,
    phase: str,
    output_dir: Path,
    cache_dir: Path,
    python_exe: str,
    script_path: Path,
    quality_gate: str,
    extra_cli_args: tuple[str, ...] = (),
) -> VideoComparison:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "best-consensus.slja"
    report_path = output_dir / "consensus-report.md"
    command = [
        python_exe,
        str(script_path),
        str(video.audio_path),
        "--output",
        str(output_path),
        "--title",
        video.title,
        "--engine",
        "local",
        "--transcription-strategy",
        "consensus",
        "--consensus-phase",
        phase,
        "--quality-gate",
        quality_gate,
        "--cache-dir",
        str(cache_dir),
        "--report-path",
        str(report_path),
    ]
    if video.caption_path is not None:
        command.extend(["--youtube-caption-file", str(video.caption_path)])
    command.extend(extra_cli_args)

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    (output_dir / "stdout.log").write_text(result.stdout, encoding="utf-8")
    (output_dir / "stderr.log").write_text(result.stderr, encoding="utf-8")
    phase_metrics = archive_metrics(output_path) if output_path.exists() else None
    return VideoComparison(
        video_id=video.video_id,
        title=video.title,
        baseline_best=None,
        phase_output=phase_metrics,
        baseline_candidates={},
        command=tuple(command),
        returncode=result.returncode,
        error="" if result.returncode == 0 else _one_line(result.stderr),
    )


def comparison_with_baseline(
    comparison: VideoComparison,
    *,
    baseline_snapshot_dir: Path,
    copied_sources: dict[str, Path],
    reference_lyrics_path: Path | None = None,
) -> VideoComparison:
    baseline_best_path = baseline_snapshot_dir / "best.slja"
    baseline_best = archive_metrics(baseline_best_path) if baseline_best_path.exists() else None
    baseline_candidates = {
        name: archive_metrics(path)
        for name, path in sorted(copied_sources.items())
        if path.name != "best.slja"
    }
    merged = VideoComparison(
        video_id=comparison.video_id,
        title=comparison.title,
        baseline_best=baseline_best,
        phase_output=comparison.phase_output,
        baseline_candidates=baseline_candidates,
        command=comparison.command,
        returncode=comparison.returncode,
        error=comparison.error,
        reference_lyrics_path=str(reference_lyrics_path or ""),
        baseline_reference=(
            lyric_reference_metrics(reference_lyrics_path, baseline_best_path)
            if reference_lyrics_path is not None and baseline_best_path.exists()
            else None
        ),
        phase_reference=(
            lyric_reference_metrics(reference_lyrics_path, Path(comparison.phase_output.path))
            if reference_lyrics_path is not None and comparison.phase_output is not None
            else None
        ),
    )
    return merged


def reference_lyrics_path(video: VideoInput, directory: Path) -> Path | None:
    candidates = [
        Path(directory) / f"{video.video_id}.txt",
        Path(directory) / f"{_slug(video.title)}.txt",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def transcript_from_slja(
    path: Path,
    *,
    source: str,
    duration_seconds: float,
) -> Transcript:
    archive = read_slja(path)
    slides = list(archive.slides)
    words: list[TranscribedWord] = []
    for index, slide in enumerate(slides):
        start = slide.start_seconds
        next_start = (
            slides[index + 1].start_seconds
            if index + 1 < len(slides)
            else max(duration_seconds, start + 4.0)
        )
        end = max(start + 0.1, next_start)
        tokens = _slide_tokens(slide)
        if not tokens:
            continue
        step = (end - start) / len(tokens)
        for token_index, token in enumerate(tokens):
            word_start = start + token_index * step
            words.append(
                TranscribedWord(
                    text=token,
                    start=word_start,
                    end=min(end, word_start + step),
                    source=source,
                )
            )
    if not words:
        raise ValueError(f"archive has no lyric words: {path}")
    return Transcript(
        words=words,
        detected_language="pt",
        duration_seconds=max(duration_seconds, words[-1].end, 1.0),
    )


def archive_metrics(path: Path) -> ArchiveMetrics:
    archive = read_slja(path)
    report = analyze_slide_quality(archive.slides)
    return ArchiveMetrics(
        path=str(path),
        slide_count=report.slide_count,
        line_count=report.line_count,
        over_hard=report.over_hard_line_count,
        over_target=report.over_target_line_count,
        aux_words=report.auxiliary_word_count,
        fast_transitions=report.fast_transition_count,
        text_words=_text_word_count(_slide_text(archive.slides)),
        median_line_chars=report.median_line_chars,
    )


def lyric_reference_metrics(
    reference_path: Path,
    archive_path: Path,
) -> LyricReferenceMetrics:
    reference_text = Path(reference_path).read_text(encoding="utf-8")
    archive = read_slja(archive_path)
    output_text = _slide_text(archive.slides)
    reference_words = _normalized_words(reference_text)
    output_words = _normalized_words(output_text)
    edit_distance = _word_edit_distance(reference_words, output_words)
    word_error_rate = (
        edit_distance / len(reference_words) if reference_words else 1.0
    )
    reference_vocab = set(reference_words)
    output_vocab = set(output_words)
    vocabulary_recall = (
        len(reference_vocab & output_vocab) / len(reference_vocab)
        if reference_vocab
        else 0.0
    )
    vocabulary_precision = (
        len(reference_vocab & output_vocab) / len(output_vocab)
        if output_vocab
        else 0.0
    )
    return LyricReferenceMetrics(
        path=str(reference_path),
        reference_word_count=len(reference_words),
        output_word_count=len(output_words),
        edit_distance=edit_distance,
        word_error_rate=round(word_error_rate, 4),
        word_similarity=round(max(0.0, 1.0 - word_error_rate), 4),
        vocabulary_recall=round(vocabulary_recall, 4),
        vocabulary_precision=round(vocabulary_precision, 4),
    )


def write_phase_gate_reports(
    *,
    run_dir: Path,
    phase: str,
    mode: str,
    expected_count: int,
    discovered_count: int,
    comparisons: list[VideoComparison],
) -> None:
    summary = phase_gate_summary(
        phase=phase,
        mode=mode,
        expected_count=expected_count,
        discovered_count=discovered_count,
        comparisons=comparisons,
    )
    (run_dir / "phase-gate-report.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "comparisons": [comparison.to_dict() for comparison in comparisons],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "phase-gate-report.md").write_text(
        format_phase_gate_report(summary, comparisons),
        encoding="utf-8",
    )
    write_phase_effort_reports(run_dir=run_dir, summary=summary, comparisons=comparisons)


def write_phase_effort_reports(
    *,
    run_dir: Path,
    summary: dict[str, object],
    comparisons: list[VideoComparison],
) -> None:
    effort_rows = [
        {
            "video_id": comparison.video_id,
            "title": comparison.title,
            "complete": comparison.complete,
            "returncode": comparison.returncode,
            "error": comparison.error,
            **_effort_dict(comparison),
        }
        for comparison in comparisons
    ]
    payload = {
        "summary": {
            "total_video_elapsed_seconds": summary["total_video_elapsed_seconds"],
            "average_video_elapsed_seconds": summary["average_video_elapsed_seconds"],
            "cache_growth_bytes": summary["cache_growth_bytes"],
            "phase_output_total_bytes": summary["phase_output_total_bytes"],
            "instrumentation_scope": (
                "video-level phase execution; per-source candidate timing is "
                "not captured yet"
            ),
        },
        "videos": effort_rows,
    }
    (run_dir / "phase-effort-report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Phase Effort Report",
        "",
        "Scope: video-level phase execution. Per-source candidate timing is not captured yet.",
        "",
        "## Summary",
        "",
        f"- Total per-video elapsed: {_format_seconds(float(summary['total_video_elapsed_seconds']))}",
        f"- Average per-video elapsed: {_format_seconds(float(summary['average_video_elapsed_seconds']))}",
        f"- Cache growth: {_format_bytes(int(summary['cache_growth_bytes']))}",
        f"- Phase output size: {_format_bytes(int(summary['phase_output_total_bytes']))}",
        "",
        "## Per Video",
        "",
        "| Video | Complete | Elapsed | Cache delta | Output size | Return code | Error |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for comparison in comparisons:
        lines.append(
            "| "
            f"`{comparison.video_id}` | {comparison.complete} | "
            f"{_format_seconds(comparison.elapsed_seconds)} | "
            f"{_format_bytes(_byte_delta(comparison.cache_bytes_before, comparison.cache_bytes_after))} | "
            f"{_format_bytes(comparison.phase_output_bytes)} | "
            f"{comparison.returncode if comparison.returncode is not None else '-'} | "
            f"{_escape_pipe(comparison.error or '-')} |"
        )
    (run_dir / "phase-effort-report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def phase_gate_summary(
    *,
    phase: str,
    mode: str,
    expected_count: int,
    discovered_count: int,
    comparisons: list[VideoComparison],
    thresholds: PhaseGateThresholds | None = None,
) -> dict[str, object]:
    cfg = thresholds or PhaseGateThresholds()
    complete = [comparison for comparison in comparisons if comparison.complete]
    baseline_hard = sum(
        comparison.baseline_best.over_hard
        for comparison in complete
        if comparison.baseline_best is not None
    )
    phase_hard = sum(
        comparison.phase_output.over_hard
        for comparison in complete
        if comparison.phase_output is not None
    )
    processed_count = len(comparisons)
    full_set_complete = (
        discovered_count == expected_count
        and processed_count == expected_count
        and len(complete) == expected_count
    )
    hard_line_non_regression = full_set_complete and phase_hard <= baseline_hard
    baseline_slides = _total_metric(complete, "baseline_best", "slide_count")
    phase_slides = _total_metric(complete, "phase_output", "slide_count")
    baseline_lines = _total_metric(complete, "baseline_best", "line_count")
    phase_lines = _total_metric(complete, "phase_output", "line_count")
    baseline_fast_transitions = _total_metric(
        complete,
        "baseline_best",
        "fast_transitions",
    )
    phase_fast_transitions = _total_metric(
        complete,
        "phase_output",
        "fast_transitions",
    )
    baseline_aux_words = _total_metric(complete, "baseline_best", "aux_words")
    phase_aux_words = _total_metric(complete, "phase_output", "aux_words")
    baseline_text_words = _total_metric(complete, "baseline_best", "text_words")
    phase_text_words = _total_metric(complete, "phase_output", "text_words")
    baseline_over_target = _total_metric(complete, "baseline_best", "over_target")
    phase_over_target = _total_metric(complete, "phase_output", "over_target")
    baseline_transition_slots = sum(
        max(0, comparison.baseline_best.slide_count - 1)
        for comparison in complete
        if comparison.baseline_best is not None
    )
    phase_transition_slots = sum(
        max(0, comparison.phase_output.slide_count - 1)
        for comparison in complete
        if comparison.phase_output is not None
    )
    slide_count_ratio = _safe_ratio(phase_slides, baseline_slides)
    line_count_ratio = _safe_ratio(phase_lines, baseline_lines)
    baseline_fast_transition_ratio = _safe_ratio(
        baseline_fast_transitions,
        baseline_transition_slots,
    )
    phase_fast_transition_ratio = _safe_ratio(
        phase_fast_transitions,
        phase_transition_slots,
    )
    baseline_aux_word_ratio = _safe_ratio(baseline_aux_words, baseline_text_words)
    phase_aux_word_ratio = _safe_ratio(phase_aux_words, phase_text_words)
    baseline_over_target_ratio = _safe_ratio(baseline_over_target, baseline_lines)
    phase_over_target_ratio = _safe_ratio(phase_over_target, phase_lines)
    slide_count_gate_pass = full_set_complete and _slide_count_gate_pass(
        complete,
        cfg,
    )
    line_count_gate_pass = full_set_complete and _line_count_gate_pass(complete, cfg)
    fast_transition_gate_pass = (
        full_set_complete
        and phase_fast_transitions - baseline_fast_transitions
        <= cfg.max_total_fast_transition_delta
        and phase_fast_transition_ratio <= cfg.max_phase_fast_transition_ratio
    )
    aux_word_delta = phase_aux_words - baseline_aux_words
    aux_word_gate_pass = (
        full_set_complete
        and aux_word_delta <= _allowed_aux_word_delta(baseline_aux_words, cfg)
        and phase_aux_word_ratio <= cfg.max_phase_aux_word_ratio
    )
    target_line_gate_pass = (
        full_set_complete
        and phase_over_target_ratio <= cfg.max_phase_over_target_line_ratio
        and all(
            _safe_ratio(comparison.phase_output.over_target, comparison.phase_output.line_count)
            <= cfg.max_phase_over_target_line_ratio
            for comparison in complete
            if comparison.phase_output is not None
        )
    )
    reference_comparisons = [
        comparison for comparison in complete if comparison.phase_reference is not None
    ]
    reference_lyrics_gate_pass = full_set_complete and _reference_lyrics_gate_pass(
        reference_comparisons,
        cfg,
    )
    if not reference_comparisons:
        reference_lyrics_gate_pass = full_set_complete
    reference_phase_similarities = [
        comparison.phase_reference.word_similarity
        for comparison in reference_comparisons
        if comparison.phase_reference is not None
    ]
    gate_failures = _phase_gate_failures(
        complete=complete,
        full_set_complete=full_set_complete,
        hard_line_non_regression=hard_line_non_regression,
        slide_count_gate_pass=slide_count_gate_pass,
        line_count_gate_pass=line_count_gate_pass,
        fast_transition_gate_pass=fast_transition_gate_pass,
        aux_word_gate_pass=aux_word_gate_pass,
        target_line_gate_pass=target_line_gate_pass,
        reference_lyrics_gate_pass=reference_lyrics_gate_pass,
        thresholds=cfg,
        expected_count=expected_count,
        discovered_count=discovered_count,
        processed_count=processed_count,
        complete_count=len(complete),
        baseline_hard=baseline_hard,
        phase_hard=phase_hard,
        baseline_slides=baseline_slides,
        phase_slides=phase_slides,
        baseline_lines=baseline_lines,
        phase_lines=phase_lines,
        baseline_fast_transitions=baseline_fast_transitions,
        phase_fast_transitions=phase_fast_transitions,
        phase_fast_transition_ratio=phase_fast_transition_ratio,
        baseline_aux_words=baseline_aux_words,
        phase_aux_words=phase_aux_words,
        phase_aux_word_ratio=phase_aux_word_ratio,
        phase_over_target_ratio=phase_over_target_ratio,
    )
    elapsed_seconds = [
        comparison.elapsed_seconds
        for comparison in comparisons
        if comparison.elapsed_seconds is not None
    ]
    cache_before_values = [
        comparison.cache_bytes_before
        for comparison in comparisons
        if comparison.cache_bytes_before is not None
    ]
    cache_after_values = [
        comparison.cache_bytes_after
        for comparison in comparisons
        if comparison.cache_bytes_after is not None
    ]
    return {
        "phase": phase,
        "mode": mode,
        "expected_count": expected_count,
        "discovered_count": discovered_count,
        "processed_count": processed_count,
        "complete_comparisons": len(complete),
        "full_set_complete": full_set_complete,
        "baseline_total_hard_lines": baseline_hard,
        "phase_total_hard_lines": phase_hard,
        "hard_line_delta": phase_hard - baseline_hard,
        "hard_line_non_regression": hard_line_non_regression,
        "baseline_total_slides": baseline_slides,
        "phase_total_slides": phase_slides,
        "slide_count_delta": phase_slides - baseline_slides,
        "slide_count_ratio": round(slide_count_ratio, 3),
        "slide_count_gate_pass": slide_count_gate_pass,
        "baseline_total_lines": baseline_lines,
        "phase_total_lines": phase_lines,
        "line_count_delta": phase_lines - baseline_lines,
        "line_count_ratio": round(line_count_ratio, 3),
        "line_count_gate_pass": line_count_gate_pass,
        "baseline_total_fast_transitions": baseline_fast_transitions,
        "phase_total_fast_transitions": phase_fast_transitions,
        "fast_transition_delta": phase_fast_transitions - baseline_fast_transitions,
        "baseline_fast_transition_ratio": round(baseline_fast_transition_ratio, 4),
        "phase_fast_transition_ratio": round(phase_fast_transition_ratio, 4),
        "fast_transition_gate_pass": fast_transition_gate_pass,
        "baseline_total_aux_words": baseline_aux_words,
        "phase_total_aux_words": phase_aux_words,
        "aux_word_delta": aux_word_delta,
        "baseline_aux_word_ratio": round(baseline_aux_word_ratio, 4),
        "phase_aux_word_ratio": round(phase_aux_word_ratio, 4),
        "aux_word_gate_pass": aux_word_gate_pass,
        "baseline_total_over_target_lines": baseline_over_target,
        "phase_total_over_target_lines": phase_over_target,
        "over_target_line_delta": phase_over_target - baseline_over_target,
        "baseline_over_target_line_ratio": round(baseline_over_target_ratio, 4),
        "phase_over_target_line_ratio": round(phase_over_target_ratio, 4),
        "target_line_gate_pass": target_line_gate_pass,
        "reference_lyrics_count": len(reference_comparisons),
        "reference_lyrics_gate_pass": reference_lyrics_gate_pass,
        "min_phase_reference_word_similarity": (
            round(min(reference_phase_similarities), 4)
            if reference_phase_similarities
            else None
        ),
        "gate_thresholds": cfg.to_dict(),
        "gate_failures": list(gate_failures),
        "phase_gate_pass": not gate_failures,
        "total_video_elapsed_seconds": round(sum(elapsed_seconds), 3),
        "average_video_elapsed_seconds": (
            round(sum(elapsed_seconds) / len(elapsed_seconds), 3)
            if elapsed_seconds
            else 0.0
        ),
        "phase_output_total_bytes": sum(
            comparison.phase_output_bytes or 0 for comparison in comparisons
        ),
        "cache_growth_bytes": (
            max(cache_after_values) - min(cache_before_values)
            if cache_before_values and cache_after_values
            else 0
        ),
    }


def _total_metric(
    comparisons: list[VideoComparison],
    side: str,
    field: str,
) -> int:
    total = 0
    for comparison in comparisons:
        metrics = getattr(comparison, side)
        if metrics is not None:
            total += int(getattr(metrics, field))
    return total


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 0.0 if numerator == 0 else float("inf")
    return float(numerator) / float(denominator)


def _slide_count_gate_pass(
    comparisons: list[VideoComparison],
    cfg: PhaseGateThresholds,
) -> bool:
    baseline_slides = _total_metric(comparisons, "baseline_best", "slide_count")
    phase_slides = _total_metric(comparisons, "phase_output", "slide_count")
    if _safe_ratio(phase_slides, baseline_slides) > cfg.max_total_slide_ratio:
        return False
    return all(
        _within_relative_metric_limit(
            baseline=comparison.baseline_best.slide_count,
            phase=comparison.phase_output.slide_count,
            ratio=cfg.max_video_slide_ratio,
            delta=cfg.max_video_slide_delta,
        )
        for comparison in comparisons
        if comparison.baseline_best is not None and comparison.phase_output is not None
    )


def _line_count_gate_pass(
    comparisons: list[VideoComparison],
    cfg: PhaseGateThresholds,
) -> bool:
    baseline_lines = _total_metric(comparisons, "baseline_best", "line_count")
    phase_lines = _total_metric(comparisons, "phase_output", "line_count")
    if _safe_ratio(phase_lines, baseline_lines) > cfg.max_total_line_ratio:
        return False
    return all(
        _within_relative_metric_limit(
            baseline=comparison.baseline_best.line_count,
            phase=comparison.phase_output.line_count,
            ratio=cfg.max_video_line_ratio,
            delta=cfg.max_video_line_delta,
        )
        for comparison in comparisons
        if comparison.baseline_best is not None and comparison.phase_output is not None
    )


def _reference_lyrics_gate_pass(
    comparisons: list[VideoComparison],
    cfg: PhaseGateThresholds,
) -> bool:
    return all(
        _reference_comparison_passes(comparison, cfg)
        for comparison in comparisons
    )


def _reference_comparison_passes(
    comparison: VideoComparison,
    cfg: PhaseGateThresholds,
) -> bool:
    if comparison.phase_reference is None:
        return True
    if comparison.phase_reference.word_similarity < cfg.min_reference_word_similarity:
        return False
    if comparison.baseline_reference is not None:
        allowed = (
            comparison.baseline_reference.word_similarity
            - cfg.max_reference_similarity_drop
        )
        if comparison.phase_reference.word_similarity < allowed:
            return False
    return True


def _within_relative_metric_limit(
    *,
    baseline: int,
    phase: int,
    ratio: float,
    delta: int,
) -> bool:
    allowed = max(baseline + delta, math.ceil(baseline * ratio))
    return phase <= allowed


def _allowed_aux_word_delta(
    baseline_aux_words: int,
    cfg: PhaseGateThresholds,
) -> int:
    return max(
        cfg.max_total_aux_word_delta,
        math.ceil(baseline_aux_words * cfg.max_total_aux_word_delta_ratio),
    )


def _phase_gate_failures(
    *,
    complete: list[VideoComparison],
    full_set_complete: bool,
    hard_line_non_regression: bool,
    slide_count_gate_pass: bool,
    line_count_gate_pass: bool,
    fast_transition_gate_pass: bool,
    aux_word_gate_pass: bool,
    target_line_gate_pass: bool,
    reference_lyrics_gate_pass: bool,
    thresholds: PhaseGateThresholds,
    expected_count: int,
    discovered_count: int,
    processed_count: int,
    complete_count: int,
    baseline_hard: int,
    phase_hard: int,
    baseline_slides: int,
    phase_slides: int,
    baseline_lines: int,
    phase_lines: int,
    baseline_fast_transitions: int,
    phase_fast_transitions: int,
    phase_fast_transition_ratio: float,
    baseline_aux_words: int,
    phase_aux_words: int,
    phase_aux_word_ratio: float,
    phase_over_target_ratio: float,
) -> tuple[str, ...]:
    failures: list[str] = []
    if not full_set_complete:
        failures.append(
            "full set incomplete: "
            f"expected {expected_count}, discovered {discovered_count}, "
            f"processed {processed_count}, complete {complete_count}"
        )
    if not hard_line_non_regression:
        failures.append(
            "hard-limit line regression: "
            f"baseline {baseline_hard}, phase {phase_hard}"
        )
    if not slide_count_gate_pass:
        failures.append(
            "total slide count ratio "
            f"{_safe_ratio(phase_slides, baseline_slides):.2f} exceeds "
            f"{thresholds.max_total_slide_ratio:.2f} "
            f"({baseline_slides} -> {phase_slides})"
        )
        failures.extend(
            _top_metric_ratio_failures(
                complete,
                field="slide_count",
                label="slide count",
                ratio=thresholds.max_video_slide_ratio,
                delta=thresholds.max_video_slide_delta,
            )
        )
    if not line_count_gate_pass:
        failures.append(
            "total line count ratio "
            f"{_safe_ratio(phase_lines, baseline_lines):.2f} exceeds "
            f"{thresholds.max_total_line_ratio:.2f} "
            f"({baseline_lines} -> {phase_lines})"
        )
        failures.extend(
            _top_metric_ratio_failures(
                complete,
                field="line_count",
                label="line count",
                ratio=thresholds.max_video_line_ratio,
                delta=thresholds.max_video_line_delta,
            )
        )
    if not fast_transition_gate_pass:
        failures.append(
            "fast transition regression: "
            f"baseline {baseline_fast_transitions}, phase {phase_fast_transitions}; "
            f"phase ratio {phase_fast_transition_ratio:.1%} exceeds "
            f"{thresholds.max_phase_fast_transition_ratio:.1%} or delta exceeds "
            f"{thresholds.max_total_fast_transition_delta}"
        )
        failures.extend(_top_fast_transition_failures(complete, thresholds))
    if not aux_word_gate_pass:
        failures.append(
            "auxiliary word regression: "
            f"baseline {baseline_aux_words}, phase {phase_aux_words}, "
            f"delta {phase_aux_words - baseline_aux_words} "
            f"(allowed {_allowed_aux_word_delta(baseline_aux_words, thresholds)}); "
            f"phase ratio {phase_aux_word_ratio:.1%} "
            f"(limit {thresholds.max_phase_aux_word_ratio:.1%})"
        )
    if not target_line_gate_pass:
        failures.append(
            "over-target line ratio gate failed: "
            f"total phase ratio {phase_over_target_ratio:.1%}, "
            f"limit {thresholds.max_phase_over_target_line_ratio:.1%}"
        )
        failures.extend(_top_target_line_failures(complete, thresholds))
    if not reference_lyrics_gate_pass:
        failures.append(
            "reference lyrics gate failed: phase output diverged from one or "
            "more expected lyric files"
        )
        failures.extend(_top_reference_lyric_failures(complete, thresholds))
    return tuple(failures)


def _top_metric_ratio_failures(
    comparisons: list[VideoComparison],
    *,
    field: str,
    label: str,
    ratio: float,
    delta: int,
) -> list[str]:
    failures: list[tuple[float, str]] = []
    for comparison in comparisons:
        if comparison.baseline_best is None or comparison.phase_output is None:
            continue
        baseline = int(getattr(comparison.baseline_best, field))
        phase = int(getattr(comparison.phase_output, field))
        metric_ratio = _safe_ratio(phase, baseline)
        if not _within_relative_metric_limit(
            baseline=baseline,
            phase=phase,
            ratio=ratio,
            delta=delta,
        ):
            failures.append(
                (
                    metric_ratio,
                    f"video `{comparison.video_id}` {label} ratio "
                    f"{metric_ratio:.2f} exceeds {ratio:.2f} "
                    f"or +{delta} allowance ({baseline} -> {phase})",
                )
            )
    return [message for _, message in sorted(failures, reverse=True)[:5]]


def _top_fast_transition_failures(
    comparisons: list[VideoComparison],
    thresholds: PhaseGateThresholds,
) -> list[str]:
    failures: list[tuple[float, str]] = []
    for comparison in comparisons:
        if comparison.phase_output is None:
            continue
        transitions = max(0, comparison.phase_output.slide_count - 1)
        ratio = _safe_ratio(comparison.phase_output.fast_transitions, transitions)
        if ratio > thresholds.max_phase_fast_transition_ratio:
            failures.append(
                (
                    ratio,
                    f"video `{comparison.video_id}` fast transition ratio "
                    f"{ratio:.1%} exceeds "
                    f"{thresholds.max_phase_fast_transition_ratio:.1%}",
                )
            )
    return [message for _, message in sorted(failures, reverse=True)[:5]]


def _top_target_line_failures(
    comparisons: list[VideoComparison],
    thresholds: PhaseGateThresholds,
) -> list[str]:
    failures: list[tuple[float, str]] = []
    for comparison in comparisons:
        if comparison.phase_output is None:
            continue
        ratio = _safe_ratio(
            comparison.phase_output.over_target,
            comparison.phase_output.line_count,
        )
        if ratio > thresholds.max_phase_over_target_line_ratio:
            failures.append(
                (
                    ratio,
                    f"video `{comparison.video_id}` over-target line ratio "
                    f"{ratio:.1%} exceeds "
                    f"{thresholds.max_phase_over_target_line_ratio:.1%}",
                )
            )
    return [message for _, message in sorted(failures, reverse=True)[:5]]


def _top_reference_lyric_failures(
    comparisons: list[VideoComparison],
    thresholds: PhaseGateThresholds,
) -> list[str]:
    failures: list[tuple[float, str]] = []
    for comparison in comparisons:
        phase = comparison.phase_reference
        if phase is None:
            continue
        reasons: list[str] = []
        if phase.word_similarity < thresholds.min_reference_word_similarity:
            reasons.append(
                f"similarity {phase.word_similarity:.3f} below "
                f"{thresholds.min_reference_word_similarity:.3f}"
            )
        if comparison.baseline_reference is not None:
            drop = comparison.baseline_reference.word_similarity - phase.word_similarity
            if drop > thresholds.max_reference_similarity_drop:
                reasons.append(
                    f"dropped {drop:.3f} from baseline "
                    f"{comparison.baseline_reference.word_similarity:.3f}"
                )
        if reasons:
            failures.append(
                (
                    1.0 - phase.word_similarity,
                    f"video `{comparison.video_id}` reference lyrics failed: "
                    + "; ".join(reasons),
                )
            )
    return [message for _, message in sorted(failures, reverse=True)[:5]]


def format_phase_gate_report(
    summary: dict[str, object],
    comparisons: list[VideoComparison],
) -> str:
    lines = [
        "# Consensus Phase Gate Report",
        "",
        f"Phase: {summary['phase']}",
        f"Mode: {summary['mode']}",
        "Gate rule: run the complete set, preserve old-process outputs, and compare phase output against that baseline.",
        "",
        "## Summary",
        "",
        f"- Expected videos: {summary['expected_count']}",
        f"- Discovered videos: {summary['discovered_count']}",
        f"- Processed videos: {summary['processed_count']}",
        f"- Complete comparisons: {summary['complete_comparisons']}",
        f"- Full set complete: {summary['full_set_complete']}",
        f"- Baseline hard-limit lines: {summary['baseline_total_hard_lines']}",
        f"- Phase hard-limit lines: {summary['phase_total_hard_lines']}",
        f"- Hard-line delta: {summary['hard_line_delta']}",
        f"- Phase gate pass: {summary['phase_gate_pass']}",
        "",
        "## Gate Checks",
        "",
        f"- Hard-line gate pass: {summary['hard_line_non_regression']}",
        f"- Slide-count gate pass: {summary['slide_count_gate_pass']} "
        f"({summary['baseline_total_slides']} -> {summary['phase_total_slides']}, "
        f"ratio {summary['slide_count_ratio']})",
        f"- Line-count gate pass: {summary['line_count_gate_pass']} "
        f"({summary['baseline_total_lines']} -> {summary['phase_total_lines']}, "
        f"ratio {summary['line_count_ratio']})",
        f"- Fast-transition gate pass: {summary['fast_transition_gate_pass']} "
        f"({summary['baseline_total_fast_transitions']} -> "
        f"{summary['phase_total_fast_transitions']}, "
        f"phase ratio {float(summary['phase_fast_transition_ratio']):.1%})",
        f"- Auxiliary-word gate pass: {summary['aux_word_gate_pass']} "
        f"({summary['baseline_total_aux_words']} -> "
        f"{summary['phase_total_aux_words']}, "
        f"phase ratio {float(summary['phase_aux_word_ratio']):.1%})",
        f"- Target-line gate pass: {summary['target_line_gate_pass']} "
        f"({summary['baseline_total_over_target_lines']} -> "
        f"{summary['phase_total_over_target_lines']}, "
        f"phase ratio {float(summary['phase_over_target_line_ratio']):.1%})",
        f"- Reference-lyrics gate pass: {summary['reference_lyrics_gate_pass']} "
        f"({summary['reference_lyrics_count']} reference file(s), "
        f"min phase similarity {_optional_metric(summary['min_phase_reference_word_similarity'])})",
        "",
        "## Gate Failures",
        "",
    ]
    failures = list(summary.get("gate_failures", []))
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("None.")
    lines.extend(
        [
        "",
        "## Effort",
        "",
        f"- Total per-video elapsed: {_format_seconds(float(summary['total_video_elapsed_seconds']))}",
        f"- Average per-video elapsed: {_format_seconds(float(summary['average_video_elapsed_seconds']))}",
        f"- Cache growth: {_format_bytes(int(summary['cache_growth_bytes']))}",
        f"- Phase output size: {_format_bytes(int(summary['phase_output_total_bytes']))}",
        "- Per-source candidate timing is not captured yet; this report measures each video-level phase execution.",
        "",
        "## Per Video",
        "",
        "| Video | Complete | Elapsed | Baseline hard | Phase hard | Delta hard | Baseline slides | Phase slides | Phase fast | Phase aux | Phase ref sim | Cache delta | Error |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for comparison in comparisons:
        delta = _delta_dict(comparison.baseline_best, comparison.phase_output)
        lines.append(
            "| "
            f"`{comparison.video_id}` | {comparison.complete} | "
            f"{_format_seconds(comparison.elapsed_seconds)} | "
            f"{_metric(comparison.baseline_best, 'over_hard')} | "
            f"{_metric(comparison.phase_output, 'over_hard')} | "
            f"{delta.get('over_hard', '-')} | "
            f"{_metric(comparison.baseline_best, 'slide_count')} | "
            f"{_metric(comparison.phase_output, 'slide_count')} | "
            f"{_metric(comparison.phase_output, 'fast_transitions')} | "
            f"{_metric(comparison.phase_output, 'aux_words')} | "
            f"{_reference_similarity_metric(comparison.phase_reference)} | "
            f"{_format_bytes(_byte_delta(comparison.cache_bytes_before, comparison.cache_bytes_after))} | "
            f"{_escape_pipe(comparison.error or '-')} |"
        )
    reference_comparisons = [
        comparison for comparison in comparisons if comparison.reference_lyrics_path
    ]
    if reference_comparisons:
        lines.extend(
            [
                "",
                "## Expected Reference Lyrics By Video (Not Generated)",
                "",
                "These lyrics are evaluation-only and were not used to generate any output.",
                "",
            ]
        )
        for comparison in reference_comparisons:
            lines.extend(
                [
                    f"### {comparison.video_id}",
                    "",
                    f"Title: {comparison.title}",
                    "",
                ]
            )
            lines.extend(
                _reference_content_section(
                    "Expected Reference Lyrics (Not Generated)",
                    comparison.reference_lyrics_path,
                )
            )
    lines.extend(["", "## Output Content By Video", ""])
    for comparison in comparisons:
        lines.extend(
            [
                f"### {comparison.video_id}",
                "",
                f"Title: {comparison.title}",
                "",
            ]
        )
        lines.extend(_archive_content_section("Baseline Best Output", comparison.baseline_best))
        lines.extend(_archive_content_section("Phase Output", comparison.phase_output))
    lines.extend(
        [
            "",
            "## Artifact Layout",
            "",
            "- `baseline-old-process/<video_id>/`: copied old-process `.slja` candidates and `best.slja`.",
            "- `phase-output/<video_id>/best-consensus.slja`: phase output for that video.",
            "- `phase-output/<video_id>/consensus-report.md`: phrase-level source decisions and low-confidence snippets.",
            "- `phase-output/<video_id>/comparison.json` and `.md`: detailed metric comparison.",
        ]
    )
    return "\n".join(lines) + "\n"


def _effort_dict(comparison: VideoComparison) -> dict[str, object]:
    return {
        "started_at": comparison.started_at,
        "finished_at": comparison.finished_at,
        "elapsed_seconds": comparison.elapsed_seconds,
        "elapsed_human": _format_seconds(comparison.elapsed_seconds),
        "cache_bytes_before": comparison.cache_bytes_before,
        "cache_bytes_after": comparison.cache_bytes_after,
        "cache_growth_bytes": _byte_delta(
            comparison.cache_bytes_before,
            comparison.cache_bytes_after,
        ),
        "phase_output_bytes": comparison.phase_output_bytes,
    }


def write_video_comparison(output_dir: Path, comparison: VideoComparison) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "comparison.json").write_text(
        json.dumps(comparison.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    lines = [
        f"# Comparison: {comparison.video_id}",
        "",
        f"Title: {comparison.title}",
        f"Complete: {comparison.complete}",
        "",
        "| Metric | Baseline best | Phase output | Delta |",
        "|---|---:|---:|---:|",
    ]
    delta = _delta_dict(comparison.baseline_best, comparison.phase_output)
    for field in (
        "slide_count",
        "over_hard",
        "over_target",
        "aux_words",
        "fast_transitions",
        "text_words",
        "median_line_chars",
    ):
        lines.append(
            "| "
            f"{field} | {_metric(comparison.baseline_best, field)} | "
            f"{_metric(comparison.phase_output, field)} | "
            f"{delta.get(field, '-')} |"
        )
    if comparison.error:
        lines.extend(["", "## Error", "", comparison.error])
    if comparison.reference_lyrics_path:
        lines.extend(
            [
                "",
                "## Reference Lyrics Gate",
                "",
                f"- Reference file: `{comparison.reference_lyrics_path}`",
                f"- Baseline similarity: {_reference_similarity_metric(comparison.baseline_reference)}",
                f"- Phase similarity: {_reference_similarity_metric(comparison.phase_reference)}",
            ]
        )
    effort = _effort_dict(comparison)
    lines.extend(
        [
            "",
            "## Effort",
            "",
            f"- Started at: {effort['started_at'] or '-'}",
            f"- Finished at: {effort['finished_at'] or '-'}",
            f"- Elapsed: {_format_seconds(comparison.elapsed_seconds)}",
            f"- Cache before: {_format_bytes(comparison.cache_bytes_before)}",
            f"- Cache after: {_format_bytes(comparison.cache_bytes_after)}",
            f"- Cache delta: {_format_bytes(_byte_delta(comparison.cache_bytes_before, comparison.cache_bytes_after))}",
            f"- Phase output size: {_format_bytes(comparison.phase_output_bytes)}",
        ]
    )
    lines.extend(["", "## Old Process Candidates", ""])
    if not comparison.baseline_candidates:
        lines.append("No copied candidate archives found.")
    else:
        lines.extend(
            [
                "| Candidate | Slides | Hard | Over target | Aux words | Fast transitions |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for name, metrics in sorted(comparison.baseline_candidates.items()):
            lines.append(
                "| "
                f"`{name}` | {metrics.slide_count} | {metrics.over_hard} | "
                f"{metrics.over_target}/{metrics.line_count} | {metrics.aux_words} | "
                f"{metrics.fast_transitions} |"
            )
    lines.extend(["", "## Expected Reference Lyrics Content (Not Generated)", ""])
    lines.extend(_reference_content_body(comparison.reference_lyrics_path))
    lines.extend(["", "## Baseline Best Content", ""])
    lines.extend(_archive_content_body(comparison.baseline_best))
    lines.extend(["", "## Phase Output Content", ""])
    lines.extend(_archive_content_body(comparison.phase_output))
    if comparison.baseline_candidates:
        lines.extend(["", "## Old Process Candidate Content", ""])
        for name, metrics in sorted(comparison.baseline_candidates.items()):
            lines.extend([f"### {name}", ""])
            lines.extend(_archive_content_body(metrics))
    (output_dir / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _slides_from_result(result: Any) -> list[Slide]:
    from louvorja_slides.slja import extract_lyric_slides

    return extract_lyric_slides(result.document)


def _slide_tokens(slide: Slide) -> list[str]:
    texts = list(slide.lines)
    if slide.aux_text and not _REPETITION_MARKER_RE.match(slide.aux_text.strip()):
        texts.append(slide.aux_text)
    return [
        token
        for text in texts
        for token in re.findall(r"\S+", text)
        if any(character.isalnum() for character in token)
    ]


def _slide_text(slides: Iterable[Slide]) -> str:
    parts: list[str] = []
    for slide in slides:
        parts.extend(slide.lines)
        if slide.aux_text and not _REPETITION_MARKER_RE.match(slide.aux_text.strip()):
            parts.append(slide.aux_text)
    return " ".join(parts).strip()


def _archive_content_section(
    label: str,
    metrics: ArchiveMetrics | None,
) -> list[str]:
    lines = [f"#### {label}", ""]
    lines.extend(_archive_content_body(metrics))
    return lines


def _reference_content_section(
    label: str,
    path_text: str,
) -> list[str]:
    lines = [f"#### {label}", ""]
    lines.extend(_reference_content_body(path_text))
    return lines


def _reference_content_body(path_text: str) -> list[str]:
    if not path_text:
        return ["No reference lyrics configured for this video.", ""]
    path = Path(path_text)
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return [f"Reference text unavailable: {_one_line(str(exc))}", ""]
    return [
        "This text is evaluation-only and was not used to generate the output.",
        "",
        "```text",
        text,
        "```",
        "",
    ]


def _archive_content_body(metrics: ArchiveMetrics | None) -> list[str]:
    if metrics is None:
        return ["Archive unavailable.", ""]
    archive_path = Path(metrics.path)
    try:
        archive = read_slja(archive_path)
    except (OSError, ValueError) as exc:
        return [f"Archive text unavailable: {_one_line(str(exc))}", ""]
    return [
        "##### Transcription",
        "",
        "```text",
        _slide_text(archive.slides),
        "```",
        "",
        "##### Slide Mapping",
        "",
        "```text",
        _slide_mapping_text(archive.slides),
        "```",
        "",
    ]


def _reference_similarity_metric(metrics: LyricReferenceMetrics | None) -> object:
    return "-" if metrics is None else f"{metrics.word_similarity:.3f}"


def _optional_metric(value: object) -> object:
    return "-" if value is None else value


def _slide_mapping_text(slides: Iterable[Slide]) -> str:
    slide_blocks: list[str] = []
    for slide in slides:
        slide_lines = [line.strip() for line in slide.lines if line.strip()]
        if slide.aux_text and slide.aux_text.strip():
            slide_lines.append(slide.aux_text.strip())
        slide_blocks.append("\n".join(slide_lines))
    return "\n\n".join(slide_blocks)


def _text_word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _normalized_words(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip().split()


def _word_edit_distance(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_word in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_word in enumerate(right, start=1):
            current.append(
                min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + (left_word != right_word),
                )
            )
        previous = current
    return previous[-1]


def _slug(text: str) -> str:
    words = _normalized_words(text)
    return "-".join(words)[:80] or "untitled"


def _delta_dict(
    baseline: ArchiveMetrics | None,
    phase: ArchiveMetrics | None,
) -> dict[str, object]:
    if baseline is None or phase is None:
        return {}
    fields = (
        "slide_count",
        "line_count",
        "over_hard",
        "over_target",
        "aux_words",
        "fast_transitions",
        "text_words",
        "median_line_chars",
    )
    return {
        field: round(float(getattr(phase, field)) - float(getattr(baseline, field)), 3)
        for field in fields
    }


def _metric(metrics: ArchiveMetrics | None, field: str) -> object:
    if metrics is None:
        return "-"
    value = getattr(metrics, field)
    if isinstance(value, float):
        return round(value, 3)
    return value


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _escape_pipe(text: str) -> str:
    return text.replace("|", "\\|")


def _byte_delta(before: int | None, after: int | None) -> int | None:
    if before is None or after is None:
        return None
    return after - before


def _format_seconds(seconds: float | int | None) -> str:
    if seconds is None:
        return "-"
    whole_seconds = max(0, int(round(float(seconds))))
    minutes, remaining_seconds = divmod(whole_seconds, 60)
    hours, remaining_minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{remaining_minutes:02d}m{remaining_seconds:02d}s"
    return f"{remaining_minutes}m{remaining_seconds:02d}s"


def _format_bytes(size: int | None) -> str:
    if size is None:
        return "-"
    units = ("B", "KiB", "MiB", "GiB")
    value = float(size)
    unit = units[0]
    for unit in units:
        if abs(value) < 1024.0 or unit == units[-1]:
            break
        value /= 1024.0
    if unit == "B":
        return f"{int(value)} {unit}"
    return f"{value:.1f} {unit}"


def _tree_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


if __name__ == "__main__":
    raise SystemExit(main())
