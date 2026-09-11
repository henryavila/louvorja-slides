# Session Handoff: SLJA Quality And Lyrics-First

## Branch

- Branch: `feat/slja-quality-local-only`
- Base: `main` at `b641a9f feat: harden local engine alignment, caching, and quality gate`
- Do not assume this branch is pushed; check `git status` and `git branch -vv`
  in the next session.

## Commits Made

- `667d51b feat: validate existing slja archives`
  - Adds existing `.slja` archive reading/validation.
  - Extends the quality gate with empty-slide, hard-line, and fast-transition
    checks.
  - Updates CLI validation output and related tests.

- `dab3a2b fix: prefer readable lyric slide breaks`
  - Makes `letra_aux` a short fallback instead of normal dense-lyric overflow.
  - Prefers readable natural endings and avoids bad duration fallbacks.
  - Adds layout regression tests.

- `8720771 refactor: make transcription engine local-only`
  - Removes the Titan runtime engine path.
  - `--engine auto` and `--engine local` now use the in-repo local pipeline on
    macOS, Linux, and WSL.
  - `--engine titan` must remain removed/rejected.
  - `--device mps` is a local forced-alignment device preference, not a Titan
    backend.

## Runtime Rule

`../titan-chordpro-lib` is reference material only. Do not import it, install it
as a runtime dependency, or call its orchestrator from this project.

It is acceptable to read Titan code and copy/adapt small implementation ideas
into this repository.

## Validation Done

Passed:

```bash
python3 -m unittest tests.test_engines tests.test_cli -v
python3 -m compileall audio_to_slja.py louvorja_slides tests
```

Known limitation in this shell:

```bash
python3 -m unittest discover -s tests -v
```

fails before running the ML-heavy tests because the system Python lacks `numpy`.
Use a local project venv with `requirements.txt` installed before treating the
full suite as green.

## Real Sample Context

User sample:

```text
/Users/henry/Library/CloudStorage/OneDrive-Pessoal/Música/Ministério Tons/Cifras Ministério Tons/Slides músicas/Outros slides/Eu sou Calebe - 2024.slja
```

The original archive fails the new archive gate with:

- 1 empty lyric slide
- 1 main line over the 34-character hard limit
- 4/33 fast transitions

A generated comparison sample at `/tmp/eu-sou-calebe-generated-v5.slja` passed
the structural gate after layout fixes, but the ASR text still had lyric
mistakes. That is why `lyrics-first` is the next work item.

## Next Work

Implement lyrics-first mode using:

```text
docs/plans/2026-06-17-lyrics-first-handoff.md
```

Suggested first steps:

1. Add `louvorja_slides/lyrics.py` with plaintext lyric parsing and normalized
   token matching helpers.
2. Add tests before wiring CLI:
   - expected casing/accent preservation,
   - ASR `Caleb` matching expected `Calebe`,
   - skipped ASR filler/bracket words,
   - interpolated timings for missing ASR words,
   - repeated chorus mapping stays monotonic,
   - low alignment coverage fails quality.
3. Wire `--lyrics-file` and optional `--lyrics-text`.
4. Keep `.slja` validation mode separate from lyrics-first generation.
5. Cache the lyrics-aligned stage with a lyrics content hash and algorithm
   revision.

## Guardrails

- No real user audio, lyrics, or `.slja` archives should be committed unless the
  user explicitly asks.
- Do not weaken the quality gate to make a sample pass.
- Older plan docs may mention Titan runtime behavior. Treat those as historical
  unless they match the current runtime rule above.
