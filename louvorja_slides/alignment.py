from __future__ import annotations

import unicodedata
from collections import defaultdict
from typing import Any, Callable, Iterable, Mapping

import numpy as np

from louvorja_slides.transcription import Transcript, TranscribedWord


class AlignmentUnavailableError(RuntimeError):
    pass


class AlignmentError(RuntimeError):
    pass


RunForcedAlign = Callable[[np.ndarray, list[TranscribedWord], str], list[Mapping[str, Any]]]


def sanitize_for_mms(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in normalized if "a" <= ch <= "z")


def refine_words_from_spans(
    words: Iterable[TranscribedWord],
    spans: Iterable[Mapping[str, Any]],
    *,
    frame_seconds: float = 0.02,
) -> list[TranscribedWord]:
    word_list = list(words)
    spans_by_word: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for span in spans:
        spans_by_word[int(span["word_idx"])].append(span)

    refined: list[TranscribedWord] = []
    for index, word in enumerate(word_list):
        word_spans = spans_by_word.get(index)
        if not word_spans:
            refined.append(word)
            continue
        start_frame = min(int(span["start_frame"]) for span in word_spans)
        end_frame = max(int(span["end_frame"]) for span in word_spans)
        refined.append(
            TranscribedWord(
                text=word.text,
                start=round(start_frame * frame_seconds, 6),
                end=round((end_frame + 1) * frame_seconds, 6),
                confidence=word.confidence,
                source="mms_align",
            )
        )
    return refined


class MmsForcedAligner:
    def __init__(
        self,
        *,
        run_forced_align: RunForcedAlign | None = None,
        frame_seconds: float = 0.02,
    ) -> None:
        self._run_forced_align = run_forced_align
        self.frame_seconds = frame_seconds

    def align_transcript(
        self,
        transcript: Transcript,
        *,
        samples: np.ndarray,
        language: str,
    ) -> Transcript:
        alignable_indices = [
            index for index, word in enumerate(transcript.words) if sanitize_for_mms(word.text)
        ]
        if not alignable_indices:
            return transcript

        spans = self._run_alignment(samples, transcript.words, language)
        if not spans:
            raise AlignmentError("no alignment spans for alignable lyrics; bypass with --alignment none")

        refined = refine_words_from_spans(
            transcript.words,
            spans,
            frame_seconds=self.frame_seconds,
        )
        missing = [
            index
            for index in alignable_indices
            if refined[index].source != "mms_align"
        ]
        if missing:
            raise AlignmentError(
                "partial MMS alignment left alignable words without spans; bypass with --alignment none"
            )

        return Transcript(
            words=refined,
            detected_language=transcript.detected_language,
            duration_seconds=transcript.duration_seconds,
        )

    def _run_alignment(
        self,
        samples: np.ndarray,
        words: list[TranscribedWord],
        language: str,
    ) -> list[Mapping[str, Any]]:
        if self._run_forced_align is not None:
            return list(self._run_forced_align(samples, words, language))
        raise AlignmentUnavailableError(
            "MMS forced alignment backend is deferred for the ML phase; run with --alignment none "
            "or inject an aligner in tests."
        )
