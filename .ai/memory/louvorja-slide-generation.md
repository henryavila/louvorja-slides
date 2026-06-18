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
