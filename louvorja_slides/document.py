from __future__ import annotations

from statistics import median
from types import SimpleNamespace

from louvorja_slides.transcription import Transcript, TranscribedWord

_PHRASE_PAUSE_SECONDS = 0.60
_MAX_PHRASE_DURATION_SECONDS = 12.0
_MAX_PHRASE_WORDS = 8


def transcript_to_document(transcript: Transcript, title: str | None = None) -> SimpleNamespace:
    words = [word for word in transcript.words if _has_lyric_text(word.text)]
    if not words:
        raise ValueError("no lyric words to convert into a document")
    lines = [_line_namespace(line_words) for line_words in _group_words_into_lines(words)]
    return SimpleNamespace(
        metadata=SimpleNamespace(title=title, artist=None),
        transcript=transcript,
        sections=[
            SimpleNamespace(
                timestamp=SimpleNamespace(
                    start=words[0].start,
                    end=words[-1].end,
                ),
                lines=lines,
            )
        ],
    )


def _group_words_into_lines(words: list[TranscribedWord]) -> list[list[TranscribedWord]]:
    if len(words) <= 1:
        return [words]

    gaps = [
        words[index + 1].start - words[index].end
        for index in range(len(words) - 1)
        if words[index + 1].start - words[index].end > 0
    ]
    line_gap = max(2.5 * median(gaps), 1.0) if gaps else 1.0

    grouped: list[list[TranscribedWord]] = [[words[0]]]
    for previous, current in zip(words, words[1:]):
        current_line = grouped[-1]
        if _starts_new_phrase(
            previous,
            current,
            current_line,
            line_gap=line_gap,
        ):
            grouped.append([])
        grouped[-1].append(current)
    return grouped


def _starts_new_phrase(
    previous: TranscribedWord,
    current: TranscribedWord,
    current_line: list[TranscribedWord],
    *,
    line_gap: float,
) -> bool:
    if not current_line:
        return False
    gap = current.start - previous.end
    if gap > line_gap or gap >= _PHRASE_PAUSE_SECONDS:
        return True
    if _ends_phrase(previous.text, len(current_line)):
        return True
    if (
        _looks_like_phrase_start(current.text)
        and _has_enough_phrase_before_capitalized_word(current_line)
        and not _is_weak_continuation(current.text)
    ):
        return True
    if current_line[-1].end - current_line[0].start >= _MAX_PHRASE_DURATION_SECONDS:
        return True
    return len(current_line) >= _MAX_PHRASE_WORDS


def _line_namespace(words: list[TranscribedWord]) -> SimpleNamespace:
    return SimpleNamespace(
        line_type="lyric",
        text=" ".join(word.text for word in words),
        word_alignments=[
            SimpleNamespace(
                text=word.text,
                timestamp=SimpleNamespace(start=word.start, end=word.end),
            )
            for word in words
        ],
    )


def _has_lyric_text(text: str) -> bool:
    return any(character.isalnum() for character in text)


def _ends_phrase(text: str, word_count: int) -> bool:
    stripped = text.rstrip()
    if stripped.endswith((".", "!", "?")):
        return True
    return stripped.endswith((",", ";", ":")) and word_count >= 5


def _looks_like_phrase_start(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped[0].isupper()


def _has_enough_phrase_before_capitalized_word(words: list[TranscribedWord]) -> bool:
    if len(words) >= 3:
        return True
    text = " ".join(word.text for word in words)
    duration = words[-1].end - words[0].start
    return len(text) >= 12 or duration >= 2.0


def _is_weak_continuation(text: str) -> bool:
    return text.strip().casefold() in {
        "a",
        "ao",
        "as",
        "da",
        "de",
        "do",
        "e",
        "em",
        "na",
        "no",
        "o",
        "os",
        "por",
        "pra",
        "para",
        "que",
        "um",
        "uma",
    }
