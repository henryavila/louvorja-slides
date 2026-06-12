# Review: Decouple Local Transcription Plan

**Plan:** `docs/plans/2026-06-10-decouple-local-transcription.md`
**Mode:** both
**Cross-ref:** internal
**Initiatives discovered:** N/A
**Local iterations:** 2
**Codex iterations:** 2 (blind + informed)
**Final verdict:** needs_changes

## Local Fix Log

- Reframed local review notes as neutral implementation constraints before the
  Codex briefing.
- Added cache variant requirements so raw/aligned transcript caches include
  quality configuration and do not cross-contaminate models or alignment modes.
- Added `Transcript.to_dict()` / `Transcript.from_dict()` plan coverage because
  the pipeline stores transcripts as JSON.
- Tightened the vocal separation adapter to call
  `Separator.load_model("htdemucs_ft.yaml")` before `separate()`, matching the
  verified `audio-separator` API behavior.
- Changed MMS alignment behavior from silent fallback to explicit
  `AlignmentError` for alignable words with no spans.
- Moved fake aligner tests into `unittest.TestCase` classes so they are
  discoverable by `python -m unittest`.
- Removed remaining soft wording found by grep.

## Codex Final Findings

### F-001 critical verification

Real end-to-end ML validation remains optional. The plan can pass unit tests and
import smoke without exercising `large-v3`, `htdemucs_ft.yaml`, model downloads,
separation output naming, or MMS alignment on any audio.

Recommendation: make a real or staged ML smoke gate required.

### F-002 major dependency

The plan verifies behavior against `audio-separator==0.44.2` but specifies
`audio-separator>=0.17`.

Recommendation: pin to `audio-separator==0.44.2` or document and test a verified
compatible range.

### F-003 major MMS alignment ambiguity

The plan still says to implement chunked MMS alignment "as Titan does" without
embedding exact source references or a self-contained checklist for tokenizer
shape, sanitized word mapping, chunk stitching, blank handling, and span mapping.

### F-004 major pipeline order contradiction

The top-level diagram says decode/probe before vocal separation, while Task 9
separates first and decodes the returned vocal stem.

### F-005 major fallback error tests

The plan requires stage-specific fallback errors but lacks orchestrator/CLI tests
that assert the stage name and bypass flag in failure messages.

### F-006 major cache incompleteness

Cache keys still omit quality-affecting settings such as Whisper timestamp flags,
hallucination thresholds, separator model filename, audio normalization details,
MMS frame parameters, and schema version.

### F-007 major partial alignment policy

`refine_words_from_spans` preserves missing spans, but the plan does not define
or test whether partial MMS alignment should raise or emit mixed-source output.

### F-008 major CLI config test gap

The CLI test patches the pipeline return without asserting the constructed
`LocalPipelineConfig`; defaults and overrides could be ignored while tests pass.

### F-009 minor document grouping edge case

The document adapter does not define behavior for transcripts with no positive
inter-word gaps.

## Self-review Against Code-quality Gates

- G1 read-before-claim: verified relevant project files with `rg --files` and
  existence checks; external package/API checks were performed for
  `pywhispercpp` and `audio-separator`.
- G2 soft-language: ran grep for the configured soft-language list after local
  corrections; remaining matches were zero.
- G6 reference-or-strike: the plan does not use `verified_by:` markers. This is
  a plan-format caveat, not fully remediated in this review.
- Initiative-depth: N/A, the plan has no phase frontmatter or materialized
  initiatives.

## Raw Outputs

- Pass 1: `/tmp/codex-output-pass1-20260610-182953.md`
- Pass 2: `/tmp/codex-output-pass2-20260610-183317.md`
