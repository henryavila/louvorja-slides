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

`slides.lja` is written in LouvorJA's CP1252/CRLF style with slide timestamps in
`HH:MM:SS`.
