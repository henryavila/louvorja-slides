# LouvorJA Slides

Generate LouvorJA `.slja` files from local MP3/MP4 audio. The project owns the
LouvorJA packaging, slide layout, and local transcription pipeline; it no longer
depends on `titan-chordpro-lib` at runtime.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

The local transcriber is quality-first, not speed-first. The intended full path
is vocal separation, Whisper `large-v3` word timestamps, MMS forced alignment,
and then the existing slide planner/exporter.

Current implementation note: the orchestration, cache, CLI, audio decode,
vocal-separation adapter, Whisper adapter, and `.slja` generation are in this
repo. The real MMS alignment backend is deferred to the ML phase; with the
default `--alignment mms`, the pipeline fails clearly until that backend lands.
Use `--alignment none` only as an explicit local smoke-test bypass.

## Usage

Current runnable smoke path while MMS is deferred:

```bash
python audio_to_slja.py song.mp3 --title "Song" --output song.slja \
  --vocal-separation none --alignment none --whisper-model medium
python audio_to_slja.py video.mp4 --title "Song" --output song.slja \
  --vocal-separation none --alignment none --whisper-model medium
```

Intended quality-first command after the MMS backend lands:

```bash
python audio_to_slja.py song.mp3 --title "Song" --output song.slja
```

Transcript-only smoke script:

```bash
python scripts/smoke_local_transcription.py local_audio/song.mp3 --alignment none
```

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

Local audio, generated outputs, and transcription cache should go in
`local_audio/`, `local_outputs/`, and `.louvorja-cache/`; all three are ignored
by Git.
