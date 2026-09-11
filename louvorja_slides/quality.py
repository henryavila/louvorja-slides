from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from typing import Iterable, TextIO

from louvorja_slides.slja import Slide
from louvorja_slides.transcription import Transcript

_REPETITION_MARKER_RE = re.compile(r"^\(\d+x\)$", re.IGNORECASE)


class QualityViolation(RuntimeError):
    """Raised when generated slides fail the configured quality gate."""


@dataclass(frozen=True)
class QualityThresholds:
    max_aux_word_ratio: float = 0.10
    max_aux_slide_ratio: float = 0.35
    target_max_chars_per_line: int = 28
    hard_max_chars_per_line: int = 34
    max_line_over_target_ratio: float = 0.30
    max_median_line_chars: float = 28.0
    max_empty_slide_count: int = 0
    max_hard_line_count: int = 0
    min_slide_transition_seconds: float = 3.0
    max_fast_transition_ratio: float = 0.05
    max_zero_duration_word_ratio: float = 0.02
    min_positive_gap_ratio: float = 0.05
    min_gap_seconds: float = 0.05
    min_lyrics_alignment_coverage: float = 0.80


@dataclass(frozen=True)
class SlideQualityReport:
    slide_count: int
    empty_slide_count: int
    main_word_count: int
    auxiliary_word_count: int
    auxiliary_slide_count: int
    line_count: int
    over_target_line_count: int
    over_hard_line_count: int
    transition_count: int
    fast_transition_count: int
    median_line_chars: float
    messages: tuple[str, ...] = field(default_factory=tuple)

    @property
    def acceptable(self) -> bool:
        return not self.messages

    @property
    def auxiliary_word_ratio(self) -> float:
        total = self.main_word_count + self.auxiliary_word_count
        return self.auxiliary_word_count / total if total else 0.0

    @property
    def auxiliary_slide_ratio(self) -> float:
        return self.auxiliary_slide_count / self.slide_count if self.slide_count else 0.0

    @property
    def line_over_target_ratio(self) -> float:
        return self.over_target_line_count / self.line_count if self.line_count else 0.0

    @property
    def fast_transition_ratio(self) -> float:
        return self.fast_transition_count / self.transition_count if self.transition_count else 0.0


@dataclass(frozen=True)
class TranscriptQualityReport:
    word_count: int
    zero_duration_word_count: int
    boundary_count: int
    positive_gap_count: int
    messages: tuple[str, ...] = field(default_factory=tuple)

    @property
    def acceptable(self) -> bool:
        return not self.messages

    @property
    def zero_duration_word_ratio(self) -> float:
        return self.zero_duration_word_count / self.word_count if self.word_count else 0.0

    @property
    def positive_gap_ratio(self) -> float:
        return self.positive_gap_count / self.boundary_count if self.boundary_count else 1.0


@dataclass(frozen=True)
class LyricsAlignmentQualityReport:
    lyric_word_count: int
    alignable_lyric_word_count: int
    matched_word_count: int
    coverage: float
    unmatched_lyric_spans: tuple[str, ...] = field(default_factory=tuple)
    unmatched_asr_spans: tuple[str, ...] = field(default_factory=tuple)
    messages: tuple[str, ...] = field(default_factory=tuple)

    @property
    def acceptable(self) -> bool:
        return not self.messages


def analyze_slide_quality(
    slides: Iterable[Slide],
    thresholds: QualityThresholds | None = None,
) -> SlideQualityReport:
    cfg = thresholds or QualityThresholds()
    slide_list = list(slides)
    lines = [line for slide in slide_list for line in slide.lines]
    line_lengths = sorted(len(line) for line in lines)
    median_line_chars = _median(line_lengths)
    transitions = [
        current.start_seconds - previous.start_seconds
        for previous, current in zip(slide_list, slide_list[1:])
    ]

    main_word_count = sum(_word_count(line) for line in lines)
    lyric_aux_texts = [
        slide.aux_text
        for slide in slide_list
        if slide.aux_text and not _is_repetition_marker(slide.aux_text)
    ]
    auxiliary_word_count = sum(_word_count(text) for text in lyric_aux_texts)
    empty_slide_count = sum(1 for slide in slide_list if not any(slide.lines))
    over_target_line_count = sum(
        1 for line in lines if len(line) > cfg.target_max_chars_per_line
    )
    over_hard_line_count = sum(1 for line in lines if len(line) > cfg.hard_max_chars_per_line)
    fast_transition_count = sum(
        1 for transition in transitions if transition < cfg.min_slide_transition_seconds
    )

    report = SlideQualityReport(
        slide_count=len(slide_list),
        empty_slide_count=empty_slide_count,
        main_word_count=main_word_count,
        auxiliary_word_count=auxiliary_word_count,
        auxiliary_slide_count=len(lyric_aux_texts),
        line_count=len(lines),
        over_target_line_count=over_target_line_count,
        over_hard_line_count=over_hard_line_count,
        transition_count=len(transitions),
        fast_transition_count=fast_transition_count,
        median_line_chars=median_line_chars,
    )

    messages: list[str] = []
    if report.slide_count == 0:
        messages.append("no lyric slides were generated")
    if report.empty_slide_count > cfg.max_empty_slide_count:
        messages.append(
            f"empty lyric slide count {report.empty_slide_count} exceeds "
            f"{cfg.max_empty_slide_count}"
        )
    if report.auxiliary_word_ratio > cfg.max_aux_word_ratio:
        messages.append(
            "auxiliary lyric word ratio "
            f"{report.auxiliary_word_ratio:.1%} exceeds {cfg.max_aux_word_ratio:.1%}"
        )
    if report.auxiliary_slide_ratio > cfg.max_aux_slide_ratio:
        messages.append(
            "auxiliary lyric slide ratio "
            f"{report.auxiliary_slide_ratio:.1%} exceeds {cfg.max_aux_slide_ratio:.1%}"
        )
    if report.line_over_target_ratio > cfg.max_line_over_target_ratio:
        messages.append(
            "main line over target ratio "
            f"{report.line_over_target_ratio:.1%} exceeds {cfg.max_line_over_target_ratio:.1%}"
        )
    if report.over_hard_line_count > cfg.max_hard_line_count:
        messages.append(
            f"main lines over hard limit {report.over_hard_line_count} exceeds "
            f"{cfg.max_hard_line_count}"
        )
    if report.median_line_chars > cfg.max_median_line_chars:
        messages.append(
            "median main line length "
            f"{report.median_line_chars:.1f} exceeds {cfg.max_median_line_chars:.1f}"
        )
    if report.fast_transition_ratio > cfg.max_fast_transition_ratio:
        messages.append(
            "fast slide transition ratio "
            f"{report.fast_transition_ratio:.1%} exceeds "
            f"{cfg.max_fast_transition_ratio:.1%}"
        )

    return SlideQualityReport(
        slide_count=report.slide_count,
        empty_slide_count=report.empty_slide_count,
        main_word_count=report.main_word_count,
        auxiliary_word_count=report.auxiliary_word_count,
        auxiliary_slide_count=report.auxiliary_slide_count,
        line_count=report.line_count,
        over_target_line_count=report.over_target_line_count,
        over_hard_line_count=report.over_hard_line_count,
        transition_count=report.transition_count,
        fast_transition_count=report.fast_transition_count,
        median_line_chars=report.median_line_chars,
        messages=tuple(messages),
    )


def analyze_transcript_quality(
    transcript: Transcript,
    thresholds: QualityThresholds | None = None,
) -> TranscriptQualityReport:
    cfg = thresholds or QualityThresholds()
    words = transcript.words
    boundary_count = max(len(words) - 1, 0)
    zero_duration_word_count = sum(1 for word in words if word.end <= word.start)
    positive_gap_count = sum(
        1
        for previous, current in zip(words, words[1:])
        if current.start - previous.end > cfg.min_gap_seconds
    )

    report = TranscriptQualityReport(
        word_count=len(words),
        zero_duration_word_count=zero_duration_word_count,
        boundary_count=boundary_count,
        positive_gap_count=positive_gap_count,
    )

    messages: list[str] = []
    if report.zero_duration_word_ratio > cfg.max_zero_duration_word_ratio:
        messages.append(
            "zero-duration word ratio "
            f"{report.zero_duration_word_ratio:.1%} exceeds {cfg.max_zero_duration_word_ratio:.1%}"
        )
    if report.positive_gap_ratio < cfg.min_positive_gap_ratio:
        messages.append(
            "positive timestamp gap ratio "
            f"{report.positive_gap_ratio:.1%} is below {cfg.min_positive_gap_ratio:.1%}"
        )

    return TranscriptQualityReport(
        word_count=report.word_count,
        zero_duration_word_count=report.zero_duration_word_count,
        boundary_count=report.boundary_count,
        positive_gap_count=report.positive_gap_count,
        messages=tuple(messages),
    )


def analyze_lyrics_alignment_quality(
    alignment_report: object,
    thresholds: QualityThresholds | None = None,
) -> LyricsAlignmentQualityReport:
    cfg = thresholds or QualityThresholds()
    lyric_word_count = int(getattr(alignment_report, "lyric_word_count", 0))
    alignable_lyric_word_count = int(
        getattr(alignment_report, "alignable_lyric_word_count", lyric_word_count)
    )
    matched_word_count = int(getattr(alignment_report, "matched_word_count", 0))
    coverage = float(
        getattr(
            alignment_report,
            "coverage",
            matched_word_count / alignable_lyric_word_count
            if alignable_lyric_word_count
            else 0.0,
        )
    )
    unmatched_lyric_spans = tuple(
        str(item) for item in getattr(alignment_report, "unmatched_lyric_spans", ())
    )
    unmatched_asr_spans = tuple(
        str(item) for item in getattr(alignment_report, "unmatched_asr_spans", ())
    )

    messages: list[str] = []
    if alignable_lyric_word_count == 0:
        messages.append("no alignable lyric words were provided")
    elif coverage < cfg.min_lyrics_alignment_coverage:
        detail = (
            "lyrics alignment coverage "
            f"{coverage:.1%} is below {cfg.min_lyrics_alignment_coverage:.1%}"
        )
        if unmatched_lyric_spans:
            detail += f"; unmatched lyrics: {', '.join(unmatched_lyric_spans[:3])}"
        if unmatched_asr_spans:
            detail += f"; unmatched ASR: {', '.join(unmatched_asr_spans[:3])}"
        messages.append(detail)

    return LyricsAlignmentQualityReport(
        lyric_word_count=lyric_word_count,
        alignable_lyric_word_count=alignable_lyric_word_count,
        matched_word_count=matched_word_count,
        coverage=coverage,
        unmatched_lyric_spans=unmatched_lyric_spans,
        unmatched_asr_spans=unmatched_asr_spans,
        messages=tuple(messages),
    )


def enforce_quality(
    *,
    slides: Iterable[Slide],
    transcript: Transcript | None = None,
    lyrics_alignment: object | None = None,
    mode: str = "fail",
    thresholds: QualityThresholds | None = None,
    stream: TextIO | None = None,
) -> tuple[SlideQualityReport, TranscriptQualityReport | None]:
    if mode not in {"fail", "warn", "off"}:
        raise ValueError("quality gate mode must be fail, warn, or off")

    slide_report = analyze_slide_quality(slides, thresholds)
    transcript_report = (
        analyze_transcript_quality(transcript, thresholds) if transcript is not None else None
    )
    lyrics_alignment_report = (
        analyze_lyrics_alignment_quality(lyrics_alignment, thresholds)
        if lyrics_alignment is not None
        else None
    )
    reports: list[tuple[str, tuple[str, ...]]] = [("slides", slide_report.messages)]
    if transcript_report is not None:
        reports.append(("transcript", transcript_report.messages))
    if lyrics_alignment_report is not None:
        reports.append(("lyrics", lyrics_alignment_report.messages))

    messages = [
        f"{name}: {message}"
        for name, report_messages in reports
        for message in report_messages
    ]
    if not messages or mode == "off":
        return slide_report, transcript_report

    text = _format_failure(messages)
    if mode == "fail":
        raise QualityViolation(text)

    output = stream or sys.stderr
    print(text, file=output)
    return slide_report, transcript_report


def _format_failure(messages: list[str]) -> str:
    details = "\n".join(f"- {message}" for message in messages)
    return (
        "quality gate failed:\n"
        f"{details}\n"
        "Run again with --quality-gate warn to write the archive anyway, "
        "or --quality-gate off to disable this check."
    )


def _word_count(text: str) -> int:
    return len(text.split())


def _is_repetition_marker(text: str) -> bool:
    return bool(_REPETITION_MARKER_RE.match(text.strip()))


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    midpoint = len(values) // 2
    if len(values) % 2:
        return float(values[midpoint])
    return (values[midpoint - 1] + values[midpoint]) / 2
