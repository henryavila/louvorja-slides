from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from types import SimpleNamespace

from louvorja_slides.transcription import Transcript, TranscribedWord

LYRICS_ALIGNMENT_REVISION = 1

_BRACKET_TOKEN_RE = re.compile(r"^\s*[\[\(][^\[\]\(\)]*[\]\)]\s*$")
_FUZZY_MATCH_THRESHOLD = 0.82
_ASR_FILLER_TOKENS = frozenset(
    {
        "ah",
        "eh",
        "hm",
        "hmm",
        "hum",
        "oh",
        "uh",
        "um",
        "music",
        "musica",
        "applause",
        "aplausos",
    }
)


@dataclass(frozen=True)
class LyricToken:
    text: str
    normalized: str
    line_index: int
    section_index: int
    token_index: int


@dataclass(frozen=True)
class LyricLine:
    text: str
    tokens: tuple[LyricToken, ...]
    line_index: int
    section_index: int


@dataclass(frozen=True)
class ParsedLyrics:
    lines: tuple[LyricLine, ...]

    @property
    def tokens(self) -> tuple[LyricToken, ...]:
        return tuple(token for line in self.lines for token in line.tokens)


@dataclass(frozen=True)
class LyricsAlignmentReport:
    lyric_word_count: int
    alignable_lyric_word_count: int
    matched_word_count: int
    skipped_asr_word_count: int
    unmatched_asr_word_count: int
    unmatched_lyric_spans: tuple[str, ...] = field(default_factory=tuple)
    unmatched_asr_spans: tuple[str, ...] = field(default_factory=tuple)

    @property
    def coverage(self) -> float:
        if self.alignable_lyric_word_count == 0:
            return 0.0
        return self.matched_word_count / self.alignable_lyric_word_count

    def to_dict(self) -> dict[str, object]:
        return {
            "lyric_word_count": self.lyric_word_count,
            "alignable_lyric_word_count": self.alignable_lyric_word_count,
            "matched_word_count": self.matched_word_count,
            "skipped_asr_word_count": self.skipped_asr_word_count,
            "unmatched_asr_word_count": self.unmatched_asr_word_count,
            "unmatched_lyric_spans": list(self.unmatched_lyric_spans),
            "unmatched_asr_spans": list(self.unmatched_asr_spans),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "LyricsAlignmentReport":
        return cls(
            lyric_word_count=int(data["lyric_word_count"]),
            alignable_lyric_word_count=int(data["alignable_lyric_word_count"]),
            matched_word_count=int(data["matched_word_count"]),
            skipped_asr_word_count=int(data["skipped_asr_word_count"]),
            unmatched_asr_word_count=int(data["unmatched_asr_word_count"]),
            unmatched_lyric_spans=tuple(
                str(item) for item in data.get("unmatched_lyric_spans", [])
            ),
            unmatched_asr_spans=tuple(
                str(item) for item in data.get("unmatched_asr_spans", [])
            ),
        )


@dataclass(frozen=True)
class LyricsAlignmentResult:
    transcript: Transcript
    report: LyricsAlignmentReport

    def to_dict(self) -> dict[str, object]:
        return {
            "transcript": self.transcript.to_dict(),
            "report": self.report.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "LyricsAlignmentResult":
        transcript_data = data.get("transcript")
        report_data = data.get("report")
        if not isinstance(transcript_data, dict):
            raise ValueError("lyrics alignment cache transcript must be an object")
        if not isinstance(report_data, dict):
            raise ValueError("lyrics alignment cache report must be an object")
        return cls(
            transcript=Transcript.from_dict(transcript_data),
            report=LyricsAlignmentReport.from_dict(report_data),
        )


@dataclass(frozen=True)
class _AsrItem:
    normalized: str
    word: TranscribedWord
    original_index: int


def parse_lyrics(text: str) -> ParsedLyrics:
    lines: list[LyricLine] = []
    section_index = 0
    line_index = 0
    token_index = 0
    section_has_content = False

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            if section_has_content:
                section_index += 1
                section_has_content = False
            continue

        tokens: list[LyricToken] = []
        for part in stripped.split():
            token = LyricToken(
                text=part,
                normalized=normalize_token(part),
                line_index=line_index,
                section_index=section_index,
                token_index=token_index,
            )
            tokens.append(token)
            token_index += 1

        lines.append(
            LyricLine(
                text=" ".join(token.text for token in tokens),
                tokens=tuple(tokens),
                line_index=line_index,
                section_index=section_index,
            )
        )
        line_index += 1
        section_has_content = True

    parsed = ParsedLyrics(lines=tuple(lines))
    if not parsed.tokens:
        raise ValueError("lyrics text has no lyric words")
    return parsed


def normalize_token(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    without_marks = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    return "".join(character for character in without_marks if character.isalnum())


def align_lyrics_to_transcript(
    transcript: Transcript,
    lyrics: ParsedLyrics,
) -> LyricsAlignmentResult:
    tokens = lyrics.tokens
    asr_items, skipped_asr_word_count = _asr_items(transcript.words)
    matches, unmatched_asr_indices = _align_token_indices(tokens, asr_items)
    aligned_words = _build_aligned_words(
        tokens=tokens,
        matches=matches,
        asr_items=asr_items,
        duration_seconds=transcript.duration_seconds,
    )
    aligned_transcript = Transcript(
        words=aligned_words,
        detected_language=transcript.detected_language,
        duration_seconds=transcript.duration_seconds,
    )

    unmatched_lyric_indices = [
        index
        for index, token in enumerate(tokens)
        if token.normalized and matches[index] is None
    ]
    matched_word_count = sum(
        1
        for index, token in enumerate(tokens)
        if token.normalized and matches[index] is not None
    )
    alignable_lyric_word_count = sum(1 for token in tokens if token.normalized)
    unmatched_asr_items = [asr_items[index] for index in sorted(unmatched_asr_indices)]
    report = LyricsAlignmentReport(
        lyric_word_count=len(tokens),
        alignable_lyric_word_count=alignable_lyric_word_count,
        matched_word_count=matched_word_count,
        skipped_asr_word_count=skipped_asr_word_count,
        unmatched_asr_word_count=len(unmatched_asr_items),
        unmatched_lyric_spans=_compact_lyric_spans(tokens, unmatched_lyric_indices),
        unmatched_asr_spans=_compact_asr_spans(unmatched_asr_items),
    )
    return LyricsAlignmentResult(transcript=aligned_transcript, report=report)


def transcript_to_lyrics_document(
    transcript: Transcript,
    lyrics: ParsedLyrics,
    *,
    title: str | None = None,
) -> SimpleNamespace:
    tokens = lyrics.tokens
    if len(transcript.words) != len(tokens):
        raise ValueError("lyrics transcript word count does not match parsed lyrics")

    sections: list[SimpleNamespace] = []
    current_section_index: int | None = None
    current_lines: list[SimpleNamespace] = []
    cursor = 0

    def flush_section() -> None:
        if not current_lines:
            return
        starts = [
            alignment.timestamp.start
            for line in current_lines
            for alignment in line.word_alignments
        ]
        ends = [
            alignment.timestamp.end
            for line in current_lines
            for alignment in line.word_alignments
        ]
        sections.append(
            SimpleNamespace(
                timestamp=SimpleNamespace(start=min(starts), end=max(ends)),
                lines=list(current_lines),
            )
        )

    for lyric_line in lyrics.lines:
        if (
            current_section_index is not None
            and lyric_line.section_index != current_section_index
        ):
            flush_section()
            current_lines = []
        current_section_index = lyric_line.section_index

        line_words = transcript.words[cursor : cursor + len(lyric_line.tokens)]
        cursor += len(lyric_line.tokens)
        current_lines.append(
            SimpleNamespace(
                line_type="lyric",
                text=lyric_line.text,
                source_line_index=lyric_line.line_index,
                source_section_index=lyric_line.section_index,
                word_alignments=[
                    SimpleNamespace(
                        text=word.text,
                        timestamp=SimpleNamespace(start=word.start, end=word.end),
                    )
                    for word in line_words
                ],
            )
        )

    flush_section()
    return SimpleNamespace(
        metadata=SimpleNamespace(title=title, artist=None),
        transcript=transcript,
        sections=sections,
    )


def _asr_items(words: list[TranscribedWord]) -> tuple[list[_AsrItem], int]:
    items: list[_AsrItem] = []
    skipped = 0
    for index, word in enumerate(words):
        normalized = normalize_token(word.text)
        if _is_ignorable_asr_word(word.text, normalized):
            skipped += 1
            continue
        items.append(_AsrItem(normalized=normalized, word=word, original_index=index))
    return items, skipped


def _is_ignorable_asr_word(text: str, normalized: str) -> bool:
    if not normalized:
        return True
    if normalized in _ASR_FILLER_TOKENS:
        return True
    return bool(_BRACKET_TOKEN_RE.match(text.strip()))


def _align_token_indices(
    tokens: tuple[LyricToken, ...],
    asr_items: list[_AsrItem],
) -> tuple[list[int | None], set[int]]:
    token_count = len(tokens)
    asr_count = len(asr_items)
    scores: list[list[tuple[float, int, int] | None]] = [
        [None for _ in range(asr_count + 1)] for _ in range(token_count + 1)
    ]
    back: list[list[tuple[int, int, str] | None]] = [
        [None for _ in range(asr_count + 1)] for _ in range(token_count + 1)
    ]
    scores[0][0] = (0.0, 0, 0)

    def update(
        next_i: int,
        next_j: int,
        candidate: tuple[float, int, int],
        previous_i: int,
        previous_j: int,
        action: str,
    ) -> None:
        existing = scores[next_i][next_j]
        if existing is None or candidate > existing:
            scores[next_i][next_j] = candidate
            back[next_i][next_j] = (previous_i, previous_j, action)

    for i in range(token_count + 1):
        for j in range(asr_count + 1):
            state = scores[i][j]
            if state is None:
                continue
            score, matches, tie_breaker = state
            if i < token_count:
                update(
                    i + 1,
                    j,
                    (score - 1.0, matches, tie_breaker - 1),
                    i,
                    j,
                    "skip_lyric",
                )
            if j < asr_count:
                update(
                    i,
                    j + 1,
                    (score - 0.7, matches, tie_breaker - 1),
                    i,
                    j,
                    "skip_asr",
                )
            if i < token_count and j < asr_count:
                similarity = _token_similarity(tokens[i].normalized, asr_items[j].normalized)
                if similarity >= _FUZZY_MATCH_THRESHOLD:
                    exact_bonus = 1.0 if similarity == 1.0 else 0.0
                    update(
                        i + 1,
                        j + 1,
                        (
                            score + 2.0 + similarity + exact_bonus,
                            matches + 1,
                            tie_breaker + 2,
                        ),
                        i,
                        j,
                        "match",
                    )

    matches: list[int | None] = [None] * token_count
    unmatched_asr_indices: set[int] = set()
    i = token_count
    j = asr_count
    while i > 0 or j > 0:
        previous = back[i][j]
        if previous is None:
            break
        previous_i, previous_j, action = previous
        if action == "match":
            matches[previous_i] = previous_j
        elif action == "skip_asr":
            unmatched_asr_indices.add(previous_j)
        i, j = previous_i, previous_j

    return matches, unmatched_asr_indices


def _token_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if min(len(left), len(right)) <= 2:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _build_aligned_words(
    *,
    tokens: tuple[LyricToken, ...],
    matches: list[int | None],
    asr_items: list[_AsrItem],
    duration_seconds: float,
) -> list[TranscribedWord]:
    words: list[TranscribedWord | None] = [None] * len(tokens)
    for token_index, asr_index in enumerate(matches):
        if asr_index is None:
            continue
        source_word = asr_items[asr_index].word
        words[token_index] = TranscribedWord(
            text=tokens[token_index].text,
            start=source_word.start,
            end=source_word.end,
            confidence=source_word.confidence,
            source="lyrics_anchor",
        )

    index = 0
    while index < len(tokens):
        if words[index] is not None:
            index += 1
            continue
        run_start = index
        while index < len(tokens) and words[index] is None:
            index += 1
        run_end = index
        intervals = _interpolated_intervals(words, run_start, run_end, duration_seconds)
        for offset, (start, end) in enumerate(intervals):
            token = tokens[run_start + offset]
            words[run_start + offset] = TranscribedWord(
                text=token.text,
                start=start,
                end=end,
                confidence=0.0,
                source="lyrics_interpolated",
            )

    return [word for word in words if word is not None]


def _interpolated_intervals(
    words: list[TranscribedWord | None],
    run_start: int,
    run_end: int,
    duration_seconds: float,
) -> list[tuple[float, float]]:
    count = run_end - run_start
    previous_word = next(
        (
            words[index]
            for index in range(run_start - 1, -1, -1)
            if words[index] is not None
        ),
        None,
    )
    next_word = next(
        (words[index] for index in range(run_end, len(words)) if words[index] is not None),
        None,
    )

    if previous_word is not None and next_word is not None:
        start_bound = previous_word.end
        end_bound = next_word.start
    elif previous_word is not None:
        start_bound = previous_word.end
        end_bound = max(duration_seconds, start_bound + count * 0.5)
    elif next_word is not None:
        end_bound = next_word.start
        start_bound = max(0.0, end_bound - count * 0.5)
    else:
        start_bound = 0.0
        end_bound = max(duration_seconds, count * 0.5)

    return _distribute_interval(start_bound, end_bound, count)


def _distribute_interval(
    start_bound: float,
    end_bound: float,
    count: int,
) -> list[tuple[float, float]]:
    if count <= 0:
        return []
    if end_bound <= start_bound:
        return [(start_bound, start_bound) for _ in range(count)]

    slot = (end_bound - start_bound) / (count + 1)
    duration = min(0.4, max(0.02, slot * 0.7))
    intervals: list[tuple[float, float]] = []
    previous_end = start_bound
    for index in range(count):
        center = start_bound + slot * (index + 1)
        start = max(previous_end, center - duration / 2)
        end = min(end_bound, center + duration / 2)
        if end < start:
            end = start
        intervals.append((start, end))
        previous_end = end
    return intervals


def _compact_lyric_spans(
    tokens: tuple[LyricToken, ...],
    indices: list[int],
    *,
    limit: int = 5,
) -> tuple[str, ...]:
    spans: list[str] = []
    for group in _consecutive_groups(indices):
        spans.append(" ".join(tokens[index].text for index in group))
        if len(spans) >= limit:
            break
    return tuple(spans)


def _compact_asr_spans(items: list[_AsrItem], *, limit: int = 5) -> tuple[str, ...]:
    grouped: list[list[_AsrItem]] = []
    for item in sorted(items, key=lambda asr_item: asr_item.original_index):
        if (
            not grouped
            or item.original_index != grouped[-1][-1].original_index + 1
        ):
            grouped.append([item])
        else:
            grouped[-1].append(item)

    spans: list[str] = []
    for group in grouped:
        spans.append(" ".join(item.word.text for item in group))
        if len(spans) >= limit:
            break
    return tuple(spans)


def _consecutive_groups(indices: list[int]) -> list[list[int]]:
    groups: list[list[int]] = []
    for index in sorted(indices):
        if not groups or index != groups[-1][-1] + 1:
            groups.append([index])
        else:
            groups[-1].append(index)
    return groups
