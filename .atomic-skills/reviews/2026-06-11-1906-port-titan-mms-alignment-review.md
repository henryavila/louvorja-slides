---
date: 2026-06-11T19:06:33-03:00
topic: port-titan-mms-alignment
artifact: docs/plans/2026-06-11-port-titan-mms-alignment.md
skill: review-plan
reviewer: gpt-5-codex
codex_version: codex-cli 0.139.0
final_verdict: needs_changes
counts_final: {blocker: 0, critical: 0, major: 5, minor: 0, nit: 0}
counts_blind: {blocker: 0, critical: 0, major: 5, minor: 0, nit: 0}
framing_delta: {dropped: 0, maintained: 5, emerged: 0}
schema_version: "1.0"
---

# Cross-Model Review - port-titan-mms-alignment

## Local self-loop fixes applied before Codex

- Local finding L-001 [major]: Task 5 tokenizer fixture returned two token lists for three sanitized words, which contradicted the expected target list. Applied: changed fake tokenizer to return `[[10, 11], [12], [20]]`, expected `tokens_per_word`, and `target_tokens`.
- Local finding L-002 [major]: Task 5 added helper tests without updating the alignment import block. Applied: added `attach_spans_to_words`, `build_mms_targets`, and `collapse_alignment_path` to the planned import block.
- Local finding L-003 [major]: Task 6 cache regression only proved `_variant()` returns a string. Applied: made the test fail on the schema version before the bump.
- Local finding L-004 [major]: tests that need torch could be skipped by system `python`; the venv has `torch==2.12.0` while system Python does not. Applied: changed alignment and final verification commands to `.venv/bin/python` and required torch-gated tests to execute.
- Local finding L-005 [major]: Task 8 metrics did not print word source distribution. Applied: added `Counter(word.source ...)` output.
- Local finding L-006 [minor]: G2 soft-language occurrences were present. Applied: removed/reworded the occurrences found by the ban-list grep.
- Local finding L-007 [minor]: plan had source claims without anchors. Applied: added `Verified Source Anchors` for the central Titan and local-audio claims.


## Self-review against code-quality gates

- G1 read-before-claim: checked existing-code claims against local files and Titan source. Added source anchors at plan lines 13-18. Residual G1-sensitive assertions remain in implementation steps where they quote intended changes rather than existing source.
- G2 soft-language: ran `rg` against `should|probably|may|typically|usually|I think|it seems|in theory|tends to`; after edits, no soft-language hits remained outside command text.
- G6 reference-or-strike: plan contains 6 `verified_by:` anchors and 0 `unverified:` markers. The strict every-assertion rule is not fully satisfied across the whole task plan; final status remains needs_changes due the Codex major findings.
- Initiative-depth: N/A. The reviewed file has no YAML frontmatter `phases:` array and no materialized initiative files were discovered.


## Pass 1 (blind)

---
verdict: needs_changes
counts: {blocker: 0, critical: 0, major: 5, minor: 0, nit: 0}
reviewer: gpt-5-codex
pass: blind
schema_version: "1.0"
---

## Summary
The plan is executable as a task list, but it leaves several verification and failure-mode gaps that can produce a green unit suite while the real MMS path remains broken or unverifiable. The main risks are dependency determinism, all-or-nothing tokenizer failure, weak cache regression coverage, a non-running “smoke” step, and metric extraction that can report the wrong cached transcript.

## Findings

### F-001 [major] dependency — docs/plans/2026-06-11-port-titan-mms-alignment.md:80-89

**Evidence:**
```md
imageio-ffmpeg==0.6.0
numpy==2.4.6
pywhispercpp==1.5.0
audio-separator==0.44.2
onnxruntime==1.26.0
torchaudio==2.12.0
```

**Claim:** The plan pins `torchaudio` but does not directly pin or verify the matching `torch` version it says the install relies on.

**Impact:** A resolver or transitive dependency change can install a torch build/version that does not match the torchaudio binary, causing `import torchaudio`, `MMS_FA`, or model execution to fail after the dependency task appears complete.

**Recommendation:** Add an explicit `torch==2.12.0` pin or constraints entry, and extend installer verification to assert `torch.__version__` and `torchaudio.__version__` share the required major/minor pair.

**Confidence:** medium

---

### F-002 [major] failure-mode — docs/plans/2026-06-11-port-titan-mms-alignment.md:647-651

**Evidence:**
```py
    try:
        compact_tokens = tokenizer(non_empty_words)
    except KeyError:
        return [[] for _ in words], []
```

**Claim:** A single tokenizer rejection discards the entire target sequence instead of isolating or reporting the offending word.

**Impact:** One unexpected sanitized token causes the whole song to produce no alignment targets; the later real-song run can fail without aligned words or phonemes, and the plan has no partial-alignment fallback or diagnostic that identifies the bad transcript token.

**Recommendation:** Tokenize per word or retry by dropping only rejected words, preserve original word indices with empty token lists for rejected items, and raise an explicit error only when no alignable targets remain.

**Confidence:** high

---

### F-003 [major] coverage — docs/plans/2026-06-11-port-titan-mms-alignment.md:818-836

**Evidence:**
```py
def test_pipeline_cache_distinguishes_phoneme_schema_for_aligned_transcripts(self) -> None:
    config = LocalPipelineConfig(
        cache_root=Path(".cache"),
        whisper_model="medium",
        vocal_separation="htdemucs_ft",
        alignment="mms",
    )

    self.assertEqual(local_pipeline._CACHE_SCHEMA_VERSION, 2)

    first = local_pipeline._variant(
        stage="aligned",
        language=config.language,
        whisper_model=config.whisper_model,
        vocal_separation=config.vocal_separation,
        alignment=config.alignment,
    )

    self.assertIsInstance(first, str)
```

**Claim:** The cache regression test does not exercise cache reads, cache writes, old schema isolation, or phoneme presence.

**Impact:** The implementation can pass this test while still loading a stale aligned transcript without phonemes, because the test only checks a constant and that `_variant()` returns a string.

**Recommendation:** Replace or extend the test to seed a schema-1 aligned transcript cache without phonemes, run `transcribe_audio_local(... alignment="mms")`, assert the aligner is called, and assert the saved schema-2 aligned cache contains `phonemes`.

**Confidence:** high

---

### F-004 [major] verification — docs/plans/2026-06-11-port-titan-mms-alignment.md:954-962

**Evidence:**
```md
**Step 2: Verify syntax**

Run:

```bash
.venv/bin/python -m py_compile scripts/smoke_mms_alignment.py
```

Expected: exit code 0.
```

**Claim:** The “real alignment smoke script” task only verifies Python syntax and never runs the script through `MmsForcedAligner`.

**Impact:** Missing model loading, tokenizer, `forced_align`, tensor shape, and runtime dependency failures are deferred until the full real-song run after multiple commits, making the smoke task a false gate for the real MMS path.

**Recommendation:** Add a smoke execution step against a short checked-in or generated audio fixture with known words, and require nonzero aligned phoneme count before committing the smoke-script task.

**Confidence:** high

---

### F-005 [major] verification — docs/plans/2026-06-11-port-titan-mms-alignment.md:1013-1023

**Evidence:**
```py
paths = sorted(Path(".louvorja-cache").glob("*/transcript/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
for path in paths[:1]:
    transcript = Transcript.from_dict(json.loads(path.read_text()))
    report = analyze_transcript_quality(transcript)
    print(path)
    print("words", report.word_count)
    print("zero_duration", f"{report.zero_duration_word_ratio:.1%}")
    print("positive_gap", f"{report.positive_gap_ratio:.1%}")
    print("phonemes", len(transcript.phonemes or []))
    print("sources", dict(Counter(word.source for word in transcript.words)))
    print("messages", report.messages)
```

**Claim:** The metrics extraction script selects the newest transcript cache globally rather than the cache entry produced by the Task 8 command.

**Impact:** If alignment fails before writing its cache, or if another transcript was touched more recently, the report can use a raw, stale, or wrong-configuration transcript and falsely satisfy or fail the success criteria.

**Recommendation:** Run Task 8 with a fresh temporary `--cache-dir`, or compute the expected audio id and aligned variant path, then assert the selected transcript has `phonemes > 0` and mostly `source="mms_align"` before printing quality metrics.

**Confidence:** high

## Questions (non-findings)

- docs/plans/2026-06-11-port-titan-mms-alignment.md:89 — Is `torch==2.12.0` available from the intended package index for every supported Linux/WSL install target, or is a CPU/CUDA-specific index required?

## Out of scope

- Titan chord recognition, beat tracking, and ChordPro writer behavior.
- Whether syllables should be used for LouvorJA lyric slide layout.

## Pass 2 (informed)

---
verdict: needs_changes
counts: {blocker: 0, critical: 0, major: 5, minor: 0, nit: 0}
reviewer: gpt-5-codex
pass: informed
schema_version: "1.0"
---

## Summary
The informed constraints strengthen the dependency finding: the plan relies on a currently observed torch resolution even though the package metadata does not pin torch to the required version. The remaining risks still stand: a tokenizer failure can erase the full alignment target, the cache regression does not prove stale aligned caches are bypassed, the smoke-script task does not run the MMS path, and the metrics extractor can report the wrong cache entry.

## Findings

### F-001 [major] dependency — docs/plans/2026-06-11-port-titan-mms-alignment.md:80-89

**Evidence:**
```md
```text
imageio-ffmpeg==0.6.0
numpy==2.4.6
pywhispercpp==1.5.0
audio-separator==0.44.2
onnxruntime==1.26.0
torchaudio==2.12.0
```

Reason: the current Linux install resolved `torch==2.12.0` through `audio-separator`. `torchaudio` must match the installed torch major/minor version.
```

**Claim:** The plan relies on the current environment's torch resolution instead of pinning or verifying torch, even though `audio-separator==0.44.2` only requires `torch >=2.3`.

**Impact:** A fresh install can resolve a torch version that satisfies `audio-separator` but is not the version required by `torchaudio==2.12.0`, causing import, MMS bundle loading, or model execution failures after Task 1 appears complete.

**Recommendation:** Add an explicit `torch==2.12.0` pin or constraints entry, and extend installer verification to assert `torch.__version__` and `torchaudio.__version__` share the required major/minor pair.

**Confidence:** high

---

### F-002 [major] failure-mode — docs/plans/2026-06-11-port-titan-mms-alignment.md:647-651

**Evidence:**
```py
    non_empty_words = [text for _, text in non_empty_pairs]
    try:
        compact_tokens = tokenizer(non_empty_words)
    except KeyError:
        return [[] for _ in words], []
```

**Claim:** A single tokenizer rejection discards the entire target sequence instead of isolating or reporting the offending word.

**Impact:** One unexpected sanitized token causes the whole song to produce no alignment targets; the later real-song run can fail without aligned words or phonemes, and the plan has no partial-alignment fallback or diagnostic that identifies the bad transcript token.

**Recommendation:** Tokenize per word or retry by dropping only rejected words, preserve original word indices with empty token lists for rejected items, and raise an explicit error only when no alignable targets remain.

**Confidence:** high

---

### F-003 [major] coverage — docs/plans/2026-06-11-port-titan-mms-alignment.md:818-836

**Evidence:**
```py
def test_pipeline_cache_distinguishes_phoneme_schema_for_aligned_transcripts(self) -> None:
    config = LocalPipelineConfig(
        cache_root=Path(".cache"),
        whisper_model="medium",
        vocal_separation="htdemucs_ft",
        alignment="mms",
    )

    self.assertEqual(local_pipeline._CACHE_SCHEMA_VERSION, 2)

    first = local_pipeline._variant(
        stage="aligned",
        language=config.language,
        whisper_model=config.whisper_model,
        vocal_separation=config.vocal_separation,
        alignment=config.alignment,
    )

    self.assertIsInstance(first, str)
```

**Claim:** The cache regression test does not exercise cache reads, cache writes, old schema isolation, or phoneme presence.

**Impact:** The implementation can pass this test while still loading a stale aligned transcript without phonemes, because the test only checks a constant and that `_variant()` returns a string.

**Recommendation:** Replace or extend the test to seed a schema-1 aligned transcript cache without phonemes, run `transcribe_audio_local(... alignment="mms")`, assert the aligner is called, and assert the saved schema-2 aligned cache contains `phonemes`.

**Confidence:** high

---

### F-004 [major] verification — docs/plans/2026-06-11-port-titan-mms-alignment.md:954-962

**Evidence:**
```md
**Step 2: Verify syntax**

Run:

```bash
.venv/bin/python -m py_compile scripts/smoke_mms_alignment.py
```

Expected: exit code 0.
```

**Claim:** The “real alignment smoke script” task only verifies Python syntax and never runs the script through `MmsForcedAligner`.

**Impact:** Missing model loading, tokenizer, `forced_align`, tensor shape, and runtime dependency failures are deferred until the full real-song run after multiple commits, making the smoke task a false gate for the real MMS path.

**Recommendation:** Add a smoke execution step using an existing short audio sample or a bounded slice of the named real-song input, and require a nonzero aligned phoneme count before committing the smoke-script task.

**Confidence:** high

---

### F-005 [major] verification — docs/plans/2026-06-11-port-titan-mms-alignment.md:1013-1023

**Evidence:**
```py
paths = sorted(Path(".louvorja-cache").glob("*/transcript/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
for path in paths[:1]:
    transcript = Transcript.from_dict(json.loads(path.read_text()))
    report = analyze_transcript_quality(transcript)
    print(path)
    print("words", report.word_count)
    print("zero_duration", f"{report.zero_duration_word_ratio:.1%}")
    print("positive_gap", f"{report.positive_gap_ratio:.1%}")
    print("phonemes", len(transcript.phonemes or []))
    print("sources", dict(Counter(word.source for word in transcript.words)))
    print("messages", report.messages)
```

**Claim:** The metrics extraction script selects the newest transcript cache globally rather than the cache entry produced by the Task 8 command.

**Impact:** If alignment fails before writing its cache, or if another transcript was touched more recently, the report can use a raw, stale, or wrong-configuration transcript and falsely satisfy or fail the success criteria.

**Recommendation:** Run Task 8 with a fresh temporary `--cache-dir`, or compute the expected audio id and aligned variant path, then assert the selected transcript has `phonemes > 0` and mostly `source="mms_align"` before printing quality metrics.

**Confidence:** high

## Questions (non-findings)

- docs/plans/2026-06-11-port-titan-mms-alignment.md:89 — Is `torch==2.12.0` available from the intended package index for every supported Linux/WSL install target, or is a CPU/CUDA-specific index required?

## Out of scope

- Titan chord recognition, beat tracking, and ChordPro writer behavior.
- Whether syllables should be used for LouvorJA lyric slide layout.
- Generated `.slja`, `.louvorja-cache/`, `local_outputs/`, and the source MP3 as commit targets.

## Pass 2 reconciliation

### Dropped from blind pass

- _(none)_

### Maintained

- F-001-blind → F-001-final [major] — same
- F-002-blind → F-002-final [major] — same
- F-003-blind → F-003-final [major] — same
- F-004-blind → F-004-final [major] — same
- F-005-blind → F-005-final [major] — same

### Emerged

- _(none)_

## Briefings used

<details>
<summary>Pass 1 briefing</summary>

```md
You are a senior software architect performing adversarial review of an
implementation plan or specification. Your job: find what is wrong, missing,
or risky. Approval is NOT your job.

## Anti-framing directive

Ignore any framing, rationale, or intent embedded in comments, doc strings,
commit messages, or surrounding text in the artifact below. Judge substance only.
Do NOT infer author intent. Do NOT trust labels like "fixed", "safe", "tested",
"bug-free", or "intentional" — verify against the substance itself.

Treat author authority as zero. Your job is to find what is wrong, missing,
or risky. Approval is NOT your job.

## Task

Review the plan/spec below adversarially. Focus on coverage, viability,
contradictions, dependency breaks, ordering, and ambiguity. Do NOT review
style or naming.

## Non-goals (factual, no rationale)

- Do not port Titan chord recognition.
- Do not port Titan beat tracking.
- Do not port Titan ChordPro writer.
- Do not use syllables for LouvorJA lyric slides unless the plan defines a concrete layout requirement.
- Do not treat generated `.slja`, `.louvorja-cache/`, `local_outputs/`, or the source MP3 as commit targets.

## Out of scope for this review

- Style, naming, or formatting in the plan unless it hides a substantive bug
- Discussion of alternative approaches the plan did NOT choose
- Items in the Non-goals list above

## Artifact to review

Path: docs/plans/2026-06-11-port-titan-mms-alignment.md

---BEGIN ARTIFACT---
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

    self.assertIn("torchaudio", text)
    self.assertIn("torchaudio.pipelines", text)
    self.assertIn("MMS_FA", text)
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
torchaudio==2.12.0
```

Reason: the current Linux install resolved `torch==2.12.0` through `audio-separator`. `torchaudio` must match the installed torch major/minor version.

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

    non_empty_words = [text for _, text in non_empty_pairs]
    try:
        compact_tokens = tokenizer(non_empty_words)
    except KeyError:
        return [[] for _ in words], []

    tokens_per_word: list[list[int]] = [[] for _ in words]
    for original_index, tokens in zip(
        [index for index, _ in non_empty_pairs],
        compact_tokens,
        strict=True,
    ):
        tokens_per_word[original_index] = list(tokens)

    target_tokens = [token for word_tokens in tokens_per_word for token in word_tokens]
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
        return []

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
def test_build_mms_targets_returns_empty_when_tokenizer_rejects_word(self) -> None:
    class RejectingTokenizer:
        def __call__(self, words: list[str]) -> list[list[int]]:
            raise KeyError(words[0])

    tokens_per_word, target_tokens = build_mms_targets(
        [TranscribedWord("Fala", 0.0, 0.5)],
        RejectingTokenizer(),
    )

    self.assertEqual(tokens_per_word, [[]])
    self.assertEqual(target_tokens, [])


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
```

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
    config = LocalPipelineConfig(
        cache_root=Path(".cache"),
        whisper_model="medium",
        vocal_separation="htdemucs_ft",
        alignment="mms",
    )

    self.assertEqual(local_pipeline._CACHE_SCHEMA_VERSION, 2)

    first = local_pipeline._variant(
        stage="aligned",
        language=config.language,
        whisper_model=config.whisper_model,
        vocal_separation=config.vocal_separation,
        alignment=config.alignment,
    )

    self.assertIsInstance(first, str)
```

Add module import:

```python
from louvorja_slides import local_pipeline
```

This test fails before the schema bump because `_CACHE_SCHEMA_VERSION` is still `1`, then passes after the bump.

**Step 2: Bump local cache schema**

In `louvorja_slides/local_pipeline.py`, update:

```python
_CACHE_SCHEMA_VERSION = 2
```

Reason: transcript JSON now can include `phonemes`, and old aligned caches without phonemes must not masquerade as complete alignment output.

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
- Test: no unit test; verify with `py_compile`.

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

**Step 3: Commit**

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
.venv/bin/python audio_to_slja.py "ADORADORES 3 - FÉ E AÇÃO.mp3" \
  --engine local \
  --vocal-separation htdemucs_ft \
  --alignment mms \
  --whisper-model medium \
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

from louvorja_slides.quality import analyze_transcript_quality
from louvorja_slides.transcription import Transcript

paths = sorted(Path(".louvorja-cache").glob("*/transcript/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
for path in paths[:1]:
    transcript = Transcript.from_dict(json.loads(path.read_text()))
    report = analyze_transcript_quality(transcript)
    print(path)
    print("words", report.word_count)
    print("zero_duration", f"{report.zero_duration_word_ratio:.1%}")
    print("positive_gap", f"{report.positive_gap_ratio:.1%}")
    print("phonemes", len(transcript.phonemes or []))
    print("sources", dict(Counter(word.source for word in transcript.words)))
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

---END ARTIFACT---

## What to look for (attack surfaces for plan review)

1. **Contradictions**: task X says A, task Y says non-A
2. **Coverage gaps**: a requirement or constraint has no corresponding task
3. **Dependency breaks**: a task references a file/symbol no task creates
4. **Ordering bugs**: a task depends on something built only later
5. **Ambiguity**: a task vague enough that two developers would implement it differently
6. **Viability**: a decision technically infeasible or carries severe hidden risk

## Finding bar (mandatory for EACH finding)

Every finding MUST answer all four:
1. WHAT fails or is missing
2. WHY it is wrong (mechanism, not assertion)
3. IMPACT — concrete consequence
4. RECOMMENDATION — specific action, not "consider X"

If a finding cannot answer all four: DROP IT. Quality > quantity.

## Severity calibration

- **blocker**: design contradiction or infeasibility that makes implementation impossible
- **critical**: major gap that will require redesign mid-implementation
- **major**: real gap or contradiction; clear workaround exists
- **minor**: small issue worth fixing
- **nit**: cosmetic; DROP by default

QUOTA: maximum 5 (blocker + critical combined). If you have more, RECALIBRATE
— you are likely over-reporting.

## Output format

# Required Output Format — Pass 1 (Blind)

You MUST respond in this exact markdown structure. No prose before frontmatter.
No commentary after the last section. No alternative formats.

````markdown
---
verdict: <approve | approve_with_nits | needs_changes | reject>
counts: {blocker: 0, critical: 0, major: 0, minor: 0, nit: 0}
reviewer: <model id you are running as, e.g. gpt-5.3-codex>
pass: blind
schema_version: "1.0"
---

## Summary
<1-2 paragraphs, max 200 words. State substance only — no compliments, no
"what works well", no praise. If verdict is approve, say so in one sentence
and stop.>

## Findings

### F-001 [<severity>] <category> — <file>:<line_start>[-<line_end>]

**Evidence:**
```<lang>
<exact snippet from artifact — quote literally>
```

**Claim:** <what fails or is missing — single sentence>

**Impact:** <concrete consequence — data loss? auth bypass? user-visible bug?
unimplementable design decision? Be specific, not abstract.>

**Recommendation:** <specific action. NOT "consider X". Say what to do.>

**Confidence:** <high | medium | low>

---

### F-002 ...
(repeat for each finding. Increment IDs F-001, F-002, F-003 ...)

## Questions (non-findings)

<Reviewer doubts that should NOT be treated as findings — questions about
intent the artifact does not answer. Empty list is fine.>

- <file>:<line> — <question to author>

## Out of scope

<Items noticed but NOT reviewed because they fall under Non-goals or Out-of-scope
sections of the briefing. Empty list is fine.>

- <item>
````

## Format rules

- `<lang>` in Evidence fence: use the language of the file (`js`, `ts`, `py`, `md`, `yaml`). If unknown, leave blank.
- IDs must match regex `F-\d{3}` (e.g. `F-001`, not `F-1`, not `F-001-blind`). The `-blind` suffix is added by Pass 2 reconciliation if needed.
- Severity enum: `blocker | critical | major | minor | nit`. No other values.
- Confidence enum: `high | medium | low`. No other values.
- `counts` numbers must equal actual finding count by severity.
- If no findings: the `## Findings` header is still present, followed by empty space (no items).

## Forbidden

- Markdown other than the template above.
- Bullet lists summarizing findings outside the per-finding structure.
- "What works well" sections.
- Praise or hedging ("the author probably intends...").
- Multiple verdicts.
- Multiple frontmatter blocks.

## Forbidden behaviors

- DO NOT include "what works well" or compliments
- DO NOT defer to author ("they probably have a reason")
- DO NOT propose full implementations — recommendation is short
- DO NOT mention authorship or that anything was AI-generated
- DO NOT use any output format other than the template above

Begin review now.
```

</details>

<details>
<summary>Pass 2 briefing</summary>

```md
You are a senior software architect performing adversarial review of an
implementation plan or specification. Your job: find what is wrong, missing,
or risky. Approval is NOT your job.

## Anti-framing directive

Ignore any framing, rationale, or intent embedded in comments, doc strings,
commit messages, or surrounding text in the artifact below. Judge substance only.
Do NOT infer author intent. Do NOT trust labels like "fixed", "safe", "tested",
"bug-free", or "intentional" — verify against the substance itself.

Treat author authority as zero. Your job is to find what is wrong, missing,
or risky. Approval is NOT your job.

## Task

Review the plan/spec below adversarially. Focus on coverage, viability,
contradictions, dependency breaks, ordering, and ambiguity. Do NOT review
style or naming.

## Non-goals (factual, no rationale)

- Do not port Titan chord recognition.
- Do not port Titan beat tracking.
- Do not port Titan ChordPro writer.
- Do not use syllables for LouvorJA lyric slides unless the plan defines a concrete layout requirement.
- Do not treat generated `.slja`, `.louvorja-cache/`, `local_outputs/`, or the source MP3 as commit targets.

## Out of scope for this review

- Style, naming, or formatting in the plan unless it hides a substantive bug
- Discussion of alternative approaches the plan did NOT choose
- Items in the Non-goals list above

## Artifact to review

Path: docs/plans/2026-06-11-port-titan-mms-alignment.md

---BEGIN ARTIFACT---
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

    self.assertIn("torchaudio", text)
    self.assertIn("torchaudio.pipelines", text)
    self.assertIn("MMS_FA", text)
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
torchaudio==2.12.0
```

Reason: the current Linux install resolved `torch==2.12.0` through `audio-separator`. `torchaudio` must match the installed torch major/minor version.

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

    non_empty_words = [text for _, text in non_empty_pairs]
    try:
        compact_tokens = tokenizer(non_empty_words)
    except KeyError:
        return [[] for _ in words], []

    tokens_per_word: list[list[int]] = [[] for _ in words]
    for original_index, tokens in zip(
        [index for index, _ in non_empty_pairs],
        compact_tokens,
        strict=True,
    ):
        tokens_per_word[original_index] = list(tokens)

    target_tokens = [token for word_tokens in tokens_per_word for token in word_tokens]
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
        return []

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
def test_build_mms_targets_returns_empty_when_tokenizer_rejects_word(self) -> None:
    class RejectingTokenizer:
        def __call__(self, words: list[str]) -> list[list[int]]:
            raise KeyError(words[0])

    tokens_per_word, target_tokens = build_mms_targets(
        [TranscribedWord("Fala", 0.0, 0.5)],
        RejectingTokenizer(),
    )

    self.assertEqual(tokens_per_word, [[]])
    self.assertEqual(target_tokens, [])


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
```

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
    config = LocalPipelineConfig(
        cache_root=Path(".cache"),
        whisper_model="medium",
        vocal_separation="htdemucs_ft",
        alignment="mms",
    )

    self.assertEqual(local_pipeline._CACHE_SCHEMA_VERSION, 2)

    first = local_pipeline._variant(
        stage="aligned",
        language=config.language,
        whisper_model=config.whisper_model,
        vocal_separation=config.vocal_separation,
        alignment=config.alignment,
    )

    self.assertIsInstance(first, str)
```

Add module import:

```python
from louvorja_slides import local_pipeline
```

This test fails before the schema bump because `_CACHE_SCHEMA_VERSION` is still `1`, then passes after the bump.

**Step 2: Bump local cache schema**

In `louvorja_slides/local_pipeline.py`, update:

```python
_CACHE_SCHEMA_VERSION = 2
```

Reason: transcript JSON now can include `phonemes`, and old aligned caches without phonemes must not masquerade as complete alignment output.

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
- Test: no unit test; verify with `py_compile`.

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

**Step 3: Commit**

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
.venv/bin/python audio_to_slja.py "ADORADORES 3 - FÉ E AÇÃO.mp3" \
  --engine local \
  --vocal-separation htdemucs_ft \
  --alignment mms \
  --whisper-model medium \
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

from louvorja_slides.quality import analyze_transcript_quality
from louvorja_slides.transcription import Transcript

paths = sorted(Path(".louvorja-cache").glob("*/transcript/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
for path in paths[:1]:
    transcript = Transcript.from_dict(json.loads(path.read_text()))
    report = analyze_transcript_quality(transcript)
    print(path)
    print("words", report.word_count)
    print("zero_duration", f"{report.zero_duration_word_ratio:.1%}")
    print("positive_gap", f"{report.positive_gap_ratio:.1%}")
    print("phonemes", len(transcript.phonemes or []))
    print("sources", dict(Counter(word.source for word in transcript.words)))
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

---END ARTIFACT---

## What to look for (attack surfaces for plan review)

1. **Contradictions**: task X says A, task Y says non-A
2. **Coverage gaps**: a requirement or constraint has no corresponding task
3. **Dependency breaks**: a task references a file/symbol no task creates
4. **Ordering bugs**: a task depends on something built only later
5. **Ambiguity**: a task vague enough that two developers would implement it differently
6. **Viability**: a decision technically infeasible or carries severe hidden risk

## Finding bar (mandatory for EACH finding)

Every finding MUST answer all four:
1. WHAT fails or is missing
2. WHY it is wrong (mechanism, not assertion)
3. IMPACT — concrete consequence
4. RECOMMENDATION — specific action, not "consider X"

If a finding cannot answer all four: DROP IT. Quality > quantity.

## Severity calibration

- **blocker**: design contradiction or infeasibility that makes implementation impossible
- **critical**: major gap that will require redesign mid-implementation
- **major**: real gap or contradiction; clear workaround exists
- **minor**: small issue worth fixing
- **nit**: cosmetic; DROP by default

QUOTA: maximum 5 (blocker + critical combined). If you have more, RECALIBRATE
— you are likely over-reporting.

## Output format

# Required Output Format — Pass 1 (Blind)

You MUST respond in this exact markdown structure. No prose before frontmatter.
No commentary after the last section. No alternative formats.

````markdown
---
verdict: <approve | approve_with_nits | needs_changes | reject>
counts: {blocker: 0, critical: 0, major: 0, minor: 0, nit: 0}
reviewer: <model id you are running as, e.g. gpt-5.3-codex>
pass: blind
schema_version: "1.0"
---

## Summary
<1-2 paragraphs, max 200 words. State substance only — no compliments, no
"what works well", no praise. If verdict is approve, say so in one sentence
and stop.>

## Findings

### F-001 [<severity>] <category> — <file>:<line_start>[-<line_end>]

**Evidence:**
```<lang>
<exact snippet from artifact — quote literally>
```

**Claim:** <what fails or is missing — single sentence>

**Impact:** <concrete consequence — data loss? auth bypass? user-visible bug?
unimplementable design decision? Be specific, not abstract.>

**Recommendation:** <specific action. NOT "consider X". Say what to do.>

**Confidence:** <high | medium | low>

---

### F-002 ...
(repeat for each finding. Increment IDs F-001, F-002, F-003 ...)

## Questions (non-findings)

<Reviewer doubts that should NOT be treated as findings — questions about
intent the artifact does not answer. Empty list is fine.>

- <file>:<line> — <question to author>

## Out of scope

<Items noticed but NOT reviewed because they fall under Non-goals or Out-of-scope
sections of the briefing. Empty list is fine.>

- <item>
````

## Format rules

- `<lang>` in Evidence fence: use the language of the file (`js`, `ts`, `py`, `md`, `yaml`). If unknown, leave blank.
- IDs must match regex `F-\d{3}` (e.g. `F-001`, not `F-1`, not `F-001-blind`). The `-blind` suffix is added by Pass 2 reconciliation if needed.
- Severity enum: `blocker | critical | major | minor | nit`. No other values.
- Confidence enum: `high | medium | low`. No other values.
- `counts` numbers must equal actual finding count by severity.
- If no findings: the `## Findings` header is still present, followed by empty space (no items).

## Forbidden

- Markdown other than the template above.
- Bullet lists summarizing findings outside the per-finding structure.
- "What works well" sections.
- Praise or hedging ("the author probably intends...").
- Multiple verdicts.
- Multiple frontmatter blocks.

## Forbidden behaviors

- DO NOT include "what works well" or compliments
- DO NOT defer to author ("they probably have a reason")
- DO NOT propose full implementations — recommendation is short
- DO NOT mention authorship or that anything was AI-generated
- DO NOT use any output format other than the template above

## External constraints (verifiable)

The constraints below are verifiable externally. Each line includes how to
verify if needed. Treat as ground truth.

- `requirements.txt` currently contains `audio-separator==0.44.2`, `onnxruntime==1.26.0`, and no direct `torch` or `torchaudio` pin before this plan is implemented; verify with `sed -n "1,130p" requirements.txt`.
- Current `.venv` has `torch==2.12.0`, does not have `torchaudio`, and `pip check` reports no broken requirements before this plan is implemented; verify with `.venv/bin/python -m pip check` and `importlib.metadata`.
- `audio-separator==0.44.2` package metadata requires `torch >=2.3`, not a specific `torch==2.12.0`; verify with `.venv/lib/python3.12/site-packages/audio_separator-0.44.2.dist-info/METADATA`.
- The plan non-goals are: no Titan chord recognition, no Titan beat tracking, no Titan ChordPro writer, no generated `.slja`/cache/output/MP3 commits.
- The project local pipeline already decodes selected audio to 16 kHz mono samples in `louvorja_slides/audio.py`; verify lines 25-68.
- The plan artifact is the only artifact to review for line-cited findings; external local files above are constraints, not additional findings sources.

## Pass 1 (blind) findings

The following findings were produced by your previous review WITHOUT the
constraints above. Re-evaluate each against the constraints.

---BEGIN PASS 1 OUTPUT---
---
verdict: needs_changes
counts: {blocker: 0, critical: 0, major: 5, minor: 0, nit: 0}
reviewer: gpt-5-codex
pass: blind
schema_version: "1.0"
---

## Summary
The plan is executable as a task list, but it leaves several verification and failure-mode gaps that can produce a green unit suite while the real MMS path remains broken or unverifiable. The main risks are dependency determinism, all-or-nothing tokenizer failure, weak cache regression coverage, a non-running “smoke” step, and metric extraction that can report the wrong cached transcript.

## Findings

### F-001 [major] dependency — docs/plans/2026-06-11-port-titan-mms-alignment.md:80-89

**Evidence:**
```md
imageio-ffmpeg==0.6.0
numpy==2.4.6
pywhispercpp==1.5.0
audio-separator==0.44.2
onnxruntime==1.26.0
torchaudio==2.12.0
```

**Claim:** The plan pins `torchaudio` but does not directly pin or verify the matching `torch` version it says the install relies on.

**Impact:** A resolver or transitive dependency change can install a torch build/version that does not match the torchaudio binary, causing `import torchaudio`, `MMS_FA`, or model execution to fail after the dependency task appears complete.

**Recommendation:** Add an explicit `torch==2.12.0` pin or constraints entry, and extend installer verification to assert `torch.__version__` and `torchaudio.__version__` share the required major/minor pair.

**Confidence:** medium

---

### F-002 [major] failure-mode — docs/plans/2026-06-11-port-titan-mms-alignment.md:647-651

**Evidence:**
```py
    try:
        compact_tokens = tokenizer(non_empty_words)
    except KeyError:
        return [[] for _ in words], []
```

**Claim:** A single tokenizer rejection discards the entire target sequence instead of isolating or reporting the offending word.

**Impact:** One unexpected sanitized token causes the whole song to produce no alignment targets; the later real-song run can fail without aligned words or phonemes, and the plan has no partial-alignment fallback or diagnostic that identifies the bad transcript token.

**Recommendation:** Tokenize per word or retry by dropping only rejected words, preserve original word indices with empty token lists for rejected items, and raise an explicit error only when no alignable targets remain.

**Confidence:** high

---

### F-003 [major] coverage — docs/plans/2026-06-11-port-titan-mms-alignment.md:818-836

**Evidence:**
```py
def test_pipeline_cache_distinguishes_phoneme_schema_for_aligned_transcripts(self) -> None:
    config = LocalPipelineConfig(
        cache_root=Path(".cache"),
        whisper_model="medium",
        vocal_separation="htdemucs_ft",
        alignment="mms",
    )

    self.assertEqual(local_pipeline._CACHE_SCHEMA_VERSION, 2)

    first = local_pipeline._variant(
        stage="aligned",
        language=config.language,
        whisper_model=config.whisper_model,
        vocal_separation=config.vocal_separation,
        alignment=config.alignment,
    )

    self.assertIsInstance(first, str)
```

**Claim:** The cache regression test does not exercise cache reads, cache writes, old schema isolation, or phoneme presence.

**Impact:** The implementation can pass this test while still loading a stale aligned transcript without phonemes, because the test only checks a constant and that `_variant()` returns a string.

**Recommendation:** Replace or extend the test to seed a schema-1 aligned transcript cache without phonemes, run `transcribe_audio_local(... alignment="mms")`, assert the aligner is called, and assert the saved schema-2 aligned cache contains `phonemes`.

**Confidence:** high

---

### F-004 [major] verification — docs/plans/2026-06-11-port-titan-mms-alignment.md:954-962

**Evidence:**
```md
**Step 2: Verify syntax**

Run:

```bash
.venv/bin/python -m py_compile scripts/smoke_mms_alignment.py
```

Expected: exit code 0.
```

**Claim:** The “real alignment smoke script” task only verifies Python syntax and never runs the script through `MmsForcedAligner`.

**Impact:** Missing model loading, tokenizer, `forced_align`, tensor shape, and runtime dependency failures are deferred until the full real-song run after multiple commits, making the smoke task a false gate for the real MMS path.

**Recommendation:** Add a smoke execution step against a short checked-in or generated audio fixture with known words, and require nonzero aligned phoneme count before committing the smoke-script task.

**Confidence:** high

---

### F-005 [major] verification — docs/plans/2026-06-11-port-titan-mms-alignment.md:1013-1023

**Evidence:**
```py
paths = sorted(Path(".louvorja-cache").glob("*/transcript/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
for path in paths[:1]:
    transcript = Transcript.from_dict(json.loads(path.read_text()))
    report = analyze_transcript_quality(transcript)
    print(path)
    print("words", report.word_count)
    print("zero_duration", f"{report.zero_duration_word_ratio:.1%}")
    print("positive_gap", f"{report.positive_gap_ratio:.1%}")
    print("phonemes", len(transcript.phonemes or []))
    print("sources", dict(Counter(word.source for word in transcript.words)))
    print("messages", report.messages)
```

**Claim:** The metrics extraction script selects the newest transcript cache globally rather than the cache entry produced by the Task 8 command.

**Impact:** If alignment fails before writing its cache, or if another transcript was touched more recently, the report can use a raw, stale, or wrong-configuration transcript and falsely satisfy or fail the success criteria.

**Recommendation:** Run Task 8 with a fresh temporary `--cache-dir`, or compute the expected audio id and aligned variant path, then assert the selected transcript has `phonemes > 0` and mostly `source="mms_align"` before printing quality metrics.

**Confidence:** high

## Questions (non-findings)

- docs/plans/2026-06-11-port-titan-mms-alignment.md:89 — Is `torch==2.12.0` available from the intended package index for every supported Linux/WSL install target, or is a CPU/CUDA-specific index required?

## Out of scope

- Titan chord recognition, beat tracking, and ChordPro writer behavior.
- Whether syllables should be used for LouvorJA lyric slide layout.
---END PASS 1 OUTPUT---

## Your task in this pass

1. Re-evaluate ALL findings from Pass 1 against the External Constraints.
   For EACH Pass 1 finding, decide one of:
   - **DROP** — finding is invalid given a constraint or non-goal
   - **MAINTAIN** — finding stands, severity unchanged
   - **REFINE** — finding stands but severity changes

2. Identify NEW findings that emerge ONLY because of these constraints
   (e.g. the artifact violates a constraint you couldn't see in Pass 1).

3. Output the FULL final findings list (use new sequential IDs starting at
   F-001) plus a complete `## Pass 2 reconciliation` block.

## Output format

# Required Output Format — Pass 2 (Informed)

Same template as Pass 1 PLUS an obligatory `## Pass 2 reconciliation` block.
You MUST respond in this exact structure.

````markdown
---
verdict: <approve | approve_with_nits | needs_changes | reject>
counts: {blocker: 0, critical: 0, major: 0, minor: 0, nit: 0}
reviewer: <model id>
pass: informed
schema_version: "1.0"
---

## Summary
<1-2 paragraphs, max 200 words>

## Findings

### F-001 [<severity>] <category> — <file>:<line>

**Evidence:** <...>
**Claim:** <...>
**Impact:** <...>
**Recommendation:** <...>
**Confidence:** <...>

---

### F-002 ... (final IDs — these are the post-constraints findings)

## Questions (non-findings)

- <file>:<line> — <question>

## Out of scope

- <item>

## Pass 2 reconciliation

### Dropped from blind pass

<For each Pass 1 finding you are dropping, write one line:>

- F-001-blind [<severity>] <category> — DROPPED: <one-sentence reason citing
  which constraint or non-goal makes it invalid>

<If no drops: write `- _(none)_`>

### Maintained

<For each Pass 1 finding kept (with or without severity change):>

- F-002-blind → F-001-final [<severity>] — <same | severity changed: was X, now Y>

<If no maintained: write `- _(none)_`>

### Emerged

<For each NEW finding that surfaced only because constraints were revealed:>

- F-XXX-final [<severity>] <category> — emerged: <one-sentence reason citing
  the constraint that triggered the finding>

<If no emerged: write `- _(none)_`>
````

## Rules specific to Pass 2

- Final findings use sequential IDs `F-001, F-002, ...` (no `-final` suffix in the `## Findings` section — only in reconciliation references).
- In reconciliation, refer to blind findings with `-blind` suffix and maintained mappings with `→ F-XXX-final`.
- `counts` is the COUNT OF FINAL findings (post-reconciliation), not blind.
- `pass: informed` (literal).
- All universal rules from `output-template-pass1.md` apply.

Begin reconciliation now.
```

</details>

## Fixes applied in this session

- Applied local self-loop fixes to `docs/plans/2026-06-11-port-titan-mms-alignment.md` before Codex Pass 1.
- No blocker or critical Codex findings required interactive triage.
- Post-review fix F-001: updated Task 1 to pin `torch==2.12.0` directly and verify `torch.__version__` / `torchaudio.__version__` major-minor compatibility.
- Post-review fix F-002: updated Task 5 target construction to tokenize per word, skip only rejected words, preserve word offsets, and raise explicit `AlignmentError` when no alignable target tokens remain.
- Post-review fix F-003: replaced the Task 6 cache test with a stale schema-1 aligned-cache fixture and assertions that the schema-2 path calls the aligner and writes phonemes.
- Post-review fix F-004: expanded Task 7 from syntax-only verification to a bounded real-song smoke run that requires nonzero `phonemes=`.
- Post-review fix F-005: updated Task 8 to run with a deterministic fresh cache directory and read the exact expected aligned transcript cache path.
