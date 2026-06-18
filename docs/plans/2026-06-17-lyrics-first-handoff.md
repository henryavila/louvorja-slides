# Lyrics-First Handoff

## Plan Anchor

This was already planned in
`docs/plans/2026-06-11-local-engine-quality-correction.md` under
`Remaining Corrections`:

> Add a lyrics-first mode for production use when the expected lyrics are known.

The old plan only names the feature. This handoff turns it into an
implementation path.

## Runtime Dependency Rule

`../titan-chordpro-lib` is reference material only. Do not import it, install it
as a dependency, call its orchestrator, or make `--engine titan` part of this
project.

It is acceptable to read Titan code and copy/adapt the small pieces of logic
needed here, but the implementation must live inside this repository and use
this repository's dependency set.

## Why It Is Next

The local macOS/Linux path now produces structurally acceptable `.slja` archives
for the `Eu sou Calebe` validation song, but ASR text is still not authoritative
enough for production worship slides. The generated archive passes the
structural gate, but Whisper can still transcribe lyric words incorrectly, for
example `Caleb` instead of the expected displayed lyric `Calebe`.

The remaining quality problem is lyric correctness. Timing and slide layout are
now good enough to use as a base for a lyrics-first pass.

## Current State

- Do not commit automatically; the user explicitly asked for "sem commit".
- Existing `.slja` files can be validated directly by `audio_to_slja.py`.
- `--engine auto` and `--engine local` use the in-repo local pipeline on macOS,
  Linux, and WSL.
- `--engine titan` must stay removed/rejected.
- `--device mps` is allowed as a local forced-alignment device preference for
  macOS; it must not imply a Titan backend.
- `louvorja_slides/layout.py` was adjusted so `letra_aux` is rare short overflow
  instead of the normal escape hatch for dense lyrics.
- The original user archive
  `/Users/henry/Library/CloudStorage/OneDrive-Pessoal/Música/Ministério Tons/Cifras Ministério Tons/Slides músicas/Outros slides/Eu sou Calebe - 2024.slja`
  fails the archive gate with 1 empty lyric slide, 1 hard-limit line, and 4/33
  fast transitions.
- The latest generated sample
  `/tmp/eu-sou-calebe-generated-v5.slja` passes the gate with 27 lyric slides, 0
  empty slides, 0 hard-limit lines, 0 aux slides, and 0/26 fast transitions.
- Full test suite passed in a Python 3.12 environment with the local project
  dependencies:

```bash
python -m unittest discover -s tests -v
```

## Goal

Add a production mode where the expected lyrics are the text source of truth and
ASR/forced alignment provides timing only.

The output `.slja` should display the provided lyrics, preserving casing,
accents, punctuation, and line intent from the lyric source, while using the
audio transcript for word timings and slide timestamps.

## Proposed CLI

Prefer a minimal explicit interface:

```bash
python audio_to_slja.py input.mp3 \
  --engine local \
  --device mps \
  --lyrics-file lyrics.txt \
  --quality-gate fail \
  --output output.slja
```

Suggested flags:

- `--lyrics-file PATH`: plaintext expected lyrics.
- `--lyrics-text TEXT`: optional direct text input for tests or quick runs.
- `--lyrics-mode asr|lyrics-first`: optional. If lyrics are provided, default to
  `lyrics-first`; otherwise keep current ASR-first behavior.

Keep `.slja` validation mode separate. When input is already `.slja`, do not
require or apply lyrics-first.

## Implementation Strategy

1. Add `louvorja_slides/lyrics.py`.
   - Parse plaintext lyrics into display tokens.
   - Preserve original display text.
   - Keep line breaks and blank-line section hints for later slide grouping.
   - Create normalized tokens for matching: casefolded, accent-insensitive,
     punctuation-stripped.

2. Add a lyrics alignment layer after engine transcription.
   - Input: engine `Transcript` with word timings plus expected lyric tokens.
   - Output: a `Transcript` or document using expected lyric words and timings.
   - Match normalized ASR words to normalized lyric words with fuzzy alignment.
   - Allow insertions, deletions, repeated chorus text, and ASR typo variants.
   - Maintain monotonic word order.
   - Use ASR word times as anchors.
   - Interpolate timings for expected lyric words that do not get a direct ASR
     match.

3. Feed the lyrics-first result into the existing slide path.
   - Reuse `transcript_to_document()` / `extract_lyric_slides()` as much as
     possible.
   - Avoid a parallel slide planner unless the current planner cannot preserve
     lyric line hints cleanly.

4. Extend the quality gate.
   - Report lyrics alignment coverage.
   - Fail by default when anchored lyric-token coverage is too low. A reasonable
     starting threshold is 80%.
   - Include unmatched lyric spans and unmatched ASR spans in diagnostics.
   - Keep existing structural checks: empty slides, hard line length,
     `letra_aux` ratio, and fast transitions.

5. Cache carefully.
   - Reuse expensive raw ASR/local alignment caches.
   - Add a lyrics-aligned cache stage whose key includes:
     - lyrics content hash,
     - lyrics-first mode/version,
     - alignment algorithm revision,
     - relevant layout settings if cached after grouping.
   - Do not let edited lyrics reuse stale aligned output.

## Tests To Add First

- Exact ASR/lyrics match preserves expected casing and accents.
- ASR `Caleb` maps to display lyric `Calebe`.
- ASR extra filler or bracket words are skipped.
- Missing ASR lyric words get interpolated monotonic timings.
- Repeated chorus text maps to the correct later occurrence and does not
  collapse non-consecutive repeats.
- Low alignment coverage fails quality.
- CLI with `--lyrics-file` writes expected lyric text, not ASR text.
- Existing `.slja` input validation ignores lyrics flags or rejects them with a
  clear error.

## Real Validation Command

Use the already extracted audio and a local cache:

```bash
python audio_to_slja.py \
  /tmp/eu-sou-calebe-2024.mp3 \
  --engine local \
  --device mps \
  --whisper-model medium \
  --cache-dir /tmp/louvorja-calebe-local-cache \
  --lyrics-file /tmp/eu-sou-calebe-lyrics.txt \
  --quality-gate fail \
  --output /tmp/eu-sou-calebe-lyrics-first.slja
```

Then validate the generated archive:

```bash
python audio_to_slja.py \
  /tmp/eu-sou-calebe-lyrics-first.slja \
  --quality-gate fail
```

Do not commit real user lyrics unless the user explicitly asks for that.

## Non-Goals

- Do not import, install, or call `../titan-chordpro-lib`.
- Do not commit user-provided `.slja`, `.mp3`, or lyric files.
- Do not add chord rendering or chord timing work in this pass.
- Do not weaken the quality gate to make a sample pass.
