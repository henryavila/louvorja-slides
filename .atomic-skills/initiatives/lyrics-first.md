---
slug: lyrics-first
title: Lyrics-first SLJA generation
status: active
started: 2026-06-18
last_updated: 2026-06-18T20:35:00Z
branch: feat/slja-quality-local-only
plan_link: docs/plans/2026-06-17-lyrics-first-handoff.md
next_action: Compact whole-candidate vocal outputs so phase 1 passes robust slide/line gates
stack:
  - id: 1
    title: Implement lyrics-first generation path
    type: task
    opened_at: 2026-06-18T00:52:56Z
  - id: 2
    title: Implement phase 1 consensus transcription prototype
    type: task
    opened_at: 2026-06-18T13:00:11Z
tasks:
  T-001:
    title: Add lyric parsing and ASR-to-lyrics alignment helpers
    status: done
    last_updated: 2026-06-18T01:04:19Z
    closed_at: 2026-06-18T01:04:19Z
  T-002:
    title: Wire lyrics-first through CLI and cache
    status: done
    last_updated: 2026-06-18T01:04:19Z
    closed_at: 2026-06-18T01:04:19Z
  T-003:
    title: Extend quality diagnostics for lyrics alignment coverage
    status: done
    last_updated: 2026-06-18T01:04:19Z
    closed_at: 2026-06-18T01:04:19Z
  T-004:
    title: Run real lyrics-first validation with user lyrics
    status: done
    last_updated: 2026-06-18T01:22:00Z
    closed_at: 2026-06-18T01:22:00Z
  T-005:
    title: Add phrase-level consensus transcription MVP
    status: done
    last_updated: 2026-06-18T13:10:07Z
    closed_at: 2026-06-18T13:10:07Z
  T-006:
    title: Validate phase 1 consensus on 11-song batch
    status: done
    last_updated: 2026-06-18T14:53:52Z
    closed_at: 2026-06-18T14:53:52Z
  T-007:
    title: Analyze and fix phase 1 consensus regressions before phase 2
    status: done
    last_updated: 2026-06-18T16:27:44Z
    closed_at: 2026-06-18T16:27:44Z
  T-008:
    title: Decide/tune phase 1 secondary layout quality gate before phase 2
    status: done
    last_updated: 2026-06-18T17:04:30Z
    closed_at: 2026-06-18T17:04:30Z
  T-009:
    title: Fix phase 1 consensus temporal overlap and slide fragmentation
    status: todo
    last_updated: 2026-06-18T17:04:30Z
  T-010:
    title: Add full transcription and slide-mapping audit text to phase reports
    status: done
    last_updated: 2026-06-18T17:34:09Z
    closed_at: 2026-06-18T17:34:09Z
  T-011:
    title: Add reference lyrics gate for Deus e Refugio
    status: done
    last_updated: 2026-06-18T17:57:49Z
    closed_at: 2026-06-18T17:57:49Z
  T-012:
    title: Fix misleading reference lyrics labeling in phase reports
    status: done
    last_updated: 2026-06-18T18:38:16Z
    closed_at: 2026-06-18T18:38:16Z
  T-013:
    title: Research and revise consensus quality plan after real gate
    status: done
    last_updated: 2026-06-18T18:48:41Z
    closed_at: 2026-06-18T18:48:41Z
  T-014:
    title: Validate vocal-primary ASR candidates on 11-song batch
    status: done
    last_updated: 2026-06-18T19:17:12Z
    closed_at: 2026-06-18T19:17:12Z
  T-015:
    title: Promote vocal separation to first evidence stage with whole-candidate fallback
    status: done
    last_updated: 2026-06-18T20:35:00Z
    closed_at: 2026-06-18T20:35:00Z
  T-016:
    title: Reduce slide and line expansion from selected vocal whole-candidate outputs
    status: todo
    last_updated: 2026-06-18T20:35:00Z
parked: []
emerged: []
---

# Notes

Resumed from `docs/plans/2026-06-18-session-handoff.md`.

The branch should keep `../titan-chordpro-lib` as reference-only material and
must not reintroduce a Titan runtime engine.

2026-06-18: Generated `/tmp/eu-sou-calebe-lyrics-first.slja` and
`/tmp/eu-sou-calebe-lyrics-first-failcheck.slja` from the extracted audio plus
temporary lyrics from the reference `.slja`. The failcheck generation and archive
validation both passed the quality gate.

2026-06-18: Regenerated the YouTube sample
`/tmp/louvorja-youtube-9yZt5ekdceI/ao-olhar-pra-cruz.slja` after fixing LouvorJA
audio metadata, embedded audio filename sanitization, punctuation-only ASR token
filtering, and phrase-preserving slide grouping. The archive passes structural
validation, but its lyric text remains ASR-derived.

2026-06-18: Implemented the phase 1 phrase-level consensus MVP in
`louvorja_slides/consensus.py` and wired it through
`--transcription-strategy consensus`. The focused tests pass; full-suite
validation on the system Python is blocked by missing `numpy`, so real 11-song
batch validation remains open.

2026-06-18: Added `scripts/phase_gate_consensus.py` to make the phase gate
explicit: each phase must run the full expected batch (default 11 videos),
snapshot the old-process `.slja` candidates and aggregate reports, write
per-video phase outputs/comparisons, and produce a consolidated
`phase-gate-report`. Limited runs are allowed only as debugging artifacts and
are marked as not full-set passes.

2026-06-18: Executed phase 1 gate on the full 11-song batch with run id
`phase1-execute-20260618T134909Z`. The gate completed all 11 comparisons but
failed: baseline old-process hard-limit lines totaled 23, phase 1 consensus
totaled 30, delta +7. Artifacts live under
`/tmp/louvorja-asr-batch-2026-06-18/phase-history/phase-1/phase1-execute-20260618T134909Z/`.
Supplemental effort report persisted inferred runtime/cost: 59m27s total
video-level processing, 5m24s average per video, phase cache about 441 MiB,
run history about 506 MiB. The gate runner now writes video-level effort
metrics and `phase-effort-report.md/.json` for future runs.

2026-06-18: Fixed the phase 1 hard-line regression in slide planning and SLJA
extraction. Root causes: overlong strong-boundary candidates were accepted, and
automatic ASR-generated line breaks were treated as rigid source line hints. The
corrected full 11-song run `phase1-fix4-20260618T160700Z` passed the official
hard-line gate: baseline 23 hard-limit lines -> phase 1 consensus 0, delta -23.
Effort for the cached rerun was 2m16s total video time, 12s average per video,
0 B cache growth, and 70.7 MiB output history. Residual decision before phase 2:
secondary layout metrics regressed (slides 130 -> 289, fast transitions 0 -> 44,
target-limit lines 45 -> 113, aux words 18 -> 70), so the team should either
accept the hard-line-only gate or add thresholds for slide/transition explosion.

2026-06-18: Added robust secondary phase gates and reran the full 11-song phase
1 gate as `phase1-robust-gate-20260618T163300Z`. The new gate correctly fails
the same artifacts that previously looked like a pass: hard-line gate passes
23 -> 0, but slide-count gate fails 130 -> 289 (ratio 2.223), line-count gate
fails 237 -> 543 (ratio 2.291), fast-transition gate fails 0 -> 44 (15.8%),
auxiliary-word gate fails 18 -> 70, and target-line gate fails due per-video
target-line ratio. Root cause is two-layered: consensus chooses phrase winners
from different ASR sources with overlapping/too-dense timestamps, then layout
splits those dense windows to obey hard line limits. The old gate was blind
because it only required full-set hard-line non-regression.

2026-06-18: Added audit text to phase reports. Consensus reports now include
`Generated Transcription` and `Generated Slide Mapping`; per-video
`comparison.md` reports include baseline, phase output, and old candidate
transcription/slide mapping; the aggregate `phase-gate-report.md` includes a
`Generated Content By Video` section. Slide mapping uses plain text with no
blank line between lines in the same slide and one blank line between slides.
The current full phase 1 run with these audit sections is
`phase1-audit-content-20260618T171000Z`, and validation confirmed all 11
consensus reports plus all 11 comparison reports contain the new sections.

2026-06-18: Added a reference lyric gate for `Deus é Refúgio` using
`quality_references/lyrics/-cFY8RAHkpc.txt`. The gate compares normalized word
edit distance against expected lyrics and also blocks material degradation from
the old baseline. Full phase 1 run `phase1-lyrics-ref-20260618T174000Z` loaded
the reference and failed as expected: baseline similarity 0.6202 / WER 0.3798,
phase similarity 0.4341 / WER 0.5659. This confirms content quality regressed
for that song, independent of layout metrics.

2026-06-18: Fixed misleading reference lyrics report labeling. The expected
lyrics were used only after generation for evaluation, but the aggregate report
previously placed them inside `Generated Content By Video`, which made
reference text look like generated output. Corrected reports now separate
`Expected Reference Lyrics By Video (Not Generated)` from `Output Content By
Video` and include an evaluation-only notice. Corrected full run:
`phase1-lyrics-ref-clear-report-20260618T181000Z`.

2026-06-18: Created revised plan
`docs/plans/2026-06-18-consensus-quality-revised-plan.md` after broader
research and the real gate. Key change: do not proceed to original phase 2.
First implement Phase A measurement and Phase B safe selector fallback, because
the current phrase consensus can be worse than the best individual candidate and
can fragment the timeline. The plan explicitly keeps reference lyrics
evaluation-only and forbids using them for candidate filtering or selection.

2026-06-18: Ran vocal-primary ASR validation at
`/tmp/louvorja-asr-batch-2026-06-18/vocal-primary-20260618T1900Z/`.
Generated `medium-vocals` and `turbo-vocals` `.slja` files with `htdemucs_ft`
before transcription, plus `vocal-primary-report.md` and per-video `content.md`
files. Result: `turbo-vocals` dramatically improved `Deus é Refúgio` against
the evaluation-only reference (0.8760 similarity), but vocal-only is not safe as
a universal final output because `medium-vocals` failed on 2 songs and
`turbo-vocals` produced very short/repetitive content in some cases.

2026-06-18: Implemented vocal-first phase 1 ordering and a whole-candidate
fallback selector. Current full gate:
`/tmp/louvorja-asr-batch-2026-06-18/phase-history/phase-1/phase1-vocal-first-fallback3-20260618T2010Z/`.
It completes all 11 videos and fixes the `Deus é Refúgio` reference gate
(baseline 0.6202 -> phase 0.8760) while preserving 0 hard-limit lines, but the
robust phase gate still fails on slide/line expansion and auxiliary words:
slides 130 -> 173, lines 237 -> 332, aux words 18 -> 41. A prior interrupted
run exposed an unbounded layout search when scoring whole candidates; that is
fixed by bounded layout scanning and phrase-level fallback scoring.
