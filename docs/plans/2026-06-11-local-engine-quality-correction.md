# Local Engine Quality Correction Plan

## Root Cause

The real local run with `ADORADORES 3 - FE E ACAO.mp3` produced a structurally
valid `.slja`, but the content was not acceptable for worship slides.

Observed issues:

- The run bypassed quality stages with `--vocal-separation none` and
  `--alignment none`.
- The transcript had weak timing quality: sparse useful gaps and zero-duration
  tokens.
- The slide planner accepted a dense result with too much essential lyric text
  in `letra_aux`.
- The CLI wrote the archive without any objective quality check.
- Installing the full local engine was not reproducible on a fresh WSL machine
  because `audio-separator` dependencies need Python headers and build tools.

## Implemented Guardrails

- Add `scripts/install_linux_local_engine.sh` for reproducible Linux/WSL setup.
- Pin direct Python dependencies in `requirements.txt`.
- Add slide/transcript quality analysis.
- Make `--quality-gate fail` the CLI default, before `write_slja`.
- Allow operator overrides with `--quality-gate warn` or `--quality-gate off`.
- Preserve the local `Transcript` on the generated document so timestamp quality
  can be checked before packaging.

## Remaining Corrections

- Wire a real MMS/torchaudio forced-alignment runner behind `--alignment mms`.
- Re-run the real song with the complete path:

```bash
python audio_to_slja.py "ADORADORES 3 - FÉ E AÇÃO.mp3" \
  --engine local \
  --whisper-model large-v3 \
  --vocal-separation htdemucs_ft \
  --alignment mms \
  --quality-gate fail \
  --output local_outputs/adoradores3-fe-acao.slja
```

- Rewrite slide planning so `letra_aux` is a rare fallback, not the main escape
  hatch for dense lyrics.
- Add a lyrics-first mode for production use when the expected lyrics are known.
