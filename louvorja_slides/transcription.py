from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import numpy as np

_WHISPER_SPECIAL_TOKEN_RE = re.compile(r"^\s*\[[^\[\]]*\]\s*$")


class TranscriptionUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class TranscribedWord:
    text: str
    start: float
    end: float
    confidence: float = 1.0
    source: str = "unknown"

    def __post_init__(self) -> None:
        clean_text = self.text.strip()
        if not clean_text:
            raise ValueError("word text is required")
        if self.start < 0:
            raise ValueError("start must be >= 0")
        if self.end < self.start:
            raise ValueError("end must be >= start")
        object.__setattr__(self, "text", clean_text)
        object.__setattr__(self, "start", float(self.start))
        object.__setattr__(self, "end", float(self.end))
        object.__setattr__(self, "confidence", float(self.confidence))

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "TranscribedWord":
        return cls(
            text=str(data["text"]),
            start=float(data["start"]),
            end=float(data["end"]),
            confidence=float(data.get("confidence", 1.0)),
            source=str(data.get("source", "unknown")),
        )


@dataclass(frozen=True)
class Transcript:
    words: list[TranscribedWord]
    detected_language: str | None
    duration_seconds: float

    def __post_init__(self) -> None:
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be > 0")
        clean_words = sorted(self.words, key=lambda word: (word.start, word.end))
        if not clean_words:
            raise ValueError("no transcribed words")
        object.__setattr__(self, "words", clean_words)
        object.__setattr__(self, "duration_seconds", float(self.duration_seconds))

    def to_dict(self) -> dict[str, object]:
        return {
            "words": [word.to_dict() for word in self.words],
            "detected_language": self.detected_language,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Transcript":
        words = [
            TranscribedWord.from_dict(item)
            for item in data.get("words", [])
            if isinstance(item, dict)
        ]
        detected_language = data.get("detected_language")
        return cls(
            words=words,
            detected_language=str(detected_language) if detected_language is not None else None,
            duration_seconds=float(data["duration_seconds"]),
        )


class LocalWhisperTranscriber:
    def __init__(self, *, model_id: str = "large-v3", model: Any | None = None) -> None:
        self.model_id = model_id
        self._model = model

    @property
    def model(self) -> Any:
        if self._model is None:
            try:
                from pywhispercpp.model import Model
            except ImportError as exc:
                raise TranscriptionUnavailableError(
                    "Whisper transcription requires pywhispercpp; install ML dependencies "
                    "or run a test with an injected transcriber."
                ) from exc
            self._model = Model(self.model_id)
        return self._model

    def transcribe_samples(
        self,
        *,
        samples: np.ndarray,
        sample_rate: int,
        duration_seconds: float,
        language: str,
    ) -> Transcript:
        if sample_rate != 16000:
            raise ValueError("Whisper transcription expects 16000 Hz mono samples")
        segments = self.model.transcribe(
            samples,
            token_timestamps=True,
            max_len=1,
            split_on_word=True,
            entropy_thold=2.2,
            no_speech_thold=0.7,
            language=language,
        )

        words: list[TranscribedWord] = []
        for segment in segments:
            text = _clean_text(getattr(segment, "text", ""))
            if not text or _WHISPER_SPECIAL_TOKEN_RE.match(text):
                continue
            start = float(getattr(segment, "t0", 0.0)) / 100.0
            end = float(getattr(segment, "t1", getattr(segment, "t0", 0.0))) / 100.0
            if end < start:
                end = start
            words.extend(_words_from_segment(text=text, start=start, end=end))

        if not words:
            raise ValueError(
                "local transcription produced no lyric words; try a larger model or inspect the vocal stem"
            )
        return Transcript(
            words=words,
            detected_language=language,
            duration_seconds=duration_seconds,
        )


def _clean_text(text: object) -> str:
    return " ".join(str(text).strip().split())


def _words_from_segment(text: str, start: float, end: float) -> list[TranscribedWord]:
    parts = text.split()
    if len(parts) <= 1:
        return [TranscribedWord(text=text, start=start, end=end, source="whisper")]

    duration = max(0.0, end - start)
    step = duration / len(parts) if duration else 0.0
    result: list[TranscribedWord] = []
    for index, part in enumerate(parts):
        part_start = start + step * index
        part_end = end if index == len(parts) - 1 else start + step * (index + 1)
        result.append(
            TranscribedWord(
                text=part,
                start=round(part_start, 6),
                end=round(part_end, 6),
                source="whisper",
            )
        )
    return result
