from __future__ import annotations

from statistics import median
from types import SimpleNamespace

from louvorja_slides.transcription import Transcript, TranscribedWord


def transcript_to_document(transcript: Transcript, *, title: str | None = None) -> SimpleNamespace:
    line_groups = _group_words_into_lines(transcript.words)
    lines = []
    for words in line_groups:
        lines.append(
            SimpleNamespace(
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
        )
    return SimpleNamespace(
        metadata=SimpleNamespace(title=title, artist=None),
        sections=[SimpleNamespace(lines=lines)],
    )


def _group_words_into_lines(words: list[TranscribedWord]) -> list[list[TranscribedWord]]:
    if not words:
        return []
    gaps = [
        words[index + 1].start - words[index].end
        for index in range(len(words) - 1)
        if words[index + 1].start - words[index].end > 0
    ]
    line_gap = max(2.5 * median(gaps), 1.0) if gaps else 1.0

    groups: list[list[TranscribedWord]] = [[words[0]]]
    for previous, current in zip(words, words[1:]):
        if current.start - previous.end > line_gap:
            groups.append([current])
        else:
            groups[-1].append(current)
    return groups
