# LouvorJA Slide Generation

## Product Intent

- This project generates LouvorJA `.slja` archives from local `.mp3` or `.mp4`
  audio files.
- Audio transcription now goes through an engine contract. `auto` selects the
  local engine on macOS, Linux, and WSL.
- `titan-chordpro-lib` is reference-only. Do not add it as a runtime
  dependency, import it, or call it from this project; copy/adapt only the
  needed implementation ideas into this repository.
- The local engine ports only the Titan decisions needed for slides: Whisper
  word timestamps, quality transcription arguments, bracket-token filtering,
  cache keys by quality configuration, and adaptive phrase grouping.
- Real user-provided `.slja` files are validation samples only. Keep them under
  `local_samples/` and do not commit them unless explicitly requested.
- Linux/WSL local setup is reproducible through
  `scripts/install_linux_local_engine.sh`. On fresh Ubuntu/WSL, the known apt
  prerequisites are `python3.12-dev`, `python3.12-venv`, `build-essential`,
  `ffmpeg`, and `git`.
- A real ASR-only run of `ADORADORES 3 - FE E ACAO.mp3` with `medium`,
  `--vocal-separation none`, and `--alignment none` produced a structurally
  valid but poor archive: 19 lyric slides for about 4:56, excessive essential
  lyrics in `letra_aux`, long main lines, and weak word timestamps. Keep quality
  gates on by default before writing `.slja`.
- After installing Linux dependencies, the same song with `medium`,
  `--vocal-separation htdemucs_ft`, and `--alignment none` still failed the
  quality gate: 20 lyric slides, 30.6% auxiliary lyric words, 80.0% auxiliary
  lyric slides, 40.0% lines over target, and transcript positive gap ratio 0.0%.
  Vocal separation alone is not enough; the local path needs real forced
  alignment and planner changes before production use.
- `audio-separator==0.44.2` imports `audio_separator.separator`, which also
  requires `onnxruntime`; keep `onnxruntime` as a direct pinned dependency and
  verify the submodule import in the Linux installer.
- Titan's high-quality chord/syllable placement comes from a full alignment
  chain, not Whisper timestamps alone: `torchaudio.pipelines.MMS_FA` creates
  20ms-frame forced-alignment token spans over stitched chunked emissions,
  those spans become `PhonemeEvent`s, syllabification groups phonemes into
  `SyllableEvent`s, and the placer anchors chords to melisma/stressed/nearest
  syllables before falling back to word starts. Porting this repo's alignment
  should bring over that real MMS runner and preserve phoneme/syllable timing.

## Slide Layout Decisions

- Main lyric slides use at most two lyric lines.
- The target line length is 28 characters, with a hard tolerance of 34
  characters when that avoids fast or awkward slide transitions.
- Prefer line breaks at punctuation or vocal/musical pauses, but do not treat a
  detected natural pause as exclusive. If the natural break makes a line too
  long, search for another readable two-line break before using `letra_aux`.
- Avoid ending a line on weak connector words such as `de`, `em`, `que`, `e`,
  or `nao`.
- `letra_aux` is valid as short overflow text or as an automatically counted
  repetition marker `(Nx)`.
- Quality gates must not count `(Nx)` repetition markers as bad auxiliary
  lyric text.
- Consecutive generated slides with identical main lines are collapsed into one
  slide with `letra_aux=(Nx)`, preserving the first start timestamp and the last
  end timestamp. Non-consecutive repetitions stay separate.
- Do not generate `(Nx)` when repeated text already fits in the same slide.

## Review Findings To Preserve

- Status snapshot on 2026-06-17: `main` is clean at
  `feat: harden local engine alignment, caching, and quality gate`. The repo has
  the CLI, SLJA exporter, engine contract, local pipeline, MMS aligner, quality
  gate, install script, smoke script, plans, and tests. There is no active
  `.atomic-skills/PROJECT-STATUS.md`; `.atomic-skills/` currently contains only
  review artifacts.
- Verification snapshot on 2026-06-17: `python3 -m compileall audio_to_slja.py
  louvorja_slides tests scripts` passes on the system Python. `python3 -m
  unittest discover -s tests -v` finds 69 tests but errors on missing `numpy` in
  the system Python and one `louvorja_slides.local_pipeline` patch/import path.
  Re-run in the intended venv before treating the suite as green.
- Production validation remains open: run a real song through `--alignment mms`
  with `--quality-gate fail`, verify nonzero phonemes and mostly
  `source="mms_align"` in the aligned cache, then compare slide quality metrics.
- Status update on 2026-06-17: existing `.slja` archives can be read and
  checked directly by the CLI. The `Eu sou Calebe - 2024.slja` reference fails
  the new archive gate with 1 empty lyric slide, 1 line over the 34-char hard
  limit, and 4/33 fast transitions.
- Real macOS validation on 2026-06-17 used the audio extracted from
  `Eu sou Calebe - 2024.slja` and a temporary Titan-reference run to compare
  behavior. That run must not become a project dependency. The first generated
  output failed because 16/18 lyric slides used `letra_aux`; after tightening
  layout selection, `/tmp/eu-sou-calebe-generated-v5.slja` passed the gate with
  27 lyric slides, 0 aux slides, 0 empty slides, 0 hard-limit lines, 0/26 fast
  transitions, 3/54 lines over the 28-char target, and median line length 23.
- Lyrics-first was already in
  `docs/plans/2026-06-11-local-engine-quality-correction.md`; the actionable
  handoff for the next session is
  `docs/plans/2026-06-17-lyrics-first-handoff.md`.
- Branch `feat/slja-quality-local-only` contains micro-commits for archive
  validation, layout quality, and local-only runtime. Session handoff:
  `docs/plans/2026-06-18-session-handoff.md`.

- `LayoutConfig.max_lines_per_slide` must be enforced by the planner. The CLI
  exposes `--lines-per-slide`, so `lines_per_slide=1` cannot produce two-line
  slides.
- Natural split candidates are preferred, not mandatory. A previous
  implementation used `natural_splits or range(...)`, which skipped valid
  non-natural breaks whenever any natural split existed and could push readable
  text into `letra_aux`.
- When there are enough natural pauses to form main text plus short auxiliary
  text, the auxiliary layout can be preferable to breaking in the middle of a
  phrase. Keep tests for both paths.
- The MMS port must pin and verify matching `torch`/`torchaudio` versions.
  In this local package index, `torch` is available through `2.12.0` but
  `torchaudio` only through `2.11.0`; use the verified pair
  `torch==2.11.0` and `torchaudio==2.11.0`.
- MMS tokenizer failures must not discard the whole target sequence. Tokenize
  per word, preserve original word offsets, skip only rejected words, and raise
  an explicit alignment error when no target tokens remain.
- The real `torchaudio.pipelines.MMS_FA` tokenizer has no `decode()` method.
  Map aligned token IDs back to symbols with `MMS_FA.get_labels()`; numeric
  fallback symbols are stale/bad cache data.
- Cache regression tests for aligned transcripts must seed stale schema data and
  prove the aligner runs and writes phonemes. Checking `_CACHE_SCHEMA_VERSION`
  or `_variant()` alone is not enough.
- Real MMS smoke verification must execute the aligner and require nonzero
  phonemes; `py_compile` is only a syntax gate.
- Real-song quality metrics must read the deterministic aligned cache produced
  by that run, not the newest transcript file under the global cache.
- Chunked MMS emissions must keep exactly `window_samples / 320` frames per
  chunk. The wav2vec2 conv stack emits 1699 frames for a 34 s chunk (not
  1700), so cropping a fixed context count from both ends drops one inner
  frame per chunk and drifts timestamps ~20 ms earlier per 30 s window
  (measured +0.18 s at the end of a 4:56 song). Stitching tests must encode
  frame indices into emission values; shape-only assertions cannot catch
  wrong crop offsets.
- Refined transcripts must keep word order stable. Unalignable words (digits,
  punctuation-only) keep Whisper timing clamped between aligned neighbours;
  mixed Whisper/MMS timelines otherwise reorder under `Transcript`'s sort and
  corrupt phoneme `parent_word_idx`. `refine_words_from_spans` rejects
  non-monotonic aligned spans with `AlignmentError`.
- The aligned-stage cache variant includes `_ALIGNMENT_REVISION`. Bump it
  whenever alignment output changes for identical inputs so stale aligned
  transcripts recompute without invalidating expensive raw Whisper caches.
- The separation cache is per-model (`vocals-<model>.wav`) with a legacy
  `vocals.wav` fallback for the default model only. Separation runs in a
  unique temp stems dir per run (concurrent-safe), renames the vocals stem
  atomically into place, and deletes intermediate stems.
- `save_json` writes through a unique temp file plus `os.replace`; a fixed
  `.tmp` name lets concurrent writers corrupt each other.
- Whisper quality kwargs live once in `QUALITY_WHISPER_KWARGS`
  (`transcription.py`); the transcript cache key derives from it, so editing
  the kwargs auto-invalidates stale transcripts.
- The local engine rejects `--device mock`; `cpu`, `cuda`, and `mps` select the
  MMS forced-alignment device when the local stack supports them.
- The quality gate fails a run that produced zero lyric slides; empty-input
  ratios defaulting to 0.0 must not sail through the gate.
- Lyrics-first mode is implemented in-repo via `louvorja_slides/lyrics.py` and
  CLI flags `--lyrics-file`, `--lyrics-text`, and `--lyrics-mode`. Expected
  lyric words become the displayed text while ASR/local alignment supplies
  timings. The matcher normalizes case/accent/punctuation, allows fuzzy matches
  such as `Caleb` -> `Calebe`, skips bracket/filler ASR tokens, interpolates
  missing lyric word timings, and preserves lyric line/blank-line hints as
  planner boundaries.
- The lyrics-aligned cache lives under the `lyrics-aligned` stage and its key
  includes the lyrics text hash, source transcript hash, language, and
  `LYRICS_ALIGNMENT_REVISION`; edited lyrics or changed ASR output must not
  reuse stale lyrics-aligned transcripts.
- The quality gate now accepts a lyrics alignment report and fails coverage
  below 80% by default, including short unmatched lyric/ASR spans in the failure
  details.
- Real macOS validation on 2026-06-18 regenerated `Eu sou Calebe` with
  lyrics-first using `/tmp/eu-sou-calebe-2024.mp3`, lyrics temporarily extracted
  from the reference `.slja`, `--whisper-model medium`,
  `--vocal-separation none`, and `--alignment none`. Output
  `/tmp/eu-sou-calebe-lyrics-first.slja` passed archive validation: 26 lyric
  slides, 0 empty, 0 hard-limit lines, and 0/25 fast transitions. Lyrics
  alignment coverage was 207/217 tokens (95.4%), and displayed text had 11
  standalone `Calebe` occurrences and 0 standalone `Caleb` occurrences,
  compared with ASR-only v5 at 0 `Calebe` and 12 `Caleb`. Caveat: because the
  temporary lyrics came from the original `.slja`, any source lyric/casing
  mistakes in that archive are preserved by design.
- YouTube validation on 2026-06-18 for `https://youtu.be/9yZt5ekdceI` generated
  `/tmp/louvorja-youtube-9yZt5ekdceI/ao-olhar-pra-cruz.slja` from ASR-only
  transcription (`medium`, `--vocal-separation none`, `--alignment none`).
  Initial output passed structural validation but used LouvorJA audio metadata
  unlike reference archives (`audio=<path>` instead of `url_musica=<path>` plus
  `audio=1`), kept punctuation-only music tokens as `?`, and grouped slides too
  much by character count. The corrected output at the same path uses sanitized
  embedded audio filenames, `url_musica`/`audio=1`, filters punctuation-only
  tokens, and preserves phrase-line hints before wrapping long phrase lines.
  Final archive validation passed: 23 lyric slides, 0 empty, 0 hard-limit lines,
  0/22 fast transitions, 2/39 lines over the 28-character target, and median
  line length 18. Because no lyrics file was supplied, displayed text remains
  Whisper-derived and must be manually reviewed for lyric correctness.
- Slide planning now treats detected musical boundaries (source lyric line or
  section changes, punctuation endings, and pauses at least
  `phrase_pause_seconds`) as hard slide/auxiliary content boundaries when such
  boundaries are present. Character limits can still choose line wraps inside a
  slide, but they must not move part of a musical phrase to a later slide or
  into `letra_aux`.
- ASR improvement sweep for the YouTube sample on 2026-06-18 used a temporary
  Python 3.13 venv with `pywhispercpp==1.5.0`, no LLM, and no manual lyric
  edits. Tested Whisper `base`, `small`, cached `medium`, `medium` segment
  mode, context/beam/prompt variants, FFmpeg `afftdn`/`dynaudnorm` and
  voice-EQ preprocessing, and `large-v3-turbo`; full `large-v3` download
  stalled at 577 MB and was aborted. Best automatic archive:
  `/tmp/louvorja-youtube-9yZt5ekdceI/ao-olhar-pra-cruz-auto-best.slja`, copied
  from `candidate-medium-segments-denoise.slja`. It passed archive validation
  with 27 lyric slides, 0 empty, 0 hard-limit lines, and 0/26 fast transitions.
  It improves the bad phrase from `Derramado a me topir` to
  `Derramado a me pôr-me`, but none of the tested ASR-only strategies produced
  the desired `derramado ali por mim` exactly.
- Batch ASR experiment on 2026-06-18 for 11 user-provided YouTube songs lives
  at `/tmp/louvorja-asr-batch-2026-06-18/experiment/`. Script:
  `scripts/asr_batch_experiment.py`. It tested Whisper `medium` original,
  denoise/dynamic normalization, voice-EQ, `large-v3-turbo` original/denoise,
  and direct YouTube Portuguese caption import where available. Best `.slja`
  archives were written as `<video_id>/best.slja`; consolidated report:
  `/tmp/louvorja-asr-batch-2026-06-18/experiment/asr-experiment-report.md`.
  Result: `medium-denoise` won most often (4/11), `medium-original` won 3/11,
  `turbo-denoise` 2/11, `medium-voice-eq` 1/11, and `turbo-original` 1/11.
  `large-v3-turbo` and voice-EQ are not consistently better on congregational
  mixes; denoise is the safest ASR-only improvement when it does not increase
  hard line failures. Auto YouTube captions were available in Portuguese for
  only two songs and were noisy enough not to win. OCR over lyric videos is the
  next promising non-LLM/non-human technique, but no local OCR engine was
  available in that run.
- Phase 1 phrase-level consensus is implemented in
  `louvorja_slides/consensus.py` and exposed with
  `--transcription-strategy consensus`. It automatically tries
  `medium-original`, `medium-denoise`, `medium-vocals`, `turbo-original`, and
  `turbo-vocals`, plus optional `--youtube-caption-file` VTT, then groups
  phrase candidates by time/text similarity and scores whole phrases by
  agreement, layout risk, word-count coverage, temporal stability, and
  repetition. Consensus writes a Markdown report by default at
  `<output>.consensus-report.md` unless `--report-path` is supplied. Phases
  `2`, `3`, `4`, and `full` intentionally fail until ROVER-lite/OCR/final
  engine work is implemented. Full 11-song validation remains pending because
  the system Python lacked `numpy`; use the project dependency environment.
- Phase gate history is implemented in `scripts/phase_gate_consensus.py`.
  The operational gate for every consensus phase is: run the complete expected
  batch (default 11 videos), preserve a snapshot of the old-process artifacts
  from `<batch-root>/experiment`, generate per-video phase outputs, and compare
  each phase output against old `best.slja`. The runner writes immutable
  history under `<batch-root>/phase-history/phase-<phase>/<run-id>/`, including
  `baseline-old-process/`, `phase-output/<video_id>/best-consensus.slja`,
  `consensus-report.md`, per-video `comparison.md/.json`, and aggregate
  `phase-gate-report.md/.json`. `--limit` is debug-only: reports mark it as
  not a full-set gate pass.
- Phase gates must persist operational cost as a decision variable, not only
  quality metrics. For each model/approach under comparison, keep elapsed time,
  cache/storage growth, dependency/setup friction, and any failure/manual
  recovery notes alongside the `.slja` and comparison artifacts so future
  choices can balance quality against effort.
- Phase 1 execute gate on 2026-06-18 ran the complete 11-song batch with run id
  `phase1-execute-20260618T134909Z` under
  `/tmp/louvorja-asr-batch-2026-06-18/phase-history/phase-1/`. It completed all
  11 comparisons but failed the pass criterion: old-process `best.slja` totaled
  23 hard-limit lines, phase 1 consensus totaled 30, delta `+7`. Reports:
  `phase-gate-report.md/.json` and supplemental `phase-effort-report.md/.json`.
  The inferred video-level processing time was 59m27s total, 5m24s average per
  video; slowest videos were `txuPSdSn62M` 8m02s, `pdu52H3o0vk` 7m00s, and
  `mWw_x_B19oo` 6m43s. Phase cache ended near 441 MiB, run history near
  506 MiB, and pywhispercpp model storage near 4.10 GiB. Do not advance to
  phase 2 as if phase 1 had passed; first analyze/fix the phrase scorer/layout
  regressions or compare a cheaper alternative.
- `scripts/phase_gate_consensus.py` now records video-level effort metrics for
  future gates: elapsed time, cache before/after/delta, phase output size, and a
  dedicated `phase-effort-report.md/.json`. It still does not record
  per-source candidate timing inside `build_phase1_consensus`; add that before
  using runtime to choose among individual candidates such as `medium-denoise`
  versus `turbo-vocals`.
- Phase 1 regression analysis on 2026-06-18 found that the failed gate was
  primarily a layout/planner issue, not only a phrase scorer issue. The planner
  accepted an overlong candidate when a far "strong boundary" existed, causing a
  whole vocal region to become one invalid slide. It also treated automatic
  ASR-generated line breaks as rigid source line hints, which made the later
  fix explode slides and fast transitions. The fix now rejects overlong strong
  boundary layouts, adds a bounded relaxed fallback to find non-overlong splits
  when musical/source boundaries would otherwise force overlong text, and only
  freezes line/section boundaries when the document line explicitly carries
  `source_line_index`/`source_section_index`.
- Final corrected phase 1 full-set gate run:
  `/tmp/louvorja-asr-batch-2026-06-18/phase-history/phase-1/phase1-fix4-20260618T160700Z/`.
  It processed all 11 videos and passed the official hard-line criterion:
  old-process baseline hard-limit lines 23, phase 1 consensus hard-limit lines
  0, delta `-23`. Cost/effort for the cached rerun was 2m16s total video time,
  12s average per video, 0 B cache growth, and 70.7 MiB phase output history.
  Slowest video was `txuPSdSn62M` at 1m30s.
- Do not treat phase 1 as quality-complete solely because the official
  hard-line gate passed. Secondary layout metrics regressed on the same
  corrected run: slide count 130 -> 289, total lines 237 -> 543, target-limit
  lines 45 -> 113, fast transitions 0 -> 44, and auxiliary lyric words
  18 -> 70. Before advancing to phase 2, decide whether to accept this tradeoff
  or tighten the phase gate to include slide explosion, fast transitions, and
  auxiliary text.
- Root-cause analysis for that discrepancy: phrase-level consensus can select
  adjacent winners from different ASR sources whose phrase timestamps overlap
  or are too close together. In `phase1-fix4`, `txuPSdSn62M` had 103 consensus
  decisions, 48 overlapping adjacent decision windows, 66 adjacent decision
  starts under 3s apart, and median decision start gap of 2s; `SpWZF8jdfCA`
  had 56 decisions with 37 overlapping adjacent windows. The layout planner then
  correctly split text to remove hard-limit lines, but it converted those dense
  or overlapping decisions into many short slide starts. This is a consensus
  temporal-normalization problem, with layout only surfacing the issue.
- The phase gate was also too weak: `phase_gate_pass` previously meant only
  full-set complete plus hard-line non-regression. Robust phase gates now live
  in `scripts/phase_gate_consensus.py` and require hard-line non-regression plus
  bounded total/per-video slide ratio, line ratio, fast transition regression,
  auxiliary-word regression, and over-target line ratio. Regression tests in
  `tests/test_phase_gate.py` cover slide explosion and fast-transition
  regression even when hard-limit lines improve.
- Robust phase 1 gate run:
  `/tmp/louvorja-asr-batch-2026-06-18/phase-history/phase-1/phase1-robust-gate-20260618T163300Z/`.
  It processed all 11 videos and failed as intended: hard-line gate passed
  (23 -> 0), but slide-count gate failed (130 -> 289, ratio 2.223),
  line-count gate failed (237 -> 543, ratio 2.291), fast-transition gate failed
  (0 -> 44, phase ratio 15.8%), auxiliary-word gate failed (18 -> 70, delta
  52), and target-line gate failed due a per-video target-ratio breach. Cached
  effort remained 2m16s total, 12s average per video, 0 B cache growth, and
  70.7 MiB phase output. Do not advance to phase 2 until phase 1 either fixes
  temporal overlap/fragmentation or the team explicitly changes these thresholds.
- Gate reports now include audit text for validation. `format_consensus_report`
  writes `Generated Transcription` and `Generated Slide Mapping` sections. The
  phase runner writes baseline/phase/candidate transcription text and slide
  mapping into each per-video `comparison.md`, and the aggregate
  `phase-gate-report.md` includes `Generated Content By Video`. Slide mapping
  format is intentionally plain text: generated slide lines are adjacent, and a
  blank line separates slides. The full current phase 1 validation run with
  those sections is
  `/tmp/louvorja-asr-batch-2026-06-18/phase-history/phase-1/phase1-audit-content-20260618T171000Z/`.
  It still fails the robust gates, but all 11 consensus reports and all 11
  comparison reports have the audit sections for manual validation.
- Reference lyric gates are now supported by `scripts/phase_gate_consensus.py`.
  Add expected lyrics as `quality_references/lyrics/<video_id>.txt`, or pass
  `--reference-lyrics-dir`. When a reference exists, the phase gate computes
  normalized word edit distance against the phase output and also checks that
  the phase does not materially regress against the old-process baseline.
  Thresholds currently require phase word similarity at least 0.80 and no more
  than 0.02 similarity drop from the baseline. These checks run for all
  consensus phases handled by the phase gate, not just phase 1.
- `quality_references/lyrics/-cFY8RAHkpc.txt` stores the user-provided expected
  lyrics for `Deus é Refúgio`. Full phase 1 run
  `phase1-lyrics-ref-20260618T174000Z` loaded that reference and failed the
  reference gate: baseline old-process similarity 0.6202 / WER 0.3798; phase
  consensus similarity 0.4341 / WER 0.5659; reference word count 129, phase
  output word count 178. This confirms the user's observation: the phase output
  is not only poor against the expected lyrics, it is materially worse than the
  old baseline for this song.
- Root-cause follow-up for the misleading `Deus é Refúgio` report: the expected
  lyrics were never passed into `audio_to_slja.py` or consensus generation by
  the phase gate. They were read only after output generation by
  `lyric_reference_metrics()` for evaluation. The confusing artifact was a
  report-labeling bug: the aggregate `phase-gate-report.md` placed
  `Reference Lyrics` under a section named `Generated Content By Video`, making
  evaluation text look like generated text. Reports now separate
  `Expected Reference Lyrics By Video (Not Generated)` from
  `Output Content By Video`, and per-video comparison reports label the same
  content as evaluation-only. Corrected full run:
  `/tmp/louvorja-asr-batch-2026-06-18/phase-history/phase-1/phase1-lyrics-ref-clear-report-20260618T181000Z/`.
  It still fails the reference gate for `-cFY8RAHkpc`: baseline similarity
  0.6202, phase similarity 0.4341.
- Revised consensus plan on 2026-06-18:
  `docs/plans/2026-06-18-consensus-quality-revised-plan.md`. The broader
  research changed the phase order. Do not proceed to original phase 2 yet.
  First implement Phase A measurement and Phase B safe selector fallback.
  Evidence: current phrase consensus improved hard-limit lines but regressed
  slide count, line count, fast transitions, auxiliary words, and `Deus é
  Refúgio` reference similarity. The revised plan explicitly forbids using
  reference lyrics for candidate filtering, phrase scoring, fallback selection,
  prompts, or generated text; references are gate-only after generation.
- Vocal-primary validation on 2026-06-18 lives at
  `/tmp/louvorja-asr-batch-2026-06-18/vocal-primary-20260618T1900Z/`.
  It generated ASR-only `.slja` files with `htdemucs_ft` before transcription
  for `medium-vocals` and `turbo-vocals`, plus full slide-content reports.
  `turbo-vocals` succeeded for all 11 videos; `medium-vocals` failed with no
  transcribed words for `-cFY8RAHkpc` and `iB29MsdK6dE`. On `Deus é Refúgio`,
  `turbo-vocals` was much better than both the old baseline and phase 1
  consensus against the evaluation-only reference: baseline similarity 0.6202,
  phase consensus 0.4341, `turbo-vocals` 0.8760. However, vocal-only is not
  globally safe: `turbo-vocals` produced only 4 words for `cgNzy67c04E` and
  visible repetition/hallucination tails in some songs. Use separation as the
  first evidence-generation stage, but keep automatic fallback/eligibility
  checks before making vocal output final.
- Phase 1 now runs vocal-first candidate generation (`turbo-vocals`,
  `medium-vocals`, then original/denoise/original-turbo) and uses a
  whole-candidate fallback when phrase stitching is risky. The selector does
  not use reference lyrics; it scores source priority, coverage, repetition,
  and estimated layout risk, and rejects very short/long candidates. Reports
  include `Selection` with mode/source/reason.
- A failed attempt,
  `phase1-vocal-first-fallback-20260618T1930Z`, exposed a root-cause
  performance bug: scoring whole candidates with full layout extraction can
  drive `plan_lyric_slides` into an unbounded search on long timestamp runs
  with no musical pauses. `layout._longest_layout` now stops scanning once an
  unconstrained segment exceeds the maximum fittable text, and fallback scoring
  uses cheap phrase-level layout estimates for all candidates. Regression test:
  `test_long_timestamp_run_without_pauses_uses_bounded_layout_search`.
- Current vocal-first fallback gate:
  `/tmp/louvorja-asr-batch-2026-06-18/phase-history/phase-1/phase1-vocal-first-fallback3-20260618T2010Z/`.
  It processed all 11 videos in 33s cached time with 0 B cache growth and fixed
  the `Deus é Refúgio` reference gate: baseline similarity 0.6202 -> phase
  0.8760, selecting `turbo-vocals` without using the reference in generation.
  Robust phase gate still fails: slides 130 -> 173, lines 237 -> 332,
  fast transitions 0 -> 1, aux words 18 -> 41, over-target lines 45 -> 61.
  Remaining blockers are slide/line expansion on `SpWZF8jdfCA`,
  `iB29MsdK6dE`, and `mWw_x_B19oo`, plus one fast transition in
  `J-LrXdce3BQ`. Next work should compact/layout whole-candidate vocal output
  without losing the content gains.
- Phase 1 slide-phrase gate passed on the full 11-song set in
  `/tmp/louvorja-asr-batch-2026-06-18/phase-history/phase-1/phase1-slide-phrases-pass-20260619T0015Z/`.
  The key root cause was not raw slide count alone: some old-process baselines
  had very long invalid lines, so comparing raw slide/line count punished the
  valid output. The phase gate now uses hard-wrapped comparable baseline
  metrics and content-scaled per-video allowances for slide/line checks. In
  consensus mode only, SLJA extraction disables `letra_aux` and plans lines with
  a 28-character hard cap so generated slide mappings show all lyric text in
  main lines. Consecutive repeated slides collapse by normalized text, allowing
  case-only variants to become `(Nx)`. Final cached gate result: hard lines
  23 -> 0, over-target lines 45 -> 0, aux words 18 -> 0, slides 130 -> 183,
  lines 237 -> 346, fast transitions 0 -> 2 with 1.2% phase ratio, `Deus é
  Refúgio` reference similarity 0.8760, total cached elapsed 23s, 0 B cache
  growth, and phase gate pass `True`.
