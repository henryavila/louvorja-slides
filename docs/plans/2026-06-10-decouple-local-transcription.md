# Decouple Local Transcription Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the Titan runtime dependency with a local Linux-capable high-quality audio-to-lyrics-with-timestamps pipeline for LouvorJA `.slja` generation.

**Architecture:** Keep LouvorJA-specific generation in this repository and copy only the small transcription/alignment decisions that matter from Titan. The default local path prioritizes quality over speed: vocal separation, Whisper word timestamps, forced alignment, cache, then the existing slide layout/exporter.

**Tech Stack:** Python 3.12, `unittest`, `imageio-ffmpeg`, `numpy`, `pywhispercpp`, `audio-separator`, `torch`, `torchaudio`.

---

## Source Decisions To Preserve

- Do not depend on `titan-chordpro-lib` at runtime.
- Reuse Titan's learned transcription choices:
  - Whisper model defaults to `large-v3` for LouvorJA local transcription because quality matters more than runtime here.
  - Keep `medium` as the documented lower-memory fallback.
  - Use word-level timestamps: `token_timestamps=True`, `max_len=1`, `split_on_word=True`.
  - Use anti-hallucination thresholds: `entropy_thold=2.2`, `no_speech_thold=0.7`.
  - Filter bracketed non-lyric tokens such as `[Música]`, `[BLANK_AUDIO]`, `[Aplausos]`.
  - Normalize audio to mono 16 kHz before Whisper/alignment.
- Reuse Titan's quality-improving shape, not its ChordPro architecture:
  - Source audio -> vocals stem -> Whisper transcription -> MMS forced alignment -> lightweight LouvorJA document.
  - No chord recognition, beat tracking, syllabification, ChordPro writer, or Titan orchestrator.
- Keep existing slide rules:
  - Max 2 lyric lines per slide.
  - Avoid quick imperceptible slide transitions.
  - Use `letra_aux=(Nx)` only for consecutive repeated slides.

## Quality Defaults

Local default pipeline:

```text
mp3/mp4
  -> ffmpeg decode/probe
  -> htdemucs vocal separation
  -> Whisper large-v3 word timestamps
  -> torchaudio MMS forced alignment
  -> adaptive phrase grouping
  -> existing slide planner
  -> .slja archive
```

Fallbacks must be explicit. Do not silently reduce quality. If vocal separation,
Whisper, or MMS alignment is enabled and cannot run, fail with a clear error
that names the failing stage and the flag required to bypass it.

## Implementation Constraints

- Cache entries must include the relevant quality configuration. A raw transcript
  from `medium` must not be reused for `large-v3`, and an aligned transcript
  must not be reused when alignment is disabled.
- The alignment stage must not silently return the unaligned Whisper transcript
  for alignable lyrics. If MMS alignment is enabled and produces no spans for
  alignable words, raise an alignment error.
- The `audio-separator` adapter must call `Separator.load_model("htdemucs_ft.yaml")`
  before `separate()`. The library raises if separation is attempted before a
  model is loaded.
- `unittest` tests must be inside `unittest.TestCase` classes. Top-level test
  functions are not discovered by `python -m unittest`.
- Dependency verification must include `audio-separator`, `torch`, and
  `torchaudio`, not just the lightweight wheels.

---

### Task 1: Replace Titan Requirement With Local ML Requirements

**Files:**
- Modify: `requirements.txt`
- Modify: `README.md`
- Test: no code test; verify installation metadata manually.

**Step 1: Update requirements**

Replace the Titan editable dependency with local Linux-capable dependencies:

```text
imageio-ffmpeg>=0.6.0
numpy>=2.0
pywhispercpp>=1.5.0
audio-separator>=0.17
torch==2.6.0
torchaudio==2.6.0
```

Do not add `titan-chordpro-lib`.

**Step 2: Update README setup language**

Change the setup section from "Mac/Titan dependency" to "Local Linux/macOS setup".

Document:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Add a note:

```text
The default local transcriber is intentionally slow and quality-first. It runs
vocal separation, Whisper large-v3, and forced alignment by default.
```

**Step 3: Verify dependency resolution**

Run:

```bash
python -m pip download --only-binary=:all: --dest /tmp/louvorja-deps \
  imageio-ffmpeg pywhispercpp numpy
python -m pip install --dry-run -r requirements.txt
```

Expected: lightweight wheels download for `manylinux` / `x86_64`, and pip can
resolve the full local ML stack. If the torch/torchaudio pair cannot resolve on
the current Python, update both pins together to a matching version pair; do not
leave them as independent `>=` constraints.

**Step 4: Commit**

```bash
git add requirements.txt README.md
git commit -m "docs: document local transcription dependencies"
```

---

### Task 2: Add Core Transcript Data Model

**Files:**
- Create: `louvorja_slides/transcription.py`
- Test: `tests/test_transcription_models.py`

**Step 1: Write failing tests**

Create `tests/test_transcription_models.py`:

```python
from __future__ import annotations

import unittest

from louvorja_slides.transcription import Transcript, TranscribedWord


class TranscriptionModelsTest(unittest.TestCase):
    def test_transcript_rejects_empty_word_list(self) -> None:
        with self.assertRaisesRegex(ValueError, "no transcribed words"):
            Transcript(words=[], detected_language="pt", duration_seconds=10.0)

    def test_transcript_rejects_inverted_word_timestamp(self) -> None:
        with self.assertRaisesRegex(ValueError, "end"):
            TranscribedWord(text="Fala", start=2.0, end=1.0)

    def test_transcript_sorts_words_by_start_time(self) -> None:
        transcript = Transcript(
            words=[
                TranscribedWord(text="comigo", start=2.0, end=2.4),
                TranscribedWord(text="Fala", start=1.0, end=1.4),
            ],
            detected_language="pt",
            duration_seconds=3.0,
        )

        self.assertEqual([word.text for word in transcript.words], ["Fala", "comigo"])

    def test_transcript_json_roundtrip(self) -> None:
        transcript = Transcript(
            words=[TranscribedWord(text="Fala", start=1.0, end=1.4, source="whisper")],
            detected_language="pt",
            duration_seconds=3.0,
        )

        self.assertEqual(Transcript.from_dict(transcript.to_dict()), transcript)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_transcription_models -v
```

Expected: FAIL because `louvorja_slides.transcription` does not exist.

**Step 3: Implement minimal model**

Create `louvorja_slides/transcription.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


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

    def to_dict(self) -> dict[str, object]:
        return {
            "words": [word.to_dict() for word in self.words],
            "detected_language": self.detected_language,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Transcript":
        return cls(
            words=[
                TranscribedWord.from_dict(item)
                for item in data.get("words", [])
                if isinstance(item, dict)
            ],
            detected_language=(
                str(data["detected_language"])
                if data.get("detected_language") is not None
                else None
            ),
            duration_seconds=float(data["duration_seconds"]),
        )
```

**Step 4: Run test to verify it passes**

Run:

```bash
python -m unittest tests.test_transcription_models -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add louvorja_slides/transcription.py tests/test_transcription_models.py
git commit -m "feat: add local transcript model"
```

---

### Task 3: Add Audio Decode And Probe Layer

**Files:**
- Create: `louvorja_slides/audio.py`
- Test: `tests/test_audio_decode.py`

**Step 1: Write failing tests using a fake ffmpeg runner**

Create `tests/test_audio_decode.py`:

```python
from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from louvorja_slides.audio import AudioDecodeError, decode_audio_16k_mono


def _write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes((np.array([0, 1000, -1000], dtype=np.int16)).tobytes())


class AudioDecodeTest(unittest.TestCase):
    def test_decode_audio_uses_ffmpeg_and_returns_float32_samples(self) -> None:
        calls = []

        def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
            calls.append(command)
            output_path = Path(command[-1])
            _write_wav(output_path)
            return SimpleNamespace(returncode=0, stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "song.mp3"
            audio_path.write_bytes(b"fake")

            decoded = decode_audio_16k_mono(audio_path, run=fake_run, ffmpeg_exe="ffmpeg")

        self.assertEqual(decoded.sample_rate, 16000)
        self.assertEqual(decoded.samples.dtype, np.float32)
        self.assertEqual(len(decoded.samples), 3)
        self.assertIn("-ar", calls[0])
        self.assertIn("16000", calls[0])
        self.assertIn("-ac", calls[0])
        self.assertIn("1", calls[0])

    def test_decode_audio_raises_clear_error_on_ffmpeg_failure(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(returncode=1, stderr="bad audio")

        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "song.mp4"
            audio_path.write_bytes(b"fake")

            with self.assertRaisesRegex(AudioDecodeError, "bad audio"):
                decode_audio_16k_mono(audio_path, run=fake_run, ffmpeg_exe="ffmpeg")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_audio_decode -v
```

Expected: FAIL because `louvorja_slides.audio` does not exist.

**Step 3: Implement audio layer**

Create `louvorja_slides/audio.py` with:

- `DecodedAudio(samples: np.ndarray, sample_rate: int, duration_seconds: float)`
- `AudioDecodeError`
- `decode_audio_16k_mono(audio_path, run=subprocess.run, ffmpeg_exe=None)`
- Use `imageio_ffmpeg.get_ffmpeg_exe()` when `ffmpeg_exe` is `None`.
- Write decoded WAV to a temporary file.
- Read WAV using stdlib `wave`.
- Convert int16 PCM to `np.float32` in `[-1.0, 1.0]`.

Implementation shape:

```python
command = [
    ffmpeg_exe,
    "-y",
    "-i",
    str(audio_path),
    "-vn",
    "-ac",
    "1",
    "-ar",
    "16000",
    "-acodec",
    "pcm_s16le",
    str(wav_path),
]
```

**Step 4: Run test to verify it passes**

Run:

```bash
python -m unittest tests.test_audio_decode -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add louvorja_slides/audio.py tests/test_audio_decode.py
git commit -m "feat: add local audio decoding"
```

---

### Task 4: Add Cache By Audio Hash And Stage

**Files:**
- Create: `louvorja_slides/cache.py`
- Test: `tests/test_cache.py`

**Step 1: Write failing tests**

Create `tests/test_cache.py`:

```python
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from louvorja_slides.cache import audio_sha256, cache_key, cache_path, load_json, save_json


class CacheTest(unittest.TestCase):
    def test_audio_sha256_uses_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "song.mp3"
            path.write_bytes(b"abc")

            self.assertEqual(audio_sha256(path), "ba7816bf8f01cfea")

    def test_save_and_load_json_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = cache_path(Path(tmp), "abc123", "transcript", variant="large-v3")
            save_json(path, {"words": [{"text": "Fala"}]})

            self.assertEqual(load_json(path), {"words": [{"text": "Fala"}]})

    def test_cache_key_changes_when_quality_config_changes(self) -> None:
        self.assertNotEqual(
            cache_key({"whisper_model": "medium", "alignment": "mms"}),
            cache_key({"whisper_model": "large-v3", "alignment": "mms"}),
        )


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_cache -v
```

Expected: FAIL because `louvorja_slides.cache` does not exist.

**Step 3: Implement cache helpers**

Create `louvorja_slides/cache.py`:

- `audio_sha256(path) -> str`, first 16 hex chars.
- `cache_key(mapping) -> str`, a stable short hash of sorted JSON.
- `cache_path(root, audio_id, stage, variant) -> Path`, shape `<root>/<audio_id>/<stage>/<variant>.json`.
- `load_json(path) -> dict | None`, returns `None` on missing file.
- `save_json(path, payload)`, atomic write through temp file then replace.

**Step 4: Run test to verify it passes**

Run:

```bash
python -m unittest tests.test_cache -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add louvorja_slides/cache.py tests/test_cache.py
git commit -m "feat: add transcription stage cache"
```

---

### Task 5: Add Vocal Separation Adapter

**Files:**
- Create: `louvorja_slides/separation.py`
- Test: `tests/test_separation.py`

**Step 1: Write failing tests with fake separator**

Create `tests/test_separation.py`:

```python
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from louvorja_slides.separation import SeparationUnavailableError, separate_vocals


class SeparationTest(unittest.TestCase):
    def test_separate_vocals_returns_existing_cached_vocal_stem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cached = root / "abc123" / "vocals.wav"
            cached.parent.mkdir(parents=True)
            cached.write_bytes(b"wav")
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")

            result = separate_vocals(audio, audio_id="abc123", cache_root=root)

        self.assertEqual(result, cached)

    def test_separate_vocals_fails_clearly_when_dependency_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "song.mp3"
            audio.write_bytes(b"audio")

            with self.assertRaisesRegex(SeparationUnavailableError, "audio-separator"):
                separate_vocals(
                    audio,
                    audio_id="abc123",
                    cache_root=Path(tmp),
                    separator_factory=lambda: (_ for _ in ()).throw(ImportError("missing")),
                )

    def test_separate_vocals_loads_htdemucs_model_before_separating(self) -> None:
        events = []

        class FakeSeparator:
            def __init__(self, output_dir: str, output_format: str, log_level: int) -> None:
                self.output_dir = Path(output_dir)

            def load_model(self, model_filename: str) -> None:
                events.append(("load", model_filename))

            def separate(self, audio_file_path: str) -> list[str]:
                events.append(("separate", audio_file_path))
                output = self.output_dir / "song_(Vocals)_htdemucs_ft.wav"
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"vocals")
                return [str(output)]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")

            result = separate_vocals(
                audio,
                audio_id="abc123",
                cache_root=root,
                separator_factory=FakeSeparator,
            )

        self.assertEqual(events[0], ("load", "htdemucs_ft.yaml"))
        self.assertEqual(events[1][0], "separate")
        self.assertEqual(result.name, "vocals.wav")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_separation -v
```

Expected: FAIL because `louvorja_slides.separation` does not exist.

**Step 3: Implement separation adapter**

Create `louvorja_slides/separation.py`:

- `SeparationUnavailableError`
- `separate_vocals(audio_path, audio_id, cache_root, model_filename="htdemucs_ft.yaml", separator_factory=None) -> Path`
- If `<cache_root>/<audio_id>/vocals.wav` exists, return it.
- Lazy import `audio_separator.separator.Separator`.
- Instantiate `Separator(output_dir=str(stems_dir), output_format="WAV", log_level=logging.WARNING)`.
- Call `separator.load_model(model_filename=model_filename)` before separating.
- Run separation.
- Locate generated vocals stem by filename containing `Vocals` or `vocals`.
- Copy or move it to `<cache_root>/<audio_id>/vocals.wav`.
- If no vocals stem is found, raise a clear error.

Do not silently fall back to full mix. Full-mix transcription must require an explicit CLI flag later.

**Step 4: Run test to verify it passes**

Run:

```bash
python -m unittest tests.test_separation -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add louvorja_slides/separation.py tests/test_separation.py
git commit -m "feat: add vocal separation adapter"
```

---

### Task 6: Add Whisper Word Timestamp Backend

**Files:**
- Modify: `louvorja_slides/transcription.py`
- Test: `tests/test_local_whisper.py`

**Step 1: Write failing tests with fake model**

Create `tests/test_local_whisper.py`:

```python
from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from louvorja_slides.transcription import LocalWhisperTranscriber


class LocalWhisperTest(unittest.TestCase):
    def test_transcriber_uses_quality_whisper_arguments(self) -> None:
        calls = []

        class FakeModel:
            def transcribe(self, samples: np.ndarray, **kwargs: object) -> list[SimpleNamespace]:
                calls.append(kwargs)
                return [SimpleNamespace(t0=100, t1=160, text="Fala")]

        transcriber = LocalWhisperTranscriber(model=FakeModel(), model_id="large-v3")

        transcript = transcriber.transcribe_samples(
            samples=np.zeros(16000, dtype=np.float32),
            sample_rate=16000,
            duration_seconds=1.0,
            language="pt",
        )

        self.assertEqual(transcript.words[0].text, "Fala")
        self.assertEqual(transcript.words[0].start, 1.0)
        self.assertEqual(transcript.words[0].end, 1.6)
        self.assertEqual(calls[0]["token_timestamps"], True)
        self.assertEqual(calls[0]["max_len"], 1)
        self.assertEqual(calls[0]["split_on_word"], True)
        self.assertEqual(calls[0]["entropy_thold"], 2.2)
        self.assertEqual(calls[0]["no_speech_thold"], 0.7)
        self.assertEqual(calls[0]["language"], "pt")

    def test_transcriber_filters_bracketed_non_lyric_tokens(self) -> None:
        class FakeModel:
            def transcribe(self, samples: np.ndarray, **kwargs: object) -> list[SimpleNamespace]:
                return [
                    SimpleNamespace(t0=0, t1=100, text="[Música]"),
                    SimpleNamespace(t0=100, t1=200, text="Santo"),
                    SimpleNamespace(t0=200, t1=300, text="[BLANK_AUDIO]"),
                ]

        transcriber = LocalWhisperTranscriber(model=FakeModel(), model_id="large-v3")

        transcript = transcriber.transcribe_samples(
            samples=np.zeros(16000, dtype=np.float32),
            sample_rate=16000,
            duration_seconds=3.0,
            language="pt",
        )

        self.assertEqual([word.text for word in transcript.words], ["Santo"])


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_local_whisper -v
```

Expected: FAIL because `LocalWhisperTranscriber` does not exist.

**Step 3: Implement backend**

Modify `louvorja_slides/transcription.py`:

- Add `_WHISPER_SPECIAL_TOKEN_RE = re.compile(r"^\s*\[[^\[\]]*\]\s*$")`.
- Add `LocalWhisperTranscriber`.
- Constructor:
  - `model_id: str = "large-v3"`
  - optional injected `model` for tests.
  - lazy import `pywhispercpp.model.Model`.
- `transcribe_samples(samples, sample_rate, duration_seconds, language)`.
- Validate `sample_rate == 16000`.
- Convert `seg.t0` / `seg.t1` centiseconds to seconds.
- Clamp inverted end times.
- Filter empty/bracketed text.
- Raise `ValueError("no transcribed words")` if all tokens are filtered.

**Step 4: Run test to verify it passes**

Run:

```bash
python -m unittest tests.test_local_whisper -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add louvorja_slides/transcription.py tests/test_local_whisper.py
git commit -m "feat: add local whisper transcription"
```

---

### Task 7: Add MMS Forced Alignment Adapter

**Files:**
- Create: `louvorja_slides/alignment.py`
- Test: `tests/test_alignment.py`

**Step 1: Write failing tests for sanitization and span conversion**

Create `tests/test_alignment.py`:

```python
from __future__ import annotations

import unittest

from louvorja_slides.alignment import refine_words_from_spans, sanitize_for_mms
from louvorja_slides.transcription import TranscribedWord


class AlignmentTest(unittest.TestCase):
    def test_sanitize_for_mms_removes_diacritics_punctuation_and_spaces(self) -> None:
        self.assertEqual(sanitize_for_mms("Coração,"), "coracao")
        self.assertEqual(sanitize_for_mms("Não temas!"), "naotemas")

    def test_refine_words_from_spans_updates_word_boundaries(self) -> None:
        words = [
            TranscribedWord("Fala", 10.0, 11.0, source="whisper"),
            TranscribedWord("comigo", 11.0, 12.0, source="whisper"),
        ]
        spans = [
            {"word_idx": 0, "start_frame": 50, "end_frame": 70},
            {"word_idx": 1, "start_frame": 80, "end_frame": 110},
        ]

        refined = refine_words_from_spans(words, spans, frame_seconds=0.02)

        self.assertEqual(refined[0].start, 1.0)
        self.assertEqual(refined[0].end, 1.42)
        self.assertEqual(refined[0].source, "mms_align")
        self.assertEqual(refined[1].start, 1.6)
        self.assertEqual(refined[1].end, 2.22)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_alignment -v
```

Expected: FAIL because `louvorja_slides.alignment` does not exist.

**Step 3: Implement pure helpers first**

Create `louvorja_slides/alignment.py`:

- `sanitize_for_mms(text)`, adapted from Titan's MMS boundary:
  - NFD normalize.
  - Keep ASCII letters only.
  - Lowercase.
- `refine_words_from_spans(words, spans, frame_seconds=0.02)`.
- Group spans by `word_idx`.
- Convert frames to `[start_frame * frame_seconds, (end_frame + 1) * frame_seconds]`.
- Preserve original word if no span exists.

**Step 4: Run test to verify it passes**

Run:

```bash
python -m unittest tests.test_alignment -v
```

Expected: PASS.

**Step 5: Add engine tests with fake aligner**

Extend `tests/test_alignment.py` with:

```python
import numpy as np

from louvorja_slides.alignment import AlignmentError, MmsForcedAligner
from louvorja_slides.transcription import Transcript


class MmsForcedAlignerTest(unittest.TestCase):
    def test_forced_aligner_raises_when_alignable_words_have_no_spans(self) -> None:
        transcript = Transcript(
            words=[TranscribedWord("Fala", 1.0, 2.0, source="whisper")],
            detected_language="pt",
            duration_seconds=3.0,
        )
        aligner = MmsForcedAligner(run_forced_align=lambda samples, words, language: [])

        with self.assertRaisesRegex(AlignmentError, "no alignment spans"):
            aligner.align_transcript(
                transcript,
                samples=np.zeros(16000, dtype=np.float32),
                language="pt",
            )

    def test_forced_aligner_refines_words_when_spans_exist(self) -> None:
        transcript = Transcript(
            words=[TranscribedWord("Fala", 1.0, 2.0, source="whisper")],
            detected_language="pt",
            duration_seconds=3.0,
        )
        aligner = MmsForcedAligner(
            run_forced_align=lambda samples, words, language: [
                {"word_idx": 0, "start_frame": 60, "end_frame": 80}
            ]
        )

        refined = aligner.align_transcript(
            transcript,
            samples=np.zeros(16000, dtype=np.float32),
            language="pt",
        )

        self.assertEqual(refined.words[0].source, "mms_align")
```

**Step 6: Implement `MmsForcedAligner`**

Implement:

- Lazy import `torch`, `torchaudio.pipelines.MMS_FA`, `torchaudio.functional.forced_align`.
- Generate emissions in 30s chunks with 2s context, as Titan does.
- Run one global Viterbi over stitched emissions.
- Decode spans back to word indices.
- Return a new `Transcript` with refined word times.
- If tokenizer rejects sanitized text, raise `AlignmentError`.
- If no spans are returned for alignable words, raise `AlignmentError`.
- If dependency missing, raise `AlignmentUnavailableError`.

**Step 7: Run tests**

Run:

```bash
python -m unittest tests.test_alignment -v
```

Expected: PASS.

**Step 8: Commit**

```bash
git add louvorja_slides/alignment.py tests/test_alignment.py
git commit -m "feat: add forced alignment adapter"
```

---

### Task 8: Convert Transcript To LouvorJA-Compatible Document

**Files:**
- Create: `louvorja_slides/document.py`
- Test: `tests/test_document.py`

**Step 1: Write failing tests**

Create `tests/test_document.py`:

```python
from __future__ import annotations

import unittest

from louvorja_slides.document import transcript_to_document
from louvorja_slides.slja import extract_lyric_slides
from louvorja_slides.transcription import Transcript, TranscribedWord


class DocumentTest(unittest.TestCase):
    def test_transcript_to_document_is_compatible_with_slja_extractor(self) -> None:
        transcript = Transcript(
            words=[
                TranscribedWord("Fala", 1.0, 1.3),
                TranscribedWord("comigo", 1.4, 1.9),
                TranscribedWord("Santo", 5.0, 5.5),
            ],
            detected_language="pt",
            duration_seconds=10.0,
        )

        doc = transcript_to_document(transcript, title="Minha musica")
        slides = extract_lyric_slides(doc)

        self.assertEqual(doc.metadata.title, "Minha musica")
        self.assertEqual(slides[0].start_seconds, 1.0)
        self.assertIn("Fala", slides[0].lines[0])


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_document -v
```

Expected: FAIL because `louvorja_slides.document` does not exist.

**Step 3: Implement document adapter**

Create `louvorja_slides/document.py`:

- Use `types.SimpleNamespace`; do not introduce Pydantic.
- Build:
  - `metadata.title`
  - `sections`
  - each section has `lines`
  - each lyric line has `line_type="lyric"`, `text`, `word_alignments`
  - each word alignment has `text`, `timestamp.start`, `timestamp.end`
- Group words into lines using adaptive gap threshold:
  - Compute positive inter-word gaps.
  - `line_gap = max(2.5 * median_gap, 1.0)`.
  - New lyric line when `next.start - prev.end > line_gap`.
- One section is enough for SLJA extraction. Do not infer verse/chorus.

**Step 4: Run test to verify it passes**

Run:

```bash
python -m unittest tests.test_document -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add louvorja_slides/document.py tests/test_document.py
git commit -m "feat: build document from local transcript"
```

---

### Task 9: Add End-To-End Local Transcription Orchestrator

**Files:**
- Create: `louvorja_slides/local_pipeline.py`
- Test: `tests/test_local_pipeline.py`

**Step 1: Write failing tests with injected fakes**

Create `tests/test_local_pipeline.py`:

```python
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from louvorja_slides.local_pipeline import LocalPipelineConfig, transcribe_audio_local
from louvorja_slides.transcription import Transcript, TranscribedWord


class LocalPipelineTest(unittest.TestCase):
    def test_pipeline_uses_separation_decode_whisper_and_alignment(self) -> None:
        events = []

        def fake_separate(audio_path: Path, **kwargs: object) -> Path:
            events.append("separate")
            return audio_path.with_suffix(".vocals.wav")

        def fake_decode(audio_path: Path):
            events.append(f"decode:{audio_path.name}")
            return type("Decoded", (), {
                "samples": np.zeros(16000, dtype=np.float32),
                "sample_rate": 16000,
                "duration_seconds": 10.0,
            })()

        class FakeTranscriber:
            def transcribe_samples(self, **kwargs: object) -> Transcript:
                events.append("whisper")
                return Transcript(
                    words=[TranscribedWord("Fala", 1.0, 1.5, source="whisper")],
                    detected_language="pt",
                    duration_seconds=10.0,
                )

        class FakeAligner:
            def align_transcript(self, transcript: Transcript, **kwargs: object) -> Transcript:
                events.append("align")
                return Transcript(
                    words=[TranscribedWord("Fala", 1.1, 1.6, source="mms_align")],
                    detected_language="pt",
                    duration_seconds=10.0,
                )

        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "song.mp3"
            audio.write_bytes(b"audio")
            transcript = transcribe_audio_local(
                audio,
                config=LocalPipelineConfig(cache_root=Path(tmp) / ".cache"),
                separate_vocals_fn=fake_separate,
                decode_fn=fake_decode,
                transcriber=FakeTranscriber(),
                aligner=FakeAligner(),
            )

        self.assertEqual(events, ["separate", "decode:song.vocals.wav", "whisper", "align"])
        self.assertEqual(transcript.words[0].source, "mms_align")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_local_pipeline -v
```

Expected: FAIL because `louvorja_slides.local_pipeline` does not exist.

**Step 3: Implement orchestrator**

Create `louvorja_slides/local_pipeline.py`:

- `LocalPipelineConfig` dataclass:
  - `language: str = "pt"`
  - `cache_root: Path = Path(".louvorja-cache")`
  - `whisper_model: str = "large-v3"`
  - `vocal_separation: str = "htdemucs_ft"`
  - `alignment: str = "mms"`
- `transcribe_audio_local(...) -> Transcript`
- Steps:
  1. Compute `audio_id`.
  2. Compute `raw_variant = cache_key({"stage": "raw", "whisper_model": config.whisper_model, "vocal_separation": config.vocal_separation, "language": config.language})`.
  3. Compute `aligned_variant = cache_key({"stage": "aligned", "whisper_model": config.whisper_model, "vocal_separation": config.vocal_separation, "alignment": config.alignment, "language": config.language})`.
  4. If aligned transcript cache exists and `config.alignment == "mms"`, return it before loading ML models.
  5. Separate vocals unless config says explicit `"none"`.
  6. Decode selected audio to 16 kHz mono.
  7. Load raw transcript cache if present; otherwise run Whisper and save raw transcript.
  8. Run forced alignment unless config says explicit `"none"`.
  9. Save aligned transcript.
  10. Return aligned transcript, or raw transcript only when `config.alignment == "none"`.
- If no words remain after Whisper, raise clear error:

```text
local transcription produced no lyric words; try a larger model or inspect the vocal stem
```

Add tests for cache behavior:

- When aligned cache exists, pipeline returns it without calling separation,
  decode, Whisper, or alignment.
- When raw cache exists but aligned cache does not, pipeline still decodes audio
  and runs alignment, but does not call Whisper.
- Changing `whisper_model` changes the cache variant.

**Step 4: Run test to verify it passes**

Run:

```bash
python -m unittest tests.test_local_pipeline -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add louvorja_slides/local_pipeline.py tests/test_local_pipeline.py
git commit -m "feat: add local transcription pipeline"
```

---

### Task 10: Wire CLI To Local Pipeline And Remove Titan Default

**Files:**
- Modify: `audio_to_slja.py`
- Test: `tests/test_cli.py`

**Step 1: Add failing CLI test**

Modify `tests/test_cli.py` to patch `audio_to_slja.transcribe_audio_local` instead of `load_transcribe`.

Add helper and assertion that default CLI calls local pipeline:

```python
def _fake_transcript() -> Transcript:
    return Transcript(
        words=[TranscribedWord("Fala", 7.0, 7.4), TranscribedWord("comigo", 7.5, 8.0)],
        detected_language="pt",
        duration_seconds=30.0,
    )

with patch("audio_to_slja.transcribe_audio_local", return_value=_fake_transcript()):
    exit_code = audio_to_slja.main([str(audio_path), "--output", str(output_path)])
```

Then assert:

- exit code is `0`
- `.slja` exists
- `slides.lja` contains lyric text.

Add another test:

```python
def test_cli_requires_explicit_flag_to_disable_quality_stages(self) -> None:
    parser = audio_to_slja.build_parser()
    args = parser.parse_args(["song.mp3", "--vocal-separation", "none", "--alignment", "none"])
    self.assertEqual(args.vocal_separation, "none")
    self.assertEqual(args.alignment, "none")
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_cli -v
```

Expected: FAIL because CLI still imports Titan.

**Step 3: Modify CLI**

Update `audio_to_slja.py`:

- Remove `load_transcribe()` and Titan import path.
- Import:

```python
from louvorja_slides.document import transcript_to_document
from louvorja_slides.local_pipeline import LocalPipelineConfig, transcribe_audio_local
```

- Parser options:
  - Keep positional `audio`.
  - Keep `--output`, `--title`, `--language`, `--lines-per-slide`.
  - Replace `--device` with quality-specific options:
    - `--whisper-model`, default `large-v3`, choices `medium`, `large-v2`, `large-v3`.
    - `--vocal-separation`, default `htdemucs_ft`, choices `htdemucs_ft`, `none`.
    - `--alignment`, default `mms`, choices `mms`, `none`.
    - `--cache-dir`, default `.louvorja-cache`.
  - Remove `--device`; tests patch the local pipeline instead of adding a mock user-facing device mode.
- Flow:

```python
transcript = transcribe_audio_local(audio_path, config=config)
doc = transcript_to_document(transcript, title=title or audio_path.stem)
slides = extract_lyric_slides(doc, lines_per_slide=args.lines_per_slide)
write_slja(...)
```

**Step 4: Run CLI tests**

Run:

```bash
python -m unittest tests.test_cli -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add audio_to_slja.py tests/test_cli.py
git commit -m "feat: use local transcription in cli"
```

---

### Task 11: Add Integration Smoke Test Without Real ML

**Files:**
- Create: `tests/test_audio_to_slja_local_flow.py`

**Step 1: Write integration test using patched pipeline**

Create `tests/test_audio_to_slja_local_flow.py`:

```python
from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import audio_to_slja
from louvorja_slides.transcription import Transcript, TranscribedWord


class AudioToSljaLocalFlowTest(unittest.TestCase):
    def test_audio_to_slja_uses_local_transcript_and_embeds_audio(self) -> None:
        transcript = Transcript(
            words=[
                TranscribedWord("Fala", 7.0, 7.4),
                TranscribedWord("comigo", 7.5, 8.0),
            ],
            detected_language="pt",
            duration_seconds=30.0,
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "song.mp3"
            output_path = tmp_path / "song.slja"
            audio_path.write_bytes(b"audio bytes")

            with patch("audio_to_slja.transcribe_audio_local", return_value=transcript):
                exit_code = audio_to_slja.main(
                    [str(audio_path), "--output", str(output_path), "--title", "Fala comigo"]
                )

            self.assertEqual(exit_code, 0)
            with zipfile.ZipFile(output_path) as archive:
                self.assertIn("audio\\song.mp3", archive.namelist())
                text = archive.read("slides.lja").decode("cp1252")

        self.assertIn("letra=Fala comigo", text)
        self.assertIn("tempo=00:00:07", text)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test**

Run:

```bash
python -m unittest tests.test_audio_to_slja_local_flow -v
```

Expected: PASS.

**Step 3: Commit**

```bash
git add tests/test_audio_to_slja_local_flow.py
git commit -m "test: cover local audio to slja flow"
```

---

### Task 12: Add Optional Real ML Smoke Script

**Files:**
- Create: `scripts/smoke_local_transcription.py`
- Modify: `.gitignore`
- Modify: `README.md`

**Step 1: Create script**

Create the `scripts/` directory if it does not exist, then create
`scripts/smoke_local_transcription.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from louvorja_slides.local_pipeline import LocalPipelineConfig, transcribe_audio_local


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--language", default="pt")
    parser.add_argument("--whisper-model", default="large-v3")
    parser.add_argument("--vocal-separation", default="htdemucs_ft", choices=("htdemucs_ft", "none"))
    parser.add_argument("--alignment", default="mms", choices=("mms", "none"))
    args = parser.parse_args()

    transcript = transcribe_audio_local(
        args.audio,
        config=LocalPipelineConfig(
            language=args.language,
            whisper_model=args.whisper_model,
            vocal_separation=args.vocal_separation,
            alignment=args.alignment,
        ),
    )
    for word in transcript.words[:80]:
        print(f"{word.start:8.2f} {word.end:8.2f} {word.text}")
    print(f"words={len(transcript.words)} duration={transcript.duration_seconds:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 2: Ignore local audio and cache**

Modify `.gitignore`:

```text
.louvorja-cache/
local_audio/
local_outputs/
```

**Step 3: Document smoke command**

Add to README:

```bash
python scripts/smoke_local_transcription.py local_audio/song.mp3
python audio_to_slja.py local_audio/song.mp3 --title "Song" --output local_outputs/song.slja
```

**Step 4: Run syntax check**

Run:

```bash
python -m py_compile scripts/smoke_local_transcription.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/smoke_local_transcription.py .gitignore README.md
git commit -m "chore: add local transcription smoke script"
```

---

### Task 13: Update Guidelines With Transcription Quality Rules

**Files:**
- Modify: `docs/slide-generation-guidelines.md`
- Modify: `.ai/memory/louvorja-slide-generation.md`

**Step 1: Add transcription section**

Append to `docs/slide-generation-guidelines.md`:

```markdown
## Transcricao Local

- A transcricao local nao depende do Titan.
- O padrao e qualidade maxima, nao velocidade.
- Usar separacao vocal antes do Whisper por padrao.
- Usar Whisper `large-v3` por padrao; `medium` e fallback manual.
- Usar timestamps por palavra, nao por segmento.
- Filtrar tokens nao liricos entre colchetes.
- Usar alinhamento MMS para refinar timestamps por padrao.
- Nao reduzir qualidade automaticamente. Fallbacks como `--vocal-separation none`
  e `--alignment none` devem ser escolhas explicitas do operador.
```

**Step 2: Update memory**

Add a short note to `.ai/memory/louvorja-slide-generation.md`:

```markdown
## Local Transcription Decision

Titan is no longer a runtime dependency for LouvorJA slides. The project copies
only the useful transcription decisions: vocal separation, Whisper word
timestamps, anti-hallucination thresholds, bracket-token filtering, MMS forced
alignment, and adaptive phrase grouping.
```

**Step 3: Commit**

```bash
git add docs/slide-generation-guidelines.md .ai/memory/louvorja-slide-generation.md
git commit -m "docs: capture local transcription rules"
```

---

### Task 14: Full Verification

**Files:**
- No file edits unless verification exposes a bug.

**Step 1: Run full unit suite**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: PASS.

**Step 2: Run import smoke**

Run:

```bash
python - <<'PY'
from pywhispercpp.model import Model
import imageio_ffmpeg
import numpy
from audio_separator.separator import Separator
import torch
import torchaudio
print("ok", Model, imageio_ffmpeg.get_ffmpeg_exe(), numpy.__version__, Separator, torch.__version__, torchaudio.__version__)
PY
```

Expected: imports succeed and ffmpeg path plus dependency versions print.

**Step 3: Run optional real audio smoke if local audio exists**

If `local_audio/*.mp3` or `local_audio/*.mp4` exists, run:

```bash
python scripts/smoke_local_transcription.py local_audio/<file> --whisper-model medium
```

Expected:

- It prints at least one transcribed word with timestamps.
- If `medium` is poor, rerun with default `large-v3`.
- Do not commit local audio, cache, or generated outputs.

**Step 4: Inspect git status**

Run:

```bash
git status -sb
```

Expected: clean after commits, except ignored local cache/audio/output files.

---

## Acceptance Criteria

- `audio_to_slja.py song.mp3 --output song.slja` no longer imports Titan.
- `requirements.txt` no longer references `../titan-chordpro-lib`.
- Default local pipeline uses quality-first stages:
  - vocal separation enabled;
  - Whisper `large-v3`;
  - word timestamps enabled;
  - MMS forced alignment enabled.
- Any quality-reducing bypass is explicit through CLI flags.
- Generated `.slja` still embeds:
  - `slides.lja`
  - original input audio under `audio\...`
  - `imagens\Capa.jpg`
  - `imagens\slides.jpg`
- Existing slide layout tests still pass.
- New tests cover:
  - transcript model validation;
  - audio decode command shape;
  - cache;
  - vocal separation adapter behavior;
  - Whisper parameters and token filtering;
  - MMS sanitization/span conversion;
  - transcript-to-document conversion;
  - CLI local flow.

## Explicit Non-Goals

- Do not implement chord recognition.
- Do not generate ChordPro.
- Do not infer verse/chorus labels for LouvorJA output.
- Do not add a frontend.
- Do not commit real user audio or real validation `.slja` files.
