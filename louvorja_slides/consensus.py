from __future__ import annotations

import math
import re
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from louvorja_slides.cache import audio_sha256
from louvorja_slides.document import transcript_to_document
from louvorja_slides.engines import AudioToDocumentConfig, AudioToDocumentEngine
from louvorja_slides.layout import LayoutConfig, LyricWord, plan_lyric_slides
from louvorja_slides.quality import SlideQualityReport, analyze_slide_quality
from louvorja_slides.slja import Slide
from louvorja_slides.transcription import Transcript, TranscribedWord

CONSENSUS_PHASE1_SOURCES: tuple[str, ...] = (
    "medium-original",
    "medium-denoise",
    "medium-vocals",
    "turbo-original",
    "turbo-vocals",
)

_PHRASE_PAUSE_SECONDS = 0.60
_MAX_PHRASE_DURATION_SECONDS = 12.0
_MAX_PHRASE_WORDS = 10
_GROUP_MATCH_THRESHOLD = 0.50


@dataclass(frozen=True)
class ConsensusCandidate:
    name: str
    transcript: Transcript


@dataclass(frozen=True)
class UnavailableConsensusSource:
    name: str
    reason: str


@dataclass(frozen=True)
class PhraseCandidate:
    candidate_name: str
    words: tuple[TranscribedWord, ...]
    start: float
    end: float
    text: str
    normalized_text: str
    normalized_tokens: tuple[str, ...]

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def center(self) -> float:
        return (self.start + self.end) / 2.0

    @property
    def word_count(self) -> int:
        return len(self.normalized_tokens)


@dataclass(frozen=True)
class PhraseScore:
    phrase: PhraseCandidate
    score: float
    agreement: float
    support_sources: int
    over_hard_lines: int
    coverage_ratio: float
    temporal_penalty: float
    repetition_penalty: float


@dataclass(frozen=True)
class ConsensusDecision:
    index: int
    start: float
    end: float
    winner: PhraseCandidate
    score: float
    confidence: float
    support_sources: int
    low_confidence: bool
    low_confidence_reason: str
    alternatives: tuple[PhraseScore, ...]


@dataclass(frozen=True)
class ConsensusResult:
    phase: str
    transcript: Transcript
    document: Any
    candidates: tuple[ConsensusCandidate, ...]
    decisions: tuple[ConsensusDecision, ...]
    unavailable_sources: tuple[UnavailableConsensusSource, ...] = ()


@dataclass(frozen=True)
class _CandidateSpec:
    name: str
    whisper_model: str
    vocal_separation: str
    audio_variant: str


_PHASE1_SPECS: tuple[_CandidateSpec, ...] = (
    _CandidateSpec("medium-original", "medium", "none", "original"),
    _CandidateSpec("medium-denoise", "medium", "none", "denoise"),
    _CandidateSpec("medium-vocals", "medium", "htdemucs_ft", "original"),
    _CandidateSpec("turbo-original", "large-v3-turbo", "none", "original"),
    _CandidateSpec("turbo-vocals", "large-v3-turbo", "htdemucs_ft", "original"),
)


def build_phase1_consensus(
    *,
    audio_path: Path,
    engine: AudioToDocumentEngine,
    base_config: AudioToDocumentConfig,
    title: str | None = None,
    youtube_caption_path: Path | None = None,
    run: Any = subprocess.run,
) -> ConsensusResult:
    candidates: list[ConsensusCandidate] = []
    unavailable: list[UnavailableConsensusSource] = []

    with tempfile.TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        audio_variants: dict[str, Path] = {"original": Path(audio_path)}
        for spec in _PHASE1_SPECS:
            try:
                source_audio = _source_audio_for_spec(
                    spec,
                    audio_path=Path(audio_path),
                    base_config=base_config,
                    temp_root=temp_root,
                    audio_variants=audio_variants,
                    run=run,
                )
                candidate = _transcribe_source(
                    spec=spec,
                    audio_path=source_audio,
                    engine=engine,
                    base_config=base_config,
                    title=title,
                )
            except Exception as exc:  # noqa: BLE001 - source failures are reported.
                unavailable.append(UnavailableConsensusSource(spec.name, str(exc)))
                continue
            candidates.append(candidate)

    if youtube_caption_path is not None:
        try:
            candidates.append(
                caption_candidate(
                    "youtube-caption",
                    Path(youtube_caption_path),
                    duration_seconds=_candidate_duration(candidates),
                )
            )
        except Exception as exc:  # noqa: BLE001 - optional source failures are reported.
            unavailable.append(UnavailableConsensusSource("youtube-caption", str(exc)))

    if not candidates:
        details = "; ".join(
            f"{source.name}: {source.reason}" for source in unavailable
        )
        suffix = f": {details}" if details else ""
        raise ValueError(f"consensus produced no usable candidates{suffix}")

    return build_consensus_from_candidates(
        candidates,
        title=title or Path(audio_path).stem,
        language=base_config.language,
        unavailable_sources=unavailable,
        phase="1",
    )


def build_consensus_from_candidates(
    candidates: Iterable[ConsensusCandidate],
    *,
    title: str | None = None,
    language: str | None = "pt",
    unavailable_sources: Iterable[UnavailableConsensusSource] = (),
    phase: str = "1",
    layout_config: LayoutConfig | None = None,
) -> ConsensusResult:
    candidate_list = [candidate for candidate in candidates if candidate.transcript.words]
    phrases = [
        phrase
        for candidate in candidate_list
        for phrase in segment_candidate_phrases(candidate)
        if phrase.word_count > 0
    ]
    if not phrases:
        raise ValueError("consensus requires at least one non-empty candidate transcript")

    cfg = layout_config or LayoutConfig()
    groups = group_phrases(phrases)
    decisions = tuple(
        choose_phrase(group, index=index, layout_config=cfg)
        for index, group in enumerate(groups, start=1)
        if group
    )
    if not decisions:
        raise ValueError("consensus could not align any candidate phrases")

    words = _dedupe_consensus_words(
        _retag_word(word, decision.winner.candidate_name)
        for decision in decisions
        for word in decision.winner.words
    )
    if not words:
        raise ValueError("consensus produced no lyric words")

    duration = max(candidate.transcript.duration_seconds for candidate in candidate_list)
    transcript = Transcript(
        words=words,
        detected_language=language,
        duration_seconds=max(duration, words[-1].end, 1.0),
    )
    return ConsensusResult(
        phase=phase,
        transcript=transcript,
        document=transcript_to_document(transcript, title=title),
        candidates=tuple(candidate_list),
        decisions=decisions,
        unavailable_sources=tuple(unavailable_sources),
    )


def segment_candidate_phrases(candidate: ConsensusCandidate) -> list[PhraseCandidate]:
    words = [word for word in candidate.transcript.words if _has_lyric_text(word.text)]
    if not words:
        return []

    groups: list[list[TranscribedWord]] = [[words[0]]]
    for previous, current in zip(words, words[1:]):
        current_group = groups[-1]
        if _starts_new_phrase(previous, current, current_group):
            groups.append([])
        groups[-1].append(current)

    return [
        _phrase_from_words(candidate.name, tuple(group))
        for group in groups
        if group
    ]


def group_phrases(phrases: Iterable[PhraseCandidate]) -> list[tuple[PhraseCandidate, ...]]:
    groups: list[list[PhraseCandidate]] = []
    for phrase in sorted(phrases, key=lambda item: (item.start, item.end, item.candidate_name)):
        best_group: list[PhraseCandidate] | None = None
        best_affinity = 0.0
        for group in groups:
            if any(item.candidate_name == phrase.candidate_name for item in group):
                continue
            affinity = _group_affinity(group, phrase)
            if affinity > best_affinity:
                best_affinity = affinity
                best_group = group
        if best_group is not None and best_affinity >= _GROUP_MATCH_THRESHOLD:
            best_group.append(phrase)
        else:
            groups.append([phrase])

    return [
        tuple(sorted(group, key=lambda item: (item.start, item.candidate_name)))
        for group in sorted(groups, key=lambda items: _median_float(item.start for item in items))
    ]


def choose_phrase(
    group: Iterable[PhraseCandidate],
    *,
    index: int,
    layout_config: LayoutConfig | None = None,
) -> ConsensusDecision:
    group_list = list(group)
    if not group_list:
        raise ValueError("cannot choose from an empty phrase group")

    cfg = layout_config or LayoutConfig()
    scores = tuple(
        sorted(
            (_score_phrase(phrase, group_list, cfg) for phrase in group_list),
            key=lambda item: (-item.score, item.phrase.candidate_name),
        )
    )
    best = scores[0]
    low_confidence_reason = _low_confidence_reason(best, group_list)
    return ConsensusDecision(
        index=index,
        start=min(phrase.start for phrase in group_list),
        end=max(phrase.end for phrase in group_list),
        winner=best.phrase,
        score=best.score,
        confidence=max(0.0, min(1.0, best.score / 100.0)),
        support_sources=best.support_sources,
        low_confidence=bool(low_confidence_reason),
        low_confidence_reason=low_confidence_reason,
        alternatives=scores,
    )


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    without_punctuation = re.sub(r"[^a-z0-9]+", " ", without_marks)
    return re.sub(r"\s+", " ", without_punctuation).strip()


def text_similarity(left: str | None, right: str | None) -> float:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm or not right_norm:
        return 0.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def caption_candidate(
    name: str,
    path: Path,
    *,
    duration_seconds: float | None = None,
) -> ConsensusCandidate:
    words = parse_vtt_words(path)
    if not words:
        raise ValueError("caption file has no usable Portuguese lyric text")
    duration = max(duration_seconds or 0.0, max(word.end for word in words), 1.0)
    return ConsensusCandidate(
        name=name,
        transcript=Transcript(
            words=[_retag_word(word, name) for word in words],
            detected_language="pt",
            duration_seconds=duration,
        ),
    )


def parse_vtt_words(path: Path) -> list[TranscribedWord]:
    raw_lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    words: list[TranscribedWord] = []
    previous_tokens: list[str] = []
    index = 0
    while index < len(raw_lines):
        line = raw_lines[index].strip()
        if "-->" not in line:
            index += 1
            continue

        start, end = _parse_vtt_time_range(line)
        index += 1
        cue_lines: list[str] = []
        while index < len(raw_lines) and raw_lines[index].strip():
            cue_lines.append(raw_lines[index].strip())
            index += 1

        cue_text = _clean_caption_text(" ".join(cue_lines))
        cue_tokens = cue_text.split()
        new_tokens = _remove_caption_overlap(previous_tokens, cue_tokens)
        previous_tokens = cue_tokens or previous_tokens
        if new_tokens:
            words.append(
                TranscribedWord(
                    text=" ".join(new_tokens),
                    start=start,
                    end=max(start, end),
                    source="youtube-caption",
                )
            )
        index += 1
    return words


def format_consensus_report(
    result: ConsensusResult,
    *,
    slides: Iterable[Slide] | None = None,
    slide_report: SlideQualityReport | None = None,
) -> str:
    slide_list = list(slides) if slides is not None else None
    report = slide_report
    if report is None and slide_list is not None:
        report = analyze_slide_quality(slide_list)

    lines = [
        "# Consensus transcription report",
        "",
        f"Phase: {result.phase}",
        "Scope: automatic sources only; no LLM correction and no manual lyric review.",
        "",
        "## Sources",
        "",
    ]
    for candidate in result.candidates:
        phrase_count = len(segment_candidate_phrases(candidate))
        lines.append(
            f"- `{candidate.name}`: {len(candidate.transcript.words)} words, "
            f"{phrase_count} phrases"
        )
    if result.unavailable_sources:
        lines.extend(["", "## Unavailable Sources", ""])
        for source in result.unavailable_sources:
            lines.append(f"- `{source.name}`: {_one_line(source.reason)}")

    if report is not None:
        lines.extend(
            [
                "",
                "## Layout Metrics",
                "",
                f"- Lyric slides: {report.slide_count}",
                f"- Hard-limit lines: {report.over_hard_line_count}",
                f"- Over-target lines: {report.over_target_line_count}/{report.line_count}",
                f"- Fast transitions: {report.fast_transition_count}/{report.transition_count}",
                f"- Auxiliary words: {report.auxiliary_word_count}",
            ]
        )

    lines.extend(
        [
            "",
            "## Generated Transcription",
            "",
            "```text",
            _transcript_text(result.transcript),
            "```",
        ]
    )

    if slide_list is not None:
        lines.extend(
            [
                "",
                "## Generated Slide Mapping",
                "",
                "```text",
                _slide_mapping_text(slide_list),
                "```",
            ]
        )

    lines.extend(
        [
            "",
            "## Phrase Decisions",
            "",
            "| # | Time | Winner | Score | Support | Low confidence | Snippet |",
            "|---:|---|---|---:|---:|---|---|",
        ]
    )
    for decision in result.decisions:
        low = decision.low_confidence_reason or "-"
        lines.append(
            "| "
            f"{decision.index} | {_format_time(decision.start)}-"
            f"{_format_time(decision.end)} | `{decision.winner.candidate_name}` | "
            f"{decision.score:.1f} | {decision.support_sources} | "
            f"{_escape_pipe(low)} | {_escape_pipe(_safe_excerpt(decision.winner.text))} |"
        )

    low_confidence = [decision for decision in result.decisions if decision.low_confidence]
    lines.extend(["", "## Low Confidence", ""])
    if not low_confidence:
        lines.append("None.")
    else:
        for decision in low_confidence:
            lines.append(
                f"- Phrase {decision.index} at {_format_time(decision.start)}: "
                f"{decision.low_confidence_reason}; "
                f"winner `{decision.winner.candidate_name}`."
            )

    return "\n".join(lines) + "\n"


def _source_audio_for_spec(
    spec: _CandidateSpec,
    *,
    audio_path: Path,
    base_config: AudioToDocumentConfig,
    temp_root: Path,
    audio_variants: dict[str, Path],
    run: Any,
) -> Path:
    if spec.audio_variant == "original":
        return audio_path
    if spec.audio_variant != "denoise":
        raise ValueError(f"unsupported consensus audio variant: {spec.audio_variant}")
    denoise = audio_variants.get("denoise")
    if denoise is not None:
        return denoise
    denoise = _prepare_denoised_audio(
        audio_path,
        cache_root=base_config.cache_root,
        cache=base_config.cache,
        temp_root=temp_root,
        run=run,
    )
    audio_variants["denoise"] = denoise
    return denoise


def _transcribe_source(
    *,
    spec: _CandidateSpec,
    audio_path: Path,
    engine: AudioToDocumentEngine,
    base_config: AudioToDocumentConfig,
    title: str | None,
) -> ConsensusCandidate:
    config = replace(
        base_config,
        title=title,
        whisper_model=spec.whisper_model,
        vocal_separation=spec.vocal_separation,
    )
    doc = engine.transcribe(audio_path, config)
    transcript = getattr(doc, "transcript", None)
    if not isinstance(transcript, Transcript):
        raise ValueError(f"{spec.name} did not return a transcript")
    return ConsensusCandidate(
        name=spec.name,
        transcript=Transcript(
            words=[_retag_word(word, spec.name) for word in transcript.words],
            detected_language=transcript.detected_language,
            duration_seconds=transcript.duration_seconds,
            phonemes=transcript.phonemes,
        ),
    )


def _prepare_denoised_audio(
    audio_path: Path,
    *,
    cache_root: Path,
    cache: bool,
    temp_root: Path,
    run: Any,
) -> Path:
    if cache:
        audio_id = audio_sha256(audio_path)
        output_path = Path(cache_root) / audio_id / "preprocess" / "phase1-denoise.wav"
    else:
        output_path = temp_root / "phase1-denoise.wav"
    if output_path.exists():
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(audio_path),
        "-af",
        "afftdn,dynaudnorm=f=150:g=15",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(output_path),
    ]
    result = run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if getattr(result, "returncode", 1) != 0:
        stderr = str(getattr(result, "stderr", "")).strip()
        raise RuntimeError(stderr or "ffmpeg failed to prepare denoised audio")
    return output_path


def _candidate_duration(candidates: Iterable[ConsensusCandidate]) -> float:
    durations = [candidate.transcript.duration_seconds for candidate in candidates]
    return max(durations) if durations else 1.0


def _starts_new_phrase(
    previous: TranscribedWord,
    current: TranscribedWord,
    current_phrase: list[TranscribedWord],
) -> bool:
    if not current_phrase:
        return False
    gap = current.start - previous.end
    if gap >= _PHRASE_PAUSE_SECONDS:
        return True
    if previous.text.rstrip().endswith((".", ",", ";", ":", "!", "?")):
        return True
    if current_phrase[-1].end - current_phrase[0].start >= _MAX_PHRASE_DURATION_SECONDS:
        return True
    return len(current_phrase) >= _MAX_PHRASE_WORDS


def _phrase_from_words(
    candidate_name: str,
    words: tuple[TranscribedWord, ...],
) -> PhraseCandidate:
    text = " ".join(word.text.strip() for word in words if word.text.strip())
    normalized = normalize_text(text)
    return PhraseCandidate(
        candidate_name=candidate_name,
        words=words,
        start=min(word.start for word in words),
        end=max(word.end for word in words),
        text=text,
        normalized_text=normalized,
        normalized_tokens=tuple(normalized.split()),
    )


def _group_affinity(group: list[PhraseCandidate], phrase: PhraseCandidate) -> float:
    text_score = max(
        text_similarity(phrase.normalized_text, item.normalized_text)
        for item in group
    )
    overlap_score = max(_temporal_overlap_ratio(phrase, item) for item in group)
    center_delta = min(abs(phrase.center - item.center) for item in group)
    if overlap_score >= 0.35:
        return 0.55 + min(0.25, text_score * 0.25)
    if center_delta <= 2.0 and text_score >= 0.20:
        return 0.50 + min(0.25, text_score * 0.25)
    if center_delta <= 8.0 and text_score >= 0.72:
        return 0.50 + min(0.30, text_score * 0.30)
    return max(overlap_score * 0.45, text_score * 0.45)


def _temporal_overlap_ratio(left: PhraseCandidate, right: PhraseCandidate) -> float:
    overlap = min(left.end, right.end) - max(left.start, right.start)
    if overlap <= 0:
        return 0.0
    shorter = max(min(left.duration, right.duration), 0.001)
    return min(1.0, overlap / shorter)


def _score_phrase(
    phrase: PhraseCandidate,
    group: list[PhraseCandidate],
    cfg: LayoutConfig,
) -> PhraseScore:
    others = [item for item in group if item is not phrase]
    similarities = [
        text_similarity(phrase.normalized_text, other.normalized_text)
        for other in others
    ]
    agreement = mean(similarities) if similarities else 0.55
    support_sources = 1 + sum(1 for similarity in similarities if similarity >= 0.62)
    token_counts = [max(item.word_count, 1) for item in group]
    median_words = median(token_counts) if token_counts else 1.0
    coverage_ratio = max(phrase.word_count, 1) / median_words
    coverage_penalty = _coverage_penalty(coverage_ratio)
    centers = [item.center for item in group]
    durations = [item.duration for item in group]
    temporal_penalty = min(abs(phrase.center - median(centers)), 10.0) * 1.5
    temporal_penalty += min(abs(phrase.duration - median(durations)), 8.0)
    over_hard, over_target = _line_overages(phrase, cfg)
    repetition_penalty = _repetition_penalty(phrase.normalized_tokens)

    score = 20.0
    score += 52.0 * agreement
    score += min(support_sources, 3) * 7.0
    score -= coverage_penalty
    score -= temporal_penalty
    score -= over_hard * 30.0
    score -= over_target * 4.0
    score -= repetition_penalty
    score = max(0.0, min(100.0, score))
    return PhraseScore(
        phrase=phrase,
        score=score,
        agreement=agreement,
        support_sources=support_sources,
        over_hard_lines=over_hard,
        coverage_ratio=coverage_ratio,
        temporal_penalty=temporal_penalty,
        repetition_penalty=repetition_penalty,
    )


def _coverage_penalty(ratio: float) -> float:
    if 0.75 <= ratio <= 1.35:
        return abs(ratio - 1.0) * 6.0
    distance = min(abs(math.log(max(ratio, 0.01))), 2.5)
    return 18.0 + distance * 10.0


def _line_overages(phrase: PhraseCandidate, cfg: LayoutConfig) -> tuple[int, int]:
    words = [
        LyricWord(text=word.text, start=word.start, end=word.end)
        for word in phrase.words
    ]
    try:
        plans = plan_lyric_slides(words, cfg)
    except ValueError:
        lines = [phrase.text]
    else:
        lines = [line for plan in plans for line in plan.lines]
    over_hard = sum(1 for line in lines if len(line) > cfg.hard_max_chars_per_line)
    over_target = sum(1 for line in lines if len(line) > cfg.target_max_chars_per_line)
    return over_hard, over_target


def _repetition_penalty(tokens: tuple[str, ...]) -> float:
    if len(tokens) <= 2:
        return 0.0
    duplicate_ratio = 1.0 - (len(set(tokens)) / len(tokens))
    bigrams = list(zip(tokens, tokens[1:]))
    repeated_bigrams = len(bigrams) - len(set(bigrams))
    return duplicate_ratio * 18.0 + repeated_bigrams * 8.0


def _low_confidence_reason(best: PhraseScore, group: list[PhraseCandidate]) -> str:
    if best.score < 55.0:
        return f"score {best.score:.1f} below threshold"
    if len(group) > 1 and best.agreement < 0.42:
        return f"low agreement {best.agreement:.2f}"
    if best.support_sources == 1 and len(group) >= 3:
        return "winner has no close textual support"
    if best.coverage_ratio < 0.60 or best.coverage_ratio > 1.70:
        return f"word-count outlier ratio {best.coverage_ratio:.2f}"
    return ""


def _dedupe_consensus_words(words: Iterable[TranscribedWord]) -> list[TranscribedWord]:
    result: list[TranscribedWord] = []
    for word in sorted(words, key=lambda item: (item.start, item.end)):
        if result:
            previous = result[-1]
            same_text = normalize_text(previous.text) == normalize_text(word.text)
            if same_text and abs(word.start - previous.start) < 0.25:
                continue
        result.append(word)
    return result


def _retag_word(word: TranscribedWord, source: str) -> TranscribedWord:
    return TranscribedWord(
        text=word.text,
        start=word.start,
        end=word.end,
        confidence=word.confidence,
        source=source,
    )


def _has_lyric_text(text: str) -> bool:
    return any(character.isalnum() for character in text)


def _transcript_text(transcript: Transcript) -> str:
    return " ".join(word.text.strip() for word in transcript.words if word.text.strip())


def _slide_mapping_text(slides: Iterable[Slide]) -> str:
    slide_blocks: list[str] = []
    for slide in slides:
        slide_lines = [line.strip() for line in slide.lines if line.strip()]
        if slide.aux_text and slide.aux_text.strip():
            slide_lines.append(slide.aux_text.strip())
        slide_blocks.append("\n".join(slide_lines))
    return "\n\n".join(slide_blocks)


def _median_float(values: Iterable[float]) -> float:
    value_list = list(values)
    return float(median(value_list)) if value_list else 0.0


def _parse_vtt_time_range(line: str) -> tuple[float, float]:
    left, right = line.split("-->", maxsplit=1)
    end_text = right.strip().split()[0]
    return _parse_vtt_timestamp(left.strip()), _parse_vtt_timestamp(end_text)


def _parse_vtt_timestamp(text: str) -> float:
    parts = text.replace(",", ".").split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = "0"
        minutes, seconds = parts
    else:
        return 0.0
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _clean_caption_text(text: str) -> str:
    text = re.sub(r"<\d\d:\d\d:\d\d\.\d+>", " ", text)
    text = re.sub(r"</?c>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _remove_caption_overlap(
    previous_tokens: list[str],
    cue_tokens: list[str],
) -> list[str]:
    if not previous_tokens or not cue_tokens:
        return cue_tokens
    previous_norm = [normalize_text(token) for token in previous_tokens]
    cue_norm = [normalize_text(token) for token in cue_tokens]
    max_overlap = min(len(previous_norm), len(cue_norm))
    for size in range(max_overlap, 0, -1):
        if previous_norm[-size:] == cue_norm[:size]:
            return cue_tokens[size:]
    return cue_tokens


def _format_time(seconds: float) -> str:
    minutes = int(max(0.0, seconds) // 60)
    remainder = int(max(0.0, seconds) % 60)
    return f"{minutes}:{remainder:02d}"


def _safe_excerpt(text: str, max_words: int = 6) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " ..."


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _escape_pipe(text: str) -> str:
    return text.replace("|", "\\|")
