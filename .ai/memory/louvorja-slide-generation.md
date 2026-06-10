# LouvorJA Slide Generation

## Product Intent

- This project generates LouvorJA `.slja` archives from local `.mp3` or `.mp4`
  audio files.
- `titan-chordpro-lib` is used as a local dependency for audio transcription and
  word timestamps, but the LouvorJA-specific export/layout code lives in this
  repository.
- The Linux/WSL environment can run unit tests and packaging smoke tests, but
  real transcription is expected to be validated on macOS with the Titan local
  dependency installed.
- Real user-provided `.slja` files are validation samples only. Keep them under
  `local_samples/` and do not commit them unless explicitly requested.

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
- Consecutive generated slides with identical main lines are collapsed into one
  slide with `letra_aux=(Nx)`, preserving the first start timestamp and the last
  end timestamp. Non-consecutive repetitions stay separate.
- Do not generate `(Nx)` when repeated text already fits in the same slide.

## Review Findings To Preserve

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
