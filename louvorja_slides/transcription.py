from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

_LOGGER = logging.getLogger(__name__)

_WHISPER_SPECIAL_TOKEN_RE = re.compile(r"^\s*\[[^\[\]]*\]\s*$")

# Bump when transcript filtering changes for identical Whisper output.
TRANSCRIPTION_FILTER_REVISION = 2

# Single source of truth for the quality-tuned whisper.cpp arguments. The
# transcript cache key derives from this mapping, so editing a value here
# invalidates stale cached transcripts automatically.
QUALITY_WHISPER_KWARGS: dict[str, object] = {
    "token_timestamps": True,
    "max_len": 1,
    "split_on_word": True,
    "entropy_thold": 2.2,
    "no_speech_thold": 0.7,
}


@dataclass(frozen=True)
class TranscribedWord:
    text: str
    start: float
    end: float
    confidence: float = 1.0
    source: str = "unknown"

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("word text is required")
        if self.start < 0:
            raise ValueError("start must be >= 0")
        if self.end < self.start:
            raise ValueError("end must be >= start")

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
class TranscribedPhoneme:
    symbol: str
    start: float
    end: float
    parent_word_idx: int
    confidence: float = 1.0
    source: str = "unknown"

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("phoneme symbol is required")
        if self.start < 0:
            raise ValueError("start must be >= 0")
        if self.end < self.start:
            raise ValueError("end must be >= start")
        if self.parent_word_idx < 0:
            raise ValueError("parent_word_idx must be >= 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "start": self.start,
            "end": self.end,
            "parent_word_idx": self.parent_word_idx,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "TranscribedPhoneme":
        return cls(
            symbol=str(data["symbol"]),
            start=float(data["start"]),
            end=float(data["end"]),
            parent_word_idx=int(data["parent_word_idx"]),
            confidence=float(data.get("confidence", 1.0)),
            source=str(data.get("source", "unknown")),
        )


@dataclass(frozen=True)
class Transcript:
    words: list[TranscribedWord]
    detected_language: str | None
    duration_seconds: float
    phonemes: list[TranscribedPhoneme] | None = None

    def __post_init__(self) -> None:
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be > 0")
        clean_words = sorted(self.words, key=lambda word: (word.start, word.end))
        if not clean_words:
            raise ValueError("no transcribed words")
        object.__setattr__(self, "words", clean_words)

    def to_dict(self) -> dict[str, object]:
        return {
            "words": [word.to_dict() for word in self.words],
            "detected_language": self.detected_language,
            "duration_seconds": self.duration_seconds,
            "phonemes": (
                [phoneme.to_dict() for phoneme in self.phonemes]
                if self.phonemes is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Transcript":
        raw_words = data.get("words", [])
        if not isinstance(raw_words, list):
            raise ValueError("words must be a list")
        raw_phonemes = data.get("phonemes")
        phonemes = (
            [
                TranscribedPhoneme.from_dict(item)
                for item in raw_phonemes
                if isinstance(item, dict)
            ]
            if isinstance(raw_phonemes, list)
            else None
        )
        return cls(
            words=[
                TranscribedWord.from_dict(item)
                for item in raw_words
                if isinstance(item, dict)
            ],
            detected_language=(
                str(data["detected_language"])
                if data.get("detected_language") is not None
                else None
            ),
            duration_seconds=float(data["duration_seconds"]),
            phonemes=phonemes,
        )


class LocalWhisperTranscriber:
    def __init__(self, model_id: str = "large-v3", model: Any | None = None) -> None:
        self.model_id = model_id
        self._model = model if model is not None else self._load_model(model_id)

    def transcribe_samples(
        self,
        *,
        samples: Any,
        sample_rate: int,
        duration_seconds: float,
        language: str | None = None,
    ) -> Transcript:
        if sample_rate != 16000:
            raise ValueError("LocalWhisperTranscriber requires 16 kHz mono samples")

        kwargs: dict[str, object] = dict(QUALITY_WHISPER_KWARGS)
        if language is not None:
            kwargs["language"] = language

        segments = self._model.transcribe(samples, **kwargs)
        words: list[TranscribedWord] = []
        for segment in segments:
            text = str(getattr(segment, "text", "")).strip()
            if not text or _WHISPER_SPECIAL_TOKEN_RE.match(text) or not _has_lyric_text(text):
                continue

            start = float(getattr(segment, "t0")) / 100.0
            end = float(getattr(segment, "t1")) / 100.0
            if end < start:
                end = start
            words.append(
                TranscribedWord(
                    text=text,
                    start=start,
                    end=end,
                    confidence=1.0,
                    source="whisper",
                )
            )

        return Transcript(
            words=words,
            detected_language=(
                language if language is not None else self._detect_language(samples)
            ),
            duration_seconds=duration_seconds,
        )

    def _detect_language(self, samples: Any) -> str | None:
        detect = getattr(self._model, "auto_detect_language", None)
        if not callable(detect):
            return None
        try:
            (language, _probability), _all_probabilities = detect(samples)
        except Exception as exc:  # noqa: BLE001 - detection must not break transcription
            _LOGGER.warning("whisper language detection failed: %s", exc)
            return None
        return str(language)

    @staticmethod
    def _load_model(model_id: str) -> Any:
        try:
            from pywhispercpp.model import Model
        except ImportError as exc:
            raise RuntimeError(
                "pywhispercpp is not installed. Install local transcription "
                "dependencies before running audio transcription."
            ) from exc
        return Model(model=model_id)


def _has_lyric_text(text: str) -> bool:
    return any(character.isalnum() for character in text)
