# LouvorJA Slides

Generate LouvorJA `.slja` files from local audio. The CLI selects the
transcription engine automatically: local Linux/WSL on Linux, and Titan on
macOS.

## Setup On Linux/WSL

```bash
./scripts/install_linux_local_engine.sh
# optionally pre-download the ~1.2 GB MMS alignment model:
./scripts/install_linux_local_engine.sh --prefetch-models
```

If the script reports missing OS packages, run the command it prints. On a
fresh Ubuntu/WSL workstation this is usually:

```bash
sudo apt-get update && sudo apt-get install -y python3.12-dev python3.12-venv build-essential ffmpeg git
```

The local engine is quality-first and slower than a mock path. It runs vocal
separation and Whisper word timestamps by default, then feeds the existing
LouvorJA slide planner/exporter.

## Setup On macOS With Titan

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -e ../titan-chordpro-lib[mac]
```

`--engine auto` uses Titan on macOS. Use `--engine titan` to force it from any
platform where the dependency is installed.

## Usage

```bash
python audio_to_slja.py song.mp3 --title "Song" --output song.slja
python audio_to_slja.py video.mp4 --title "Song" --output song.slja
```

Engine overrides:

```bash
python audio_to_slja.py song.mp3 --engine local --whisper-model medium --output song.slja
python audio_to_slja.py song.mp3 --engine titan --device mps --output song.slja
python audio_to_slja.py song.mp3 --engine titan --device mock --output song.slja
```

The local engine defaults to `--vocal-separation htdemucs_ft` and
`--alignment none`. `--alignment mms` is available behind the alignment contract,
but requires a wired MMS/torchaudio implementation in the environment.

`--device mock` and `--device mps` are Titan-only options; the local engine
rejects them with an error instead of silently running the real pipeline.
On the local engine, `--device cpu`/`--device cuda` select the device used by
MMS forced alignment.

Generated output is checked by a quality gate before the archive is written.
The default is `--quality-gate fail`, which rejects suspicious output such as
too much essential lyric text in `letra_aux`, long main lines, weak local
word timestamps, or a run that produced no lyric slides at all. Use
`--quality-gate warn` to write the archive while preserving the diagnostics,
or `--quality-gate off` only for low-level debugging.

The generated `.slja` archive contains:

- `slides.lja`
- `audio\<input filename>`
- `imagens\Capa.jpg`
- `imagens\slides.jpg`

`slides.lja` is written in LouvorJA's CP1252/CRLF style with slide timestamps in
`HH:MM:SS`. The cover slide uses `imagens\Capa.jpg`; all lyric slides use
`imagens\slides.jpg`, matching the reference archive layout.

## Slide Layout Rules

The generator plans lyric slides with congregation readability in mind:

- max 2 main lyric lines per slide;
- target 28 characters per line, with hard tolerance up to 34;
- prefer breaks after punctuation or vocal/musical pauses;
- avoid breaks after weak words such as `de`, `em`, `que`, `e`, `nao`;
- avoid fast one-line slide transitions when adjacent phrases fit together;
- use `letra_aux` as an overflow fallback or as an automatic `(Nx)` marker
  when consecutive generated slides have the same lyric lines.

Real `.slja` files used for local validation should go in `local_samples/`. That
directory is ignored by Git so operator examples are not committed accidentally.

## Consensus Phase Gates

Consensus phases must be validated against the complete batch, not only unit
tests or spot checks. Use the phase gate runner so every phase keeps its own
history and preserves the old-process artifacts:

```bash
python scripts/phase_gate_consensus.py \
  --batch-root /tmp/louvorja-asr-batch-2026-06-18 \
  --metadata-jsonl /tmp/louvorja-asr-batch-2026-06-18/metadata.jsonl \
  --phase 1 \
  --mode execute
```

The runner writes a new immutable run under
`<batch-root>/phase-history/phase-<phase>/<run-id>/`. Each run contains:

- `baseline-old-process/`: copied old `.slja` candidates, `best.slja`,
  old aggregate reports, and input metadata;
- `phase-output/<video_id>/best-consensus.slja`;
- `phase-output/<video_id>/consensus-report.md`;
- `phase-output/<video_id>/comparison.md` and `.json`;
- `phase-gate-report.md` and `.json`;
- `phase-effort-report.md` and `.json`, with elapsed time, cache growth, and
  output size for the phase run.

The default expected batch size is 11. A run with `--limit` is useful for
debugging, but the phase gate report will not mark it as a full-set pass.

If `quality_references/lyrics/<video_id>.txt` exists, the phase gate also
checks the generated phase output against that expected lyric text. This gate
uses normalized word edit distance and fails when the output is below the
reference similarity threshold or regresses materially against the old-process
baseline. Use `--reference-lyrics-dir <path>` to point the gate at a different
reference set.
