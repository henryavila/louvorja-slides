from __future__ import annotations

import math
import unicodedata
from collections.abc import Callable, Sequence
from typing import Any

from louvorja_slides.transcription import Transcript, TranscribedPhoneme, TranscribedWord

_SAMPLE_RATE = 16000
_FRAME_SAMPLES = 320
_FRAME_SECONDS = _FRAME_SAMPLES / _SAMPLE_RATE
_CHUNK_WINDOW_SECONDS = 30.0
_CHUNK_CONTEXT_SECONDS = 2.0


class AlignmentError(RuntimeError):
    pass


class AlignmentUnavailableError(AlignmentError):
    pass


def sanitize_for_mms(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(char for char in normalized if char.isascii() and char.isalpha()).lower()


def refine_words_from_spans(
    words: list[TranscribedWord],
    spans: list[dict[str, Any]],
    *,
    frame_seconds: float = 0.02,
) -> list[TranscribedWord]:
    frame_ranges: dict[int, tuple[int, int]] = {}
    for span in spans:
        word_idx = int(span["word_idx"])
        start_frame = int(span["start_frame"])
        end_frame = int(span["end_frame"])
        if word_idx not in frame_ranges:
            frame_ranges[word_idx] = (start_frame, end_frame)
            continue
        low, high = frame_ranges[word_idx]
        frame_ranges[word_idx] = (min(low, start_frame), max(high, end_frame))

    aligned_times = {
        index: (start_frame * frame_seconds, (end_frame + 1) * frame_seconds)
        for index, (start_frame, end_frame) in frame_ranges.items()
    }
    previous_aligned_start: float | None = None
    for index in sorted(aligned_times):
        start = aligned_times[index][0]
        if previous_aligned_start is not None and start < previous_aligned_start:
            raise AlignmentError(
                f"aligned spans are not monotonic at word index {index}; "
                "refusing to build a reordered timeline"
            )
        previous_aligned_start = start

    next_aligned_start: dict[int, float] = {}
    upcoming: float | None = None
    for index in range(len(words) - 1, -1, -1):
        if upcoming is not None:
            next_aligned_start[index] = upcoming
        if index in aligned_times:
            upcoming = aligned_times[index][0]

    refined: list[TranscribedWord] = []
    previous_end = 0.0
    for index, word in enumerate(words):
        if index in aligned_times:
            start, end = aligned_times[index]
            source = "mms_align"
        else:
            # Unalignable words (digits, punctuation-only) keep their original
            # timing clamped between aligned neighbours. Without the clamp the
            # mixed Whisper/MMS timeline reorders words when Transcript sorts
            # by start time, which also corrupts phoneme parent_word_idx.
            start = max(word.start, previous_end)
            end = max(word.end, start)
            upper_bound = next_aligned_start.get(index)
            if upper_bound is not None:
                start = min(start, upper_bound)
                end = min(end, upper_bound)
            source = word.source
        refined.append(
            TranscribedWord(
                text=word.text,
                start=start,
                end=end,
                confidence=word.confidence,
                source=source,
            )
        )
        previous_end = end
    return refined


def refine_transcript_from_spans(
    transcript: Transcript,
    spans: list[dict[str, Any]],
    *,
    frame_seconds: float = 0.02,
) -> Transcript:
    phonemes = [
        TranscribedPhoneme(
            symbol=str(span["text"]),
            start=int(span["start_frame"]) * frame_seconds,
            end=(int(span["end_frame"]) + 1) * frame_seconds,
            parent_word_idx=int(span["word_idx"]),
            confidence=1.0,
            source="mms_align",
        )
        for span in spans
    ]
    return Transcript(
        words=refine_words_from_spans(
            transcript.words,
            spans,
            frame_seconds=frame_seconds,
        ),
        detected_language=transcript.detected_language,
        duration_seconds=transcript.duration_seconds,
        phonemes=phonemes,
    )


def build_mms_targets(
    words: list[TranscribedWord],
    tokenizer: Any,
) -> tuple[list[list[int]], list[int]]:
    sanitized_words = [sanitize_for_mms(word.text) for word in words]
    non_empty_pairs = [
        (index, text) for index, text in enumerate(sanitized_words) if text
    ]
    if not non_empty_pairs:
        return [[] for _ in words], []

    tokens_per_word: list[list[int]] = [[] for _ in words]
    rejected_words: list[tuple[int, str]] = []
    for original_index, text in non_empty_pairs:
        try:
            word_tokens = tokenizer([text])
        except KeyError:
            rejected_words.append((original_index, text))
            continue
        if word_tokens:
            tokens_per_word[original_index] = list(word_tokens[0])

    target_tokens = [token for word_tokens in tokens_per_word for token in word_tokens]
    if not target_tokens and rejected_words:
        preview = ", ".join(f"{index}:{text}" for index, text in rejected_words[:5])
        raise AlignmentError(f"MMS tokenizer rejected all sanitized words: {preview}")

    return tokens_per_word, target_tokens


def collapse_alignment_path(
    alignment_path: list[int],
    blank_id: int,
) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    current_token: int | None = None
    current_start = 0

    for frame_idx, raw_token in enumerate(alignment_path):
        token = int(raw_token)
        if token == blank_id:
            if current_token is not None:
                spans.append(
                    {
                        "_tok": current_token,
                        "start_frame": current_start,
                        "end_frame": frame_idx - 1,
                    }
                )
                current_token = None
            continue
        if token != current_token:
            if current_token is not None:
                spans.append(
                    {
                        "_tok": current_token,
                        "start_frame": current_start,
                        "end_frame": frame_idx - 1,
                    }
                )
            current_token = token
            current_start = frame_idx

    if current_token is not None:
        spans.append(
            {
                "_tok": current_token,
                "start_frame": current_start,
                "end_frame": len(alignment_path) - 1,
            }
        )

    return spans


def attach_spans_to_words(
    spans: list[dict[str, Any]],
    tokens_per_word: list[list[int]],
    tokenizer: Any,
    labels: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    expected_count = sum(len(word_tokens) for word_tokens in tokens_per_word)
    if len(spans) != expected_count:
        raise AlignmentError(
            f"forced alignment produced {len(spans)} token spans for "
            f"{expected_count} target tokens"
        )

    result: list[dict[str, Any]] = []
    token_cursor = 0
    for word_idx, word_tokens in enumerate(tokens_per_word):
        for expected_token in word_tokens:
            span = spans[token_cursor]
            token_id = int(span["_tok"])
            if token_id != int(expected_token):
                raise AlignmentError(
                    f"aligned token {token_id} does not match target token "
                    f"{int(expected_token)} at span {token_cursor}"
                )
            if hasattr(tokenizer, "decode"):
                try:
                    text = tokenizer.decode([token_id])
                except Exception:  # noqa: BLE001
                    text = _label_for_token(token_id, labels)
            else:
                text = _label_for_token(token_id, labels)
            result.append(
                {
                    "text": text,
                    "start_frame": int(span["start_frame"]),
                    "end_frame": int(span["end_frame"]),
                    "word_idx": word_idx,
                }
            )
            token_cursor += 1
    return result


def _label_for_token(token_id: int, labels: Sequence[str] | None) -> str:
    if labels is not None and 0 <= token_id < len(labels):
        label = str(labels[token_id])
        if label:
            return label
    return str(token_id)


def _device_of_model(model: Any) -> str:
    try:
        parameter = next(iter(model.parameters()))
        return str(parameter.device)
    except (AttributeError, StopIteration, TypeError):
        return "cpu"


class MmsForcedAligner:
    def __init__(
        self,
        run_forced_align: Callable[[Any, list[TranscribedWord], str], list[dict[str, Any]]]
        | None = None,
        frame_seconds: float = 0.02,
        model: Any | None = None,
        tokenizer: Any | None = None,
        blank_id: int | None = None,
        labels: Sequence[str] | None = None,
        device: str | None = None,
    ) -> None:
        self._run_forced_align = run_forced_align
        self._frame_seconds = frame_seconds
        self._model = model
        self._tokenizer = tokenizer
        self._blank_id = 0 if blank_id is None else blank_id
        self._labels = labels
        self._requested_device = device
        if device is not None:
            self._device = device
        elif model is not None:
            self._device = _device_of_model(model)
        else:
            self._device = "cpu"

    def align_transcript(
        self,
        transcript: Transcript,
        *,
        samples: Any,
        language: str,
    ) -> Transcript:
        alignable_words = [word for word in transcript.words if sanitize_for_mms(word.text)]
        if not alignable_words:
            return transcript

        spans = self._run(samples, transcript.words, language)
        if not spans:
            raise AlignmentError("no alignment spans returned for alignable words")

        return refine_transcript_from_spans(
            transcript,
            spans,
            frame_seconds=self._frame_seconds,
        )

    def _run(
        self,
        samples: Any,
        words: list[TranscribedWord],
        language: str,
    ) -> list[dict[str, Any]]:
        if self._run_forced_align is not None:
            return self._run_forced_align(samples, words, language)
        return self._run_real_forced_align(samples, words, language)

    def generate_emissions(
        self,
        waveform_1d: Any,
        *,
        window_seconds: float = _CHUNK_WINDOW_SECONDS,
        context_seconds: float = _CHUNK_CONTEXT_SECONDS,
        batch_size: int = 1,
    ) -> Any:
        import torch

        if self._model is None:
            self._load_bundle()

        n_samples = int(waveform_1d.size(0))
        window_samples = int(window_seconds * _SAMPLE_RATE)
        context_samples = int(context_seconds * _SAMPLE_RATE)
        context_frames = int(round(context_seconds / _FRAME_SECONDS))

        if n_samples <= window_samples:
            with torch.inference_mode():
                emissions, _ = self._model(waveform_1d.unsqueeze(0).to(self._device))
            return emissions.cpu()

        extension = math.ceil(n_samples / window_samples) * window_samples - n_samples
        padded = torch.nn.functional.pad(
            waveform_1d,
            (context_samples, context_samples + extension),
        )
        chunk_length = window_samples + 2 * context_samples
        chunks = padded.unfold(0, chunk_length, window_samples)

        emissions_list = []
        with torch.inference_mode():
            for index in range(0, int(chunks.size(0)), batch_size):
                batch = chunks[index : index + batch_size].to(self._device)
                emissions, _ = self._model(batch)
                emissions_list.append(emissions.cpu())

        stitched = torch.cat(emissions_list, dim=0)
        # The wav2vec2 conv stack emits slightly fewer frames than
        # chunk_samples/320 (1699 instead of 1700 for a 34 s chunk). Keep
        # exactly window_samples/320 frames per chunk so the global
        # frame -> seconds grid stays exact; cropping a fixed context count
        # from both ends instead would drop one inner frame per chunk and
        # drift timestamps ~20 ms earlier per 30 s window.
        window_frames = window_samples // _FRAME_SAMPLES
        required_frames = context_frames + window_frames
        if int(stitched.shape[1]) < required_frames:
            raise AlignmentError(
                f"MMS model produced {int(stitched.shape[1])} emission frames per "
                f"chunk; at least {required_frames} are required to keep the "
                f"{_FRAME_SECONDS * 1000:.0f} ms timeline grid. The conv stack "
                "emits slightly fewer frames than samples/320, so "
                "context_seconds must be large enough to absorb the shortfall."
            )
        stitched = stitched[:, context_frames : context_frames + window_frames, :]
        stitched = stitched.flatten(0, 1)

        extension_frames = int(round((extension / _SAMPLE_RATE) / _FRAME_SECONDS))
        if extension_frames > 0:
            stitched = stitched[:-extension_frames]

        return stitched.unsqueeze(0)

    def _load_bundle(self) -> None:
        try:
            import torch
            from torchaudio.pipelines import MMS_FA
        except ImportError as exc:
            raise AlignmentUnavailableError(
                "torchaudio with MMS_FA is not installed; run "
                "scripts/install_linux_local_engine.sh or use `--alignment none`."
            ) from exc

        if self._requested_device is not None:
            device = self._requested_device
        else:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        bundle = MMS_FA
        self._model = bundle.get_model().to(device).train(False)
        self._tokenizer = bundle.get_tokenizer()
        self._blank_id = getattr(self._tokenizer, "blank_id", 0)
        self._labels = bundle.get_labels()
        self._device = device

    def _run_real_forced_align(
        self,
        samples: Any,
        words: list[TranscribedWord],
        language: str,
    ) -> list[dict[str, Any]]:
        import torch
        from torchaudio.functional import forced_align

        if self._model is None or self._tokenizer is None:
            self._load_bundle()

        waveform = torch.as_tensor(samples, dtype=torch.float32).flatten()
        emissions = self.generate_emissions(waveform)
        tokens_per_word, target_tokens = build_mms_targets(words, self._tokenizer)
        if not target_tokens:
            raise AlignmentError("MMS tokenizer produced no target tokens for alignable words")

        targets_tensor = torch.tensor([target_tokens], dtype=torch.int32)
        input_lengths = torch.tensor([emissions.shape[1]], dtype=torch.int32)
        target_lengths = torch.tensor([len(target_tokens)], dtype=torch.int32)

        alignments, _scores = forced_align(
            emissions,
            targets_tensor,
            input_lengths,
            target_lengths,
            blank=self._blank_id,
        )
        spans = collapse_alignment_path(alignments[0].tolist(), self._blank_id)
        return attach_spans_to_words(
            spans,
            tokens_per_word,
            self._tokenizer,
            labels=self._labels,
        )
