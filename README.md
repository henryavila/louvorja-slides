# LouvorJA Slides

Generate LouvorJA `.slja` files from local audio using `titan-chordpro-lib` as
the transcription dependency.

## Setup On Mac

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

The real Titan pipeline is supported on macOS Apple Silicon. This WSL/Linux
workspace can run the local packaging tests, but should not be treated as a real
MP3/MP4 transcription environment.

## Usage

```bash
python audio_to_slja.py song.mp3 --title "Song" --output song.slja
python audio_to_slja.py video.mp4 --title "Song" --output song.slja
```

Useful smoke test without ML:

```bash
python audio_to_slja.py song.mp3 --device mock --output song.slja
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
