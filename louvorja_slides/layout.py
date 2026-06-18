from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class LayoutConfig:
    target_max_chars_per_line: int = 28
    hard_max_chars_per_line: int = 34
    max_lines_per_slide: int = 2
    min_slide_duration: float = 4.0
    min_transition_gap: float = 3.0
    phrase_pause_seconds: float = 0.60
    auxiliary_max_chars: int = 28
    auxiliary_max_words: int = 3
    allow_auxiliary: bool = True
    weak_break_words: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "a",
                "o",
                "as",
                "os",
                "um",
                "uma",
                "de",
                "do",
                "da",
                "dos",
                "das",
                "em",
                "no",
                "na",
                "nos",
                "nas",
                "e",
                "que",
                "nao",
                "não",
            }
        )
    )


@dataclass(frozen=True)
class LyricWord:
    text: str
    start: float
    end: float
    line_index: int | None = None
    section_index: int | None = None


@dataclass(frozen=True)
class SlidePlan:
    lines: tuple[str, ...]
    start_seconds: float
    end_seconds: float
    aux_text: str = ""


@dataclass(frozen=True)
class _LayoutCandidate:
    lines: tuple[str, ...]
    aux_text: str
    score: float
    overlong: bool = False


def plan_lyric_slides(
    words: Iterable[Any],
    config: LayoutConfig | None = None,
) -> list[SlidePlan]:
    cfg = config or LayoutConfig()
    lyric_words = [_coerce_word(word) for word in words]
    lyric_words = [word for word in lyric_words if word.text]
    if not lyric_words:
        raise ValueError("no lyric words to layout")

    slides: list[SlidePlan] = []
    index = 0
    while index < len(lyric_words):
        strong_boundary = _first_strong_boundary(lyric_words, index, cfg)
        if strong_boundary is not None:
            candidate = _layout_segment(lyric_words[index : strong_boundary + 1], cfg)
            if candidate is not None and not candidate.overlong:
                slides.append(
                    _slide_from_candidate(
                        lyric_words[index : strong_boundary + 1],
                        candidate,
                    )
                )
                index = strong_boundary + 1
                continue

        end, candidate = _longest_layout(lyric_words, index, cfg)
        segment = lyric_words[index : end + 1]
        slides.append(_slide_from_candidate(segment, candidate))
        index = end + 1

    return collapse_repeated_slides(slides)


def collapse_repeated_slides(slides: Iterable[SlidePlan]) -> list[SlidePlan]:
    slide_list = list(slides)
    collapsed: list[SlidePlan] = []
    index = 0

    while index < len(slide_list):
        current = slide_list[index]
        if current.aux_text:
            collapsed.append(current)
            index += 1
            continue

        repeat_count = 1
        repeat_end_seconds = current.end_seconds
        next_index = index + 1
        while next_index < len(slide_list):
            next_slide = slide_list[next_index]
            if next_slide.aux_text or next_slide.lines != current.lines:
                break
            repeat_count += 1
            repeat_end_seconds = next_slide.end_seconds
            next_index += 1

        if repeat_count == 1:
            collapsed.append(current)
        else:
            collapsed.append(
                SlidePlan(
                    lines=current.lines,
                    start_seconds=current.start_seconds,
                    end_seconds=repeat_end_seconds,
                    aux_text=f"({repeat_count}x)",
                )
            )
        index = next_index

    return collapsed


def _coerce_word(word: Any) -> LyricWord:
    if isinstance(word, LyricWord):
        return word

    text = getattr(word, "text", None)
    timestamp = getattr(word, "timestamp", None)
    if text is None or timestamp is None:
        raise ValueError("word text and timestamp are required")

    start = getattr(timestamp, "start", None)
    end = getattr(timestamp, "end", None)
    if start is None or end is None:
        raise ValueError("word timestamp start/end are required")

    return LyricWord(text=str(text).strip(), start=float(start), end=float(end))


def _first_strong_boundary(
    words: list[LyricWord],
    start: int,
    cfg: LayoutConfig,
) -> int | None:
    for index in range(start, len(words) - 1):
        if _section_boundary_after(words, index):
            return index
        if words[index + 1].start - words[index].end >= cfg.min_transition_gap:
            return index
    return None


def _longest_layout(
    words: list[LyricWord],
    start: int,
    cfg: LayoutConfig,
) -> tuple[int, _LayoutCandidate]:
    viable: list[tuple[int, _LayoutCandidate]] = []
    has_source_lines = _has_source_line_hints(words[start:])
    has_musical_boundaries = _has_musical_boundaries(words, start, cfg)
    for end in range(start, len(words)):
        segment = words[start : end + 1]
        if has_source_lines:
            if end < len(words) - 1 and not _source_boundary_after(words, end):
                continue
            if _source_line_count(segment) > cfg.max_lines_per_slide:
                continue
        elif (
            has_musical_boundaries
            and end < len(words) - 1
            and not _musical_boundary_after(words, end, cfg)
        ):
            continue
        candidate = _layout_segment(segment, cfg)
        if candidate is not None:
            viable.append((end, candidate))

    if viable:
        non_overlong = [item for item in viable if not item[1].overlong]
        candidates = non_overlong
        if not candidates and (has_source_lines or has_musical_boundaries):
            candidates = _relaxed_non_overlong_layouts(words, start, cfg)
        candidates = candidates or viable

        duration_ok = [
            item
            for item in candidates
            if _duration_ok(words, start, item[0], cfg)
        ]
        candidates = duration_ok or candidates
        best_bucket = min(
            _candidate_bucket(words, start, end, candidate, cfg)
            for end, candidate in candidates
        )
        bucketed = [
            (end, candidate)
            for end, candidate in candidates
            if _candidate_bucket(words, start, end, candidate, cfg) == best_bucket
        ]
        return max(bucketed, key=lambda item: (item[0], -item[1].score))

    word = words[start]
    return start, _LayoutCandidate(lines=(word.text,), aux_text="", score=0.0)


def _relaxed_non_overlong_layouts(
    words: list[LyricWord],
    start: int,
    cfg: LayoutConfig,
) -> list[tuple[int, _LayoutCandidate]]:
    viable: list[tuple[int, _LayoutCandidate]] = []
    max_fittable_chars = _max_fittable_segment_chars(cfg)
    for end in range(start, len(words)):
        if len(_join(words[start : end + 1])) > max_fittable_chars:
            break
        candidate = _layout_segment(words[start : end + 1], cfg)
        if candidate is not None and not candidate.overlong:
            viable.append((end, candidate))
    return viable


def _max_fittable_segment_chars(cfg: LayoutConfig) -> int:
    main_text_chars = cfg.hard_max_chars_per_line * cfg.max_lines_per_slide
    main_text_chars += max(0, cfg.max_lines_per_slide - 1)
    if not cfg.allow_auxiliary:
        return main_text_chars
    return main_text_chars + 1 + cfg.auxiliary_max_chars


def _candidate_bucket(
    words: list[LyricWord],
    start: int,
    end: int,
    candidate: _LayoutCandidate,
    cfg: LayoutConfig,
) -> int:
    if candidate.aux_text:
        line_bucket = 3
    elif all(len(line) <= cfg.target_max_chars_per_line for line in candidate.lines):
        line_bucket = 0
    else:
        line_bucket = 1
    boundary_bucket = 0 if _is_natural_segment_end(words, start, end, cfg) else 2
    return boundary_bucket + line_bucket


def _is_natural_segment_end(
    words: list[LyricWord],
    start: int,
    end: int,
    cfg: LayoutConfig,
) -> bool:
    if end == len(words) - 1:
        return True
    if _source_boundary_after(words, end):
        return True
    if _ends_sentence(words[end].text):
        return True
    if words[end + 1].start - words[end].end >= cfg.phrase_pause_seconds:
        return True
    if _is_weak_break_word(words[end].text, cfg):
        return False
    return words[end].end - words[start].start >= cfg.min_slide_duration * 2


def _duration_ok(words: list[LyricWord], start: int, end: int, cfg: LayoutConfig) -> bool:
    if end == len(words) - 1:
        return True
    current_duration = words[end].end - words[start].start
    tail_duration = words[-1].end - words[end + 1].start
    return current_duration >= cfg.min_slide_duration and tail_duration >= cfg.min_slide_duration


def _layout_segment(words: list[LyricWord], cfg: LayoutConfig) -> _LayoutCandidate | None:
    full_text = _join(words)
    if len(words) == 1:
        return _LayoutCandidate(lines=(full_text,), aux_text="", score=_line_score(words, cfg))

    candidates: list[_LayoutCandidate] = []
    if (
        len(full_text) <= cfg.hard_max_chars_per_line
        and _source_line_count(words) <= 1
    ):
        score = _length_over_target(len(full_text), cfg)
        if len(full_text) <= cfg.target_max_chars_per_line:
            score -= 12.0
        candidates.append(
            _LayoutCandidate(
                lines=(full_text,),
                aux_text="",
                score=score,
            )
        )

    natural_splits = _natural_split_indices(words, cfg)
    if cfg.max_lines_per_slide >= 2:
        natural_split_set = set(natural_splits)

        def add_two_line_candidates(split_indices: Iterable[int]) -> int:
            added = 0
            for split_index in split_indices:
                first = words[: split_index + 1]
                second = words[split_index + 1 :]
                if not first or not second:
                    continue
                first_text = _join(first)
                second_text = _join(second)
                if len(first_text) > cfg.hard_max_chars_per_line:
                    continue
                if len(second_text) > cfg.hard_max_chars_per_line:
                    continue
                candidates.append(
                    _LayoutCandidate(
                        lines=(first_text, second_text),
                        aux_text="",
                        score=_split_score(first, second, cfg),
                    )
                )
                added += 1
            return added

        added_from_natural = add_two_line_candidates(natural_splits)
        if (
            cfg.allow_auxiliary
            and len(natural_splits) >= 2
            and added_from_natural == 0
        ):
            aux_candidate = _auxiliary_layout(words, natural_splits, cfg)
            if aux_candidate is not None:
                candidates.append(aux_candidate)

        if not natural_splits:
            add_two_line_candidates(range(0, len(words) - 1))
        elif added_from_natural == 0 and not candidates:
            add_two_line_candidates(
                split_index
                for split_index in range(0, len(words) - 1)
                if split_index not in natural_split_set
            )

    if cfg.allow_auxiliary and cfg.max_lines_per_slide >= 2 and not candidates:
        aux_candidate = _auxiliary_layout(words, natural_splits, cfg)
        if aux_candidate is not None:
            candidates.append(aux_candidate)

    if not candidates:
        return _overlong_layout(words, cfg)

    return min(candidates, key=lambda candidate: candidate.score)


def _auxiliary_layout(
    words: list[LyricWord],
    natural_splits: list[int],
    cfg: LayoutConfig,
) -> _LayoutCandidate | None:
    split_pairs: list[tuple[int, int]] = []
    if natural_splits:
        split_pairs = [
            (first, second)
            for second in natural_splits
            for first in range(0, second)
        ]
    else:
        split_pairs = [
            (first, second)
            for first in range(0, len(words) - 2)
            for second in range(first + 1, len(words) - 1)
        ]

    candidates: list[_LayoutCandidate] = []
    for first_split, second_split in split_pairs:
        first = words[: first_split + 1]
        second = words[first_split + 1 : second_split + 1]
        aux = words[second_split + 1 :]
        if not first or not second or not aux:
            continue
        first_text = _join(first)
        second_text = _join(second)
        aux_text = _join(aux)
        if len(first_text) > cfg.hard_max_chars_per_line:
            continue
        if len(second_text) > cfg.hard_max_chars_per_line:
            continue
        if len(aux_text) > cfg.auxiliary_max_chars:
            continue
        if len(aux) > cfg.auxiliary_max_words:
            continue
        candidates.append(
            _LayoutCandidate(
                lines=(first_text, second_text),
                aux_text=aux_text,
                score=_split_score(first, second, cfg) + 40.0 + len(aux_text) * 0.1,
            )
        )

    if not candidates:
        return None
    return min(candidates, key=lambda candidate: candidate.score)


def _overlong_layout(words: list[LyricWord], cfg: LayoutConfig) -> _LayoutCandidate:
    full_text = _join(words)
    if cfg.max_lines_per_slide < 2 or len(words) == 1:
        return _LayoutCandidate(
            lines=(full_text,),
            aux_text="",
            score=1000.0 + _length_over_target(len(full_text), cfg),
            overlong=True,
        )

    candidates: list[_LayoutCandidate] = []
    for split_index in range(0, len(words) - 1):
        first = words[: split_index + 1]
        second = words[split_index + 1 :]
        first_text = _join(first)
        second_text = _join(second)
        longest_line = max(len(first_text), len(second_text))
        score = 1000.0 + longest_line * 2.0
        score += abs(len(first_text) - len(second_text)) * 0.2
        score += _line_score(first, cfg)
        candidates.append(
            _LayoutCandidate(
                lines=(first_text, second_text),
                aux_text="",
                score=score,
                overlong=True,
            )
        )
    return min(candidates, key=lambda candidate: candidate.score)


def _natural_split_indices(words: list[LyricWord], cfg: LayoutConfig) -> list[int]:
    result: list[int] = []
    for index in range(0, len(words) - 1):
        if _musical_boundary_after(words, index, cfg):
            result.append(index)
    return result


def _has_musical_boundaries(
    words: list[LyricWord],
    start: int,
    cfg: LayoutConfig,
) -> bool:
    return any(
        _musical_boundary_after(words, index, cfg)
        for index in range(start, len(words) - 1)
    )


def _musical_boundary_after(
    words: list[LyricWord],
    index: int,
    cfg: LayoutConfig,
) -> bool:
    if _source_boundary_after(words, index):
        return True
    if _ends_sentence(words[index].text):
        return True
    return words[index + 1].start - words[index].end >= cfg.phrase_pause_seconds


def _slide_from_candidate(words: list[LyricWord], candidate: _LayoutCandidate) -> SlidePlan:
    return SlidePlan(
        lines=candidate.lines,
        start_seconds=words[0].start,
        end_seconds=words[-1].end,
        aux_text=candidate.aux_text,
    )


def _split_score(first: list[LyricWord], second: list[LyricWord], cfg: LayoutConfig) -> float:
    first_text = _join(first)
    second_text = _join(second)
    score = abs(len(first_text) - len(second_text)) * 0.2
    score += _length_over_target(len(first_text), cfg)
    score += _length_over_target(len(second_text), cfg)
    score += _line_score(first, cfg)
    if _is_weak_break_word(first[-1].text, cfg):
        score += 25.0
    if _section_boundary_between(first[-1], second[0]):
        score -= 10.0
    elif _line_boundary_between(first[-1], second[0]):
        score -= 7.0
    if _ends_sentence(first[-1].text):
        score -= 8.0
    elif second[0].start - first[-1].end >= cfg.phrase_pause_seconds:
        score -= 6.0
    return score


def _line_score(words: list[LyricWord], cfg: LayoutConfig) -> float:
    if not words:
        return 0.0
    return 10.0 if _is_weak_break_word(words[-1].text, cfg) else 0.0


def _length_over_target(length: int, cfg: LayoutConfig) -> float:
    return max(0, length - cfg.target_max_chars_per_line) * 2.0


def _is_weak_break_word(text: str, cfg: LayoutConfig) -> bool:
    return _normalize_word(text) in cfg.weak_break_words


def _ends_sentence(text: str) -> bool:
    return text.rstrip().endswith((".", ",", ";", ":", "!", "?", "..."))


def _source_boundary_after(words: list[LyricWord], index: int) -> bool:
    return _section_boundary_after(words, index) or _line_boundary_after(words, index)


def _section_boundary_after(words: list[LyricWord], index: int) -> bool:
    return _section_boundary_between(words[index], words[index + 1])


def _line_boundary_after(words: list[LyricWord], index: int) -> bool:
    return _line_boundary_between(words[index], words[index + 1])


def _section_boundary_between(left: LyricWord, right: LyricWord) -> bool:
    return (
        left.section_index is not None
        and right.section_index is not None
        and left.section_index != right.section_index
    )


def _line_boundary_between(left: LyricWord, right: LyricWord) -> bool:
    return (
        left.line_index is not None
        and right.line_index is not None
        and left.line_index != right.line_index
    )


def _has_source_line_hints(words: list[LyricWord]) -> bool:
    return any(word.line_index is not None for word in words)


def _source_line_count(words: list[LyricWord]) -> int:
    hinted = {word.line_index for word in words if word.line_index is not None}
    return len(hinted) if hinted else 0


def _normalize_word(text: str) -> str:
    return text.strip().strip(".,;:!?()[]{}").lower()


def _join(words: list[LyricWord]) -> str:
    return " ".join(word.text for word in words)
