# Port Titan MMS Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Port Titan's real MMS/torchaudio forced-alignment path into the LouvorJA local engine so generated slide timestamps are based on 20ms-frame forced alignment instead of raw Whisper token timing.

**Architecture:** Keep LouvorJA's engine contract and `.slja` exporter in this repository. Port only Titan's alignment mechanics: MMS_FA bundle loading, chunked emission stitching, global `forced_align`, frame-to-second conversion, and optional phoneme preservation. Do not port Titan's chord recognition, beat tracking, or ChordPro writer in this phase.

**Tech Stack:** Python 3.12, `unittest`, `numpy`, `torch`, `torchaudio`, existing `audio-separator`, existing `pywhispercpp`.

**Verified Source Anchors:**

- verified_by: `louvorja_slides/audio.py:25-68` confirms this repo already decodes selected audio to 16 kHz mono samples.
- verified_by: `/home/henry/titan-chordpro-lib/titan_chordpro/engines/alignment/torchaudio_align.py:45-54` confirms MMS frame/sample constants and chunk settings.
- verified_by: `/home/henry/titan-chordpro-lib/titan_chordpro/engines/alignment/torchaudio_align.py:59-78` confirms Titan sanitization behavior.
- verified_by: `/home/henry/titan-chordpro-lib/titan_chordpro/engines/alignment/torchaudio_align.py:199-282` confirms Titan chunked emission stitching.
- verified_by: `/home/henry/titan-chordpro-lib/titan_chordpro/engines/alignment/torchaudio_align.py:284-419` confirms global `forced_align`, token collapse, and word reattachment.
- verified_by: `/home/henry/titan-chordpro-lib/titan_chordpro/core/schemas.py:51-69` confirms Titan phoneme and syllable event shapes.

---

## Source Reference

Read these Titan files before implementing:

- `/home/henry/titan-chordpro-lib/titan_chordpro/engines/alignment/torchaudio_align.py`
- `/home/henry/titan-chordpro-lib/titan_chordpro/core/schemas.py`
- `/home/henry/titan-chordpro-lib/titan_chordpro/fusion/syllabifier.py`
- `/home/henry/titan-chordpro-lib/titan_chordpro/engines/lang/portuguese.py`
- `/home/henry/titan-chordpro-lib/tests/unit/engines/alignment/test_torchaudio_align.py`

Key Titan behavior to preserve:

- MMS uses 16 kHz mono audio.
- MMS frame stride is 320 samples, so each frame is `0.02` seconds.
- Long audio is split into 30s windows with 2s context on both sides.
- Context frames are cropped before emissions are stitched.
- `torchaudio.functional.forced_align` runs once over the stitched global emissions.
- Sanitization strips diacritics, punctuation, spaces, and digits before tokenization.
- Span `end_frame` is inclusive, so event end seconds are `(end_frame + 1) * 0.02`.

Do not preserve Titan's file I/O design blindly. This repo already decodes selected audio to 16 kHz mono in `louvorja_slides/audio.py`; implement the local aligner to consume those samples directly.

---

### Task 1: Pin And Verify Alignment Dependencies

**Files:**
- Modify: `requirements.txt`
- Modify: `scripts/install_linux_local_engine.sh`
- Test: `tests/test_install_script.py`

**Step 1: Write the failing test**

Extend `tests/test_install_script.py`:

```python
def test_linux_install_script_verifies_torchaudio_alignment_stack(self) -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    self.assertIn("torch==2.11.0", requirements)
    self.assertIn("torchaudio==2.11.0", requirements)
    self.assertIn("torchaudio", text)
    self.assertIn("torchaudio.pipelines", text)
    self.assertIn("MMS_FA", text)
    self.assertIn("torch.__version__", text)
    self.assertIn("torchaudio.__version__", text)
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m unittest tests.test_install_script -v
```

Expected: FAIL because the installer does not verify `torchaudio` or `MMS_FA`.

**Step 3: Update dependency pins**

Modify `requirements.txt`:

```text
imageio-ffmpeg==0.6.0
numpy==2.4.6
pywhispercpp==1.5.0
audio-separator==0.44.2
onnxruntime==1.26.0
torch==2.11.0
torchaudio==2.11.0
```

Reason: the local package index offers `torch==2.12.0`, but `torchaudio` only up to `2.11.0`; the verified installable pair is `torch==2.11.0` and `torchaudio==2.11.0`. Pin `torch` directly so a fresh install cannot pair torchaudio with a different torch major/minor.

**Step 4: Update installer verification**

In `scripts/install_linux_local_engine.sh`, update the Python verification block to import the concrete alignment bundle:

```python
required_modules = [
    "imageio_ffmpeg",
    "numpy",
    "pywhispercpp",
    "audio_separator",
    "audio_separator.separator",
    "onnxruntime",
    "torch",
    "torchaudio",
    "torchaudio.pipelines",
]

missing = [name for name in required_modules if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit(f"Missing Python modules after install: {', '.join(missing)}")

from torchaudio.pipelines import MMS_FA
import torch
import torchaudio


def _major_minor(version: str) -> tuple[int, int]:
    clean = version.split("+", 1)[0]
    major, minor, *_ = clean.split(".")
    return int(major), int(minor)


if _major_minor(torch.__version__) != _major_minor(torchaudio.__version__):
    raise SystemExit(
        "torch and torchaudio major/minor versions must match: "
        f"torch={torch.__version__}, torchaudio={torchaudio.__version__}"
    )

_ = MMS_FA.get_labels()
```

**Step 5: Run verification**

Run:

```bash
python -m unittest tests.test_install_script -v
./scripts/install_linux_local_engine.sh
.venv/bin/python -m pip check
```

Expected:

- tests pass;
- installer completes;
- `pip check` reports no broken requirements.

**Step 6: Commit**

```bash
git add requirements.txt scripts/install_linux_local_engine.sh tests/test_install_script.py
git commit -m "chore: add torchaudio alignment dependency"
```

---

### Task 2: Add Phoneme Data Model To Local Transcript

**Files:**
- Modify: `louvorja_slides/transcription.py`
- Test: `tests/test_transcription_models.py`

**Step 1: Write the failing test**

Add to `tests/test_transcription_models.py`:

```python
def test_transcript_preserves_optional_phonemes_in_json(self) -> None:
    transcript = Transcript(
        words=[TranscribedWord(text="Fala", start=1.0, end=1.4, source="whisper")],
        detected_language="pt",
        duration_seconds=3.0,
        phonemes=[
            TranscribedPhoneme(
                symbol="f",
                start=1.0,
                end=1.1,
                parent_word_idx=0,
                source="mms_align",
            )
        ],
    )

    self.assertEqual(Transcript.from_dict(transcript.to_dict()), transcript)
```

Add import:

```python
from louvorja_slides.transcription import Transcript, TranscribedPhoneme, TranscribedWord
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_transcription_models -v
```

Expected: FAIL because `TranscribedPhoneme` does not exist and `Transcript` has no `phonemes`.

**Step 3: Implement minimal model**

In `louvorja_slides/transcription.py`, add:

```python
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
```

Update `Transcript`:

```python
@dataclass(frozen=True)
class Transcript:
    words: list[TranscribedWord]
    detected_language: str | None
    duration_seconds: float
    phonemes: list[TranscribedPhoneme] | None = None
```

Update `to_dict()`:

```python
"phonemes": [phoneme.to_dict() for phoneme in self.phonemes]
if self.phonemes is not None
else None,
```

Update `from_dict()`:

```python
raw_phonemes = data.get("phonemes")
phonemes = (
    [TranscribedPhoneme.from_dict(item) for item in raw_phonemes if isinstance(item, dict)]
    if isinstance(raw_phonemes, list)
    else None
)
```

Pass `phonemes=phonemes` into `Transcript(...)`.

**Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m unittest tests.test_transcription_models -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add louvorja_slides/transcription.py tests/test_transcription_models.py
git commit -m "feat: preserve phoneme alignment data"
```

---

### Task 3: Convert MMS Spans Into Words And Phonemes

**Files:**
- Modify: `louvorja_slides/alignment.py`
- Test: `tests/test_alignment.py`

**Step 1: Write the failing test**

Add to `tests/test_alignment.py`:

```python
def test_refine_transcript_from_spans_returns_phonemes(self) -> None:
    transcript = Transcript(
        words=[TranscribedWord("Fala", 10.0, 11.0, source="whisper")],
        detected_language="pt",
        duration_seconds=20.0,
    )
    spans = [
        {"text": "f", "word_idx": 0, "start_frame": 50, "end_frame": 54},
        {"text": "a", "word_idx": 0, "start_frame": 55, "end_frame": 70},
    ]

    refined = refine_transcript_from_spans(transcript, spans, frame_seconds=0.02)

    self.assertEqual(refined.words[0].start, 1.0)
    self.assertEqual(refined.words[0].end, 1.42)
    self.assertEqual(refined.words[0].source, "mms_align")
    self.assertEqual(len(refined.phonemes or []), 2)
    self.assertEqual((refined.phonemes or [])[0].symbol, "f")
    self.assertEqual((refined.phonemes or [])[0].parent_word_idx, 0)
```

Update import:

```python
from louvorja_slides.alignment import (
    AlignmentError,
    MmsForcedAligner,
    refine_transcript_from_spans,
    refine_words_from_spans,
    sanitize_for_mms,
)
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_alignment -v
```

Expected: FAIL because `refine_transcript_from_spans` does not exist.

**Step 3: Implement span conversion**

In `louvorja_slides/alignment.py`, import `TranscribedPhoneme`:

```python
from louvorja_slides.transcription import Transcript, TranscribedPhoneme, TranscribedWord
```

Add:

```python
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
```

Update `MmsForcedAligner.align_transcript()` to return `refine_transcript_from_spans(...)` instead of manually constructing `Transcript`.

**Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m unittest tests.test_alignment -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add louvorja_slides/alignment.py tests/test_alignment.py
git commit -m "feat: return phoneme spans from alignment"
```

---

### Task 4: Port Titan's Chunked MMS Emission Stitching

**Files:**
- Modify: `louvorja_slides/alignment.py`
- Test: `tests/test_alignment.py`

**Step 1: Write failing chunking tests**

Add these tests to `tests/test_alignment.py`. They mirror Titan's tests but use `unittest`.

```python
@unittest.skipUnless(importlib.util.find_spec("torch"), "torch not installed")
def test_generate_emissions_short_audio_uses_single_forward(self) -> None:
    import torch
    from unittest.mock import MagicMock

    fake_emissions = torch.zeros(1, 500, 32)
    fake_model = MagicMock(return_value=(fake_emissions, None))
    aligner = MmsForcedAligner(model=fake_model, tokenizer=object(), blank_id=0)

    result = aligner.generate_emissions(torch.zeros(10 * 16000))

    self.assertEqual(fake_model.call_count, 1)
    self.assertEqual(tuple(result.shape), (1, 500, 32))
```

Add:

```python
@unittest.skipUnless(importlib.util.find_spec("torch"), "torch not installed")
def test_generate_emissions_long_audio_chunks_and_stitches(self) -> None:
    import torch
    from unittest.mock import MagicMock

    def fake_forward(batch):
        return torch.zeros(batch.shape[0], 1700, 32), None

    fake_model = MagicMock(side_effect=fake_forward)
    aligner = MmsForcedAligner(model=fake_model, tokenizer=object(), blank_id=0)

    result = aligner.generate_emissions(
        torch.zeros(90 * 16000),
        window_seconds=30.0,
        context_seconds=2.0,
        batch_size=1,
    )

    self.assertEqual(fake_model.call_count, 3)
    self.assertEqual(tuple(result.shape), (1, 4500, 32))
```

Add imports:

```python
import importlib.util
from unittest.mock import MagicMock
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_alignment -v
```

Expected: FAIL because `MmsForcedAligner` does not accept `model/tokenizer/blank_id` and has no `generate_emissions()`.

**Step 3: Update aligner constructor**

Update `MmsForcedAligner.__init__`:

```python
def __init__(
    self,
    run_forced_align: Callable[[Any, list[TranscribedWord], str], list[dict[str, Any]]] | None = None,
    frame_seconds: float = 0.02,
    model: Any | None = None,
    tokenizer: Any | None = None,
    blank_id: int | None = None,
    device: str | None = None,
) -> None:
    self._run_forced_align = run_forced_align
    self._frame_seconds = frame_seconds
    self._model = model
    self._tokenizer = tokenizer
    self._blank_id = 0 if blank_id is None else blank_id
    self._device = device or "cpu"
```

**Step 4: Port emission stitching**

Add constants:

```python
_SAMPLE_RATE = 16000
_FRAME_SAMPLES = 320
_FRAME_SECONDS = _FRAME_SAMPLES / _SAMPLE_RATE
_CHUNK_WINDOW_SECONDS = 30.0
_CHUNK_CONTEXT_SECONDS = 2.0
```

Add method:

```python
def generate_emissions(
    self,
    waveform_1d: Any,
    *,
    window_seconds: float = _CHUNK_WINDOW_SECONDS,
    context_seconds: float = _CHUNK_CONTEXT_SECONDS,
    batch_size: int = 1,
) -> Any:
    import math
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
    if context_frames > 0:
        stitched = stitched[:, context_frames:-context_frames, :]
    stitched = stitched.flatten(0, 1)

    extension_frames = int(round((extension / _SAMPLE_RATE) / _FRAME_SECONDS))
    if extension_frames > 0:
        stitched = stitched[:-extension_frames]

    return stitched.unsqueeze(0)
```

**Step 5: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m unittest tests.test_alignment -v
```

Expected: PASS with the torch-gated chunking tests executed, not skipped.

**Step 6: Commit**

```bash
git add louvorja_slides/alignment.py tests/test_alignment.py
git commit -m "feat: stitch chunked mms emissions"
```

---

### Task 5: Port Real MMS Forced Alignment Runner

**Files:**
- Modify: `louvorja_slides/alignment.py`
- Test: `tests/test_alignment.py`

**Step 1: Write tokenizer path tests**

Add to `tests/test_alignment.py`:

```python
def test_build_mms_targets_preserves_original_word_indices(self) -> None:
    class FakeTokenizer:
        def __call__(self, words: list[str]) -> list[list[int]]:
            self.words = words
            return [[10, 11], [12], [20]]

    tokenizer = FakeTokenizer()
    words = [
        TranscribedWord("Não", 0.0, 0.1),
        TranscribedWord("[Música]", 0.2, 0.3),
        TranscribedWord("temas", 0.4, 0.5),
    ]

    tokens_per_word, target_tokens = build_mms_targets(words, tokenizer)

    self.assertEqual(tokenizer.words, ["nao", "musica", "temas"])
    self.assertEqual(tokens_per_word, [[10, 11], [12], [20]])
    self.assertEqual(target_tokens, [10, 11, 12, 20])
```

If bracketed tokens are filtered before alignment, adjust this expected value to match the chosen behavior. Recommended behavior: align every sanitized non-empty word in the transcript; special bracket tokens are filtered by `LocalWhisperTranscriber`.

Update the existing `louvorja_slides.alignment` import in `tests/test_alignment.py`:

```python
from louvorja_slides.alignment import (
    AlignmentError,
    MmsForcedAligner,
    attach_spans_to_words,
    build_mms_targets,
    collapse_alignment_path,
    refine_transcript_from_spans,
    refine_words_from_spans,
    sanitize_for_mms,
)
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_alignment -v
```

Expected: FAIL because `build_mms_targets` does not exist.

**Step 3: Implement target construction**

In `louvorja_slides/alignment.py`, add:

```python
def build_mms_targets(
    words: list[TranscribedWord],
    tokenizer: Any,
) -> tuple[list[list[int]], list[int]]:
    sanitized_words = [sanitize_for_mms(word.text) for word in words]
    non_empty_pairs = [(index, text) for index, text in enumerate(sanitized_words) if text]
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
```

**Step 4: Port `_run_forced_align`**

Implement `MmsForcedAligner._load_bundle()`:

```python
def _load_bundle(self) -> None:
    try:
        import torch
        from torchaudio.pipelines import MMS_FA
    except ImportError as exc:
        raise AlignmentUnavailableError(
            "torchaudio with MMS_FA is not installed; run scripts/install_linux_local_engine.sh "
            "or use `--alignment none`."
        ) from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    bundle = MMS_FA
    self._model = bundle.get_model().to(device).train(False)
    self._tokenizer = bundle.get_tokenizer()
    self._blank_id = getattr(self._tokenizer, "blank_id", 0)
    self._device = device
```

Implement `_run_forced_align()` using decoded samples:

```python
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
    return attach_spans_to_words(spans, tokens_per_word, self._tokenizer)
```

Then update `_run()`:

```python
if self._run_forced_align is not None:
    return self._run_forced_align(samples, words, language)
return self._run_real_forced_align(samples, words, language)
```

Also implement helpers `collapse_alignment_path()` and `attach_spans_to_words()` based on Titan's `torchaudio_align.py`.

**Step 5: Add helper unit tests**

Add tests for `collapse_alignment_path()`:

```python
def test_collapse_alignment_path_skips_blanks_and_groups_runs(self) -> None:
    spans = collapse_alignment_path([0, 1, 1, 0, 2, 2, 2], blank_id=0)

    self.assertEqual(
        spans,
        [
            {"_tok": 1, "start_frame": 1, "end_frame": 2},
            {"_tok": 2, "start_frame": 4, "end_frame": 6},
        ],
    )
```

Add tests for `build_mms_targets()` tokenizer rejection and `attach_spans_to_words()` word-index preservation:

```python
def test_build_mms_targets_skips_only_rejected_words(self) -> None:
    class PartiallyRejectingTokenizer:
        def __call__(self, words: list[str]) -> list[list[int]]:
            if words == ["ruim"]:
                raise KeyError(words[0])
            return [[{"fala": 10, "senhor": 20}[words[0]]]]

    tokens_per_word, target_tokens = build_mms_targets(
        [
            TranscribedWord("Fala", 0.0, 0.5),
            TranscribedWord("ruim", 0.5, 1.0),
            TranscribedWord("Senhor", 1.0, 1.5),
        ],
        PartiallyRejectingTokenizer(),
    )

    self.assertEqual(tokens_per_word, [[10], [], [20]])
    self.assertEqual(target_tokens, [10, 20])


def test_build_mms_targets_reports_when_all_words_are_rejected(self) -> None:
    class RejectingTokenizer:
        def __call__(self, words: list[str]) -> list[list[int]]:
            raise KeyError(words[0])

    with self.assertRaisesRegex(AlignmentError, "rejected all sanitized words"):
        build_mms_targets([TranscribedWord("Fala", 0.0, 0.5)], RejectingTokenizer())


def test_attach_spans_to_words_preserves_empty_word_offsets(self) -> None:
    class FakeTokenizer:
        def decode(self, tokens: list[int]) -> str:
            return {10: "f", 20: "t"}[tokens[0]]

    spans = [
        {"_tok": 10, "start_frame": 1, "end_frame": 2},
        {"_tok": 20, "start_frame": 7, "end_frame": 8},
    ]

    attached = attach_spans_to_words(spans, [[10], [], [20]], FakeTokenizer())

    self.assertEqual([span["word_idx"] for span in attached], [0, 2])
    self.assertEqual([span["text"] for span in attached], ["f", "t"])


def test_attach_spans_to_words_uses_labels_without_decode_api(self) -> None:
    spans = [
        {"_tok": 24, "start_frame": 1, "end_frame": 2},
        {"_tok": 3, "start_frame": 7, "end_frame": 8},
    ]
    labels = [""] * 29
    labels[3] = "e"
    labels[24] = "f"

    attached = attach_spans_to_words(
        spans,
        [[24, 3]],
        tokenizer=object(),
        labels=labels,
    )

    self.assertEqual([span["text"] for span in attached], ["f", "e"])
```

Note: the real `MMS_FA` tokenizer does not expose `decode()`. Use `MMS_FA.get_labels()` to map token IDs back to phoneme symbols, and only fall back to numeric strings when labels are unavailable.

**Step 6: Run tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_alignment -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add louvorja_slides/alignment.py tests/test_alignment.py
git commit -m "feat: run real mms forced alignment"
```

---

### Task 6: Make Pipeline Cache And Quality Gate Alignment-Aware

**Files:**
- Modify: `louvorja_slides/local_pipeline.py`
- Modify: `louvorja_slides/quality.py`
- Test: `tests/test_local_pipeline.py`
- Test: `tests/test_quality.py`

**Step 1: Write cache regression test**

Add to `tests/test_local_pipeline.py`:

```python
def test_pipeline_cache_distinguishes_phoneme_schema_for_aligned_transcripts(self) -> None:
    events: list[str] = []

    def fake_decode(audio_path: Path) -> object:
        events.append("decode")
        return type(
            "Decoded",
            (),
            {
                "samples": np.zeros(16000, dtype=np.float32),
                "sample_rate": 16000,
                "duration_seconds": 10.0,
            },
        )()

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
                detected_language=transcript.detected_language,
                duration_seconds=transcript.duration_seconds,
                phonemes=[
                    TranscribedPhoneme(
                        symbol="f",
                        start=1.1,
                        end=1.2,
                        parent_word_idx=0,
                        source="mms_align",
                    )
                ],
            )

    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "song.mp3"
        audio.write_bytes(b"audio")
        cache_root = Path(tmp) / ".cache"
        audio_id = audio_sha256(audio)
        config = LocalPipelineConfig(
            cache_root=cache_root,
            whisper_model="medium",
            vocal_separation="none",
            alignment="mms",
        )

        schema_2_variant = cache_key(
            {
                "schema": 2,
                "sample_rate": 16000,
                "whisper_token_timestamps": True,
                "whisper_max_len": 1,
                "whisper_split_on_word": True,
                "whisper_entropy_thold": 2.2,
                "whisper_no_speech_thold": 0.7,
                "stage": "aligned",
                "language": config.language,
                "whisper_model": config.whisper_model,
                "vocal_separation": config.vocal_separation,
                "alignment": config.alignment,
            }
        )
        save_json(
            cache_path(cache_root, audio_id, "transcript", schema_2_variant),
            Transcript(
                words=[TranscribedWord("Fala", 9.0, 9.0, source="old_cache")],
                detected_language="pt",
                duration_seconds=10.0,
                phonemes=[
                    TranscribedPhoneme(
                        symbol="24",
                        start=9.0,
                        end=9.1,
                        parent_word_idx=0,
                        source="mms_align",
                    )
                ],
            ).to_dict(),
        )

        transcript = transcribe_audio_local(
            audio,
            config=config,
            decode_fn=fake_decode,
            transcriber=FakeTranscriber(),
            aligner=FakeAligner(),
        )

        current_variant = local_pipeline._variant(
            stage="aligned",
            language=config.language,
            whisper_model=config.whisper_model,
            vocal_separation=config.vocal_separation,
            alignment=config.alignment,
        )
        cached = load_json(cache_path(cache_root, audio_id, "transcript", current_variant))

    self.assertEqual(events, ["decode", "whisper", "align"])
    self.assertEqual(len(transcript.phonemes or []), 1)
    self.assertIsInstance((cached or {}).get("phonemes"), list)
```

Add imports:

```python
from louvorja_slides.cache import audio_sha256, cache_key, cache_path, load_json, save_json
from louvorja_slides import local_pipeline
from louvorja_slides.transcription import Transcript, TranscribedPhoneme, TranscribedWord
```

This test seeds a schema-2 aligned transcript with numeric phoneme symbols, then proves the schema-3 pipeline ignores that stale cache, calls the aligner, and writes a label-bearing aligned cache.

**Step 2: Bump local cache schema**

In `louvorja_slides/local_pipeline.py`, update:

```python
_CACHE_SCHEMA_VERSION = 3
```

Reason: transcript JSON now can include label-bearing `phonemes`; old aligned caches without phonemes or with numeric token IDs must not masquerade as complete alignment output.

**Step 3: Update transcript quality**

In `tests/test_quality.py`, add:

```python
def test_aligned_transcript_with_positive_gaps_passes_timestamp_quality(self) -> None:
    transcript = Transcript(
        words=[
            TranscribedWord("Fala", 1.00, 1.20, source="mms_align"),
            TranscribedWord("comigo", 1.32, 1.70, source="mms_align"),
            TranscribedWord("Senhor", 2.10, 2.50, source="mms_align"),
        ],
        detected_language="pt",
        duration_seconds=3.0,
    )

    report = analyze_transcript_quality(transcript)

    self.assertTrue(report.acceptable, report.messages)
```

**Step 4: Run tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_local_pipeline tests.test_quality -v
```

Expected: PASS after schema bump and no quality code changes unless current thresholds need adjustment.

**Step 5: Commit**

```bash
git add louvorja_slides/local_pipeline.py tests/test_local_pipeline.py tests/test_quality.py
git commit -m "chore: make local cache alignment-aware"
```

---

### Task 7: Add A Real Alignment Smoke Script

**Files:**
- Create: `scripts/smoke_mms_alignment.py`
- Test: no unit test; verify syntax and one real MMS run.

**Step 1: Create script**

Create `scripts/smoke_mms_alignment.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from louvorja_slides.alignment import MmsForcedAligner
from louvorja_slides.audio import decode_audio_16k_mono
from louvorja_slides.transcription import Transcript, TranscribedWord


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test MMS alignment on a short audio file")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--words", required=True, help="Whitespace-separated transcript text")
    parser.add_argument("--language", default="pt")
    args = parser.parse_args()

    decoded = decode_audio_16k_mono(args.audio)
    tokens = args.words.split()
    words = [
        TranscribedWord(text=token, start=index * 0.5, end=index * 0.5 + 0.2, source="manual")
        for index, token in enumerate(tokens)
    ]
    transcript = Transcript(
        words=words,
        detected_language=args.language,
        duration_seconds=decoded.duration_seconds,
    )

    aligned = MmsForcedAligner().align_transcript(
        transcript,
        samples=decoded.samples,
        language=args.language,
    )

    print(f"words={len(aligned.words)} phonemes={len(aligned.phonemes or [])}")
    for word in aligned.words[:20]:
        print(f"{word.start:.2f}-{word.end:.2f} {word.text} {word.source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 2: Verify syntax**

Run:

```bash
.venv/bin/python -m py_compile scripts/smoke_mms_alignment.py
```

Expected: exit code 0.

**Step 3: Run the smoke script through real MMS alignment**

Use a bounded clip from the named real song so the smoke validates model loading, tokenizer, `forced_align`, tensor shapes, and phoneme output without committing generated artifacts:

```bash
mkdir -p local_outputs
FFMPEG="$(
  .venv/bin/python - <<'PY'
import imageio_ffmpeg
print(imageio_ffmpeg.get_ffmpeg_exe())
PY
)"
"$FFMPEG" -y -ss 30 -t 8 -i "ADORADORES 3 - FÉ E AÇÃO.mp3" \
  -vn -ac 1 -ar 16000 local_outputs/smoke-mms-alignment.wav
.venv/bin/python scripts/smoke_mms_alignment.py \
  local_outputs/smoke-mms-alignment.wav \
  --words "fé e ação" \
  --language pt | tee local_outputs/smoke-mms-alignment.txt
grep -E 'phonemes=[1-9][0-9]*' local_outputs/smoke-mms-alignment.txt
```

Expected: the smoke command exits 0 and prints a nonzero `phonemes=` count. If the smoke cannot produce phonemes, fix the MMS path before committing this task.

**Step 4: Commit**

```bash
git add scripts/smoke_mms_alignment.py
git commit -m "chore: add mms alignment smoke script"
```

---

### Task 8: Run Real Song With Alignment And Compare Metrics

**Files:**
- No source changes unless a bug is found.
- Generated files stay under ignored `local_outputs/` and `.louvorja-cache/`.

**Step 1: Run full command**

Run:

```bash
CACHE_DIR=local_outputs/adoradores3-mms-cache
rm -rf "$CACHE_DIR"
mkdir -p "$CACHE_DIR"
.venv/bin/python audio_to_slja.py "ADORADORES 3 - FÉ E AÇÃO.mp3" \
  --engine local \
  --vocal-separation htdemucs_ft \
  --alignment mms \
  --whisper-model medium \
  --cache-dir "$CACHE_DIR" \
  --quality-gate fail \
  --output local_outputs/adoradores3-fe-acao-mms.slja \
  --title "Fé e Ação"
```

Expected:

- First run can download MMS model weights and take several minutes on CPU.
- If gate passes, `local_outputs/adoradores3-fe-acao-mms.slja` is written.
- If gate fails, capture exact metrics and do not claim improvement.

**Step 2: Extract quality metrics**

Run:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from collections import Counter
import json

from louvorja_slides import local_pipeline
from louvorja_slides.cache import audio_sha256, cache_path
from louvorja_slides.quality import analyze_transcript_quality
from louvorja_slides.transcription import Transcript

audio_path = Path("ADORADORES 3 - FÉ E AÇÃO.mp3")
cache_root = Path("local_outputs/adoradores3-mms-cache")
audio_id = audio_sha256(audio_path)
variant = local_pipeline._variant(
    stage="aligned",
    language="pt",
    whisper_model="medium",
    vocal_separation="htdemucs_ft",
    alignment="mms",
)
path = cache_path(cache_root, audio_id, "transcript", variant)
if not path.exists():
    raise SystemExit(f"Expected aligned transcript cache not found: {path}")

transcript = Transcript.from_dict(json.loads(path.read_text()))
report = analyze_transcript_quality(transcript)
source_counts = Counter(word.source for word in transcript.words)
if not transcript.phonemes:
    raise SystemExit(f"Expected phonemes in aligned transcript cache: {path}")
if source_counts.get("mms_align", 0) <= len(transcript.words) // 2:
    raise SystemExit(f"Expected most words from mms_align, got {dict(source_counts)}")

print(path)
print("words", report.word_count)
print("zero_duration", f"{report.zero_duration_word_ratio:.1%}")
print("positive_gap", f"{report.positive_gap_ratio:.1%}")
print("phonemes", len(transcript.phonemes or []))
print("sources", dict(source_counts))
print("messages", report.messages)
PY
```

Expected target:

- `zero_duration` below `2.0%`;
- `positive_gap` at or above `5.0%`;
- `phonemes > 0`;
- source counts show most or all words as `mms_align`.

**Step 3: Commit only source/test changes**

Do not commit:

- `ADORADORES 3 - FÉ E AÇÃO.mp3`;
- `.louvorja-cache/`;
- `local_outputs/`;
- generated `.slja`.

---

### Task 9: Optional Phase 2, Syllables For Titan-Level Placement

This task is not required for slide timestamps. Do it after MMS word alignment is proven.

**Files:**
- Create: `louvorja_slides/syllables.py`
- Modify: `louvorja_slides/transcription.py`
- Test: `tests/test_syllables.py`

**Step 1: Add `TranscribedSyllable`**

Model shape:

```python
@dataclass(frozen=True)
class TranscribedSyllable:
    text: str
    start: float
    end: float
    parent_word_idx: int
    phoneme_indices: list[int]
    is_stressed: bool = False
    confidence: float = 1.0
```

**Step 2: Port Titan's phoneme syllabifier**

Copy the smallest useful subset of:

- `syllabify_word()`
- `_phoneme_is_vowel()`
- `_phoneme_stress_level()`
- `syllabify_word_from_phonemes()`

from `/home/henry/titan-chordpro-lib/titan_chordpro/fusion/syllabifier.py`.

**Step 3: Add tests from Titan**

Port representative tests:

- PT `amigo` with IPA phonemes produces 3 syllables and stress on the middle.
- no vowels returns one syllable.
- empty phoneme list returns one syllable spanning the word.

**Step 4: Decide whether slides need syllables**

For `.slja` lyric slides, do not use syllables without a concrete layout requirement. Preserve them for future chord/cue placement only.

---

## Final Verification

Run:

```bash
.venv/bin/python -m compileall audio_to_slja.py louvorja_slides tests scripts
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
git diff --check
```

Expected:

- compileall exits 0;
- all tests pass;
- no broken Python requirements;
- no whitespace errors.

Then run the real-song command from Task 8 and report the exact quality metrics.

## Success Criteria

- `--alignment mms` runs without injected test aligner.
- Aligned transcript cache includes `phonemes`.
- Aligned words have `source="mms_align"`.
- Real song no longer has `positive_gap_ratio 0.0%`.
- Gate failure, if any, is due primarily to layout/readability rather than timestamp quality.
- Generated `.slja` is only considered acceptable when `--quality-gate fail` writes it successfully.
