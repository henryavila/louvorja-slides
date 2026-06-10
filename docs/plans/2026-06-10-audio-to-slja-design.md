# Audio to LouvorJA SLJA Design

## Goal

Build a local `louvorja-slides` tool that receives one audio file (`.mp3` or `.mp4`
initially) and writes a LouvorJA `.slja` archive with the audio embedded and lyrics
timed from the audio transcription.

## Scope

The script belongs to this project, not to `titan-chordpro-lib`. Titan is used as
a dependency that supplies audio transcription, word timestamps, and inferred lyric
sections.

First version:

- Input: one local audio file.
- Output: one `.slja` ZIP archive.
- Lyrics: generated from Titan's transcription output.
- Timing: each LouvorJA slide receives the timestamp of its first lyric line.
- External lyrics: out of scope for the first version.
- Real ML verification: deferred to macOS Apple Silicon, where Titan is supported.

## Architecture

`audio_to_slja.py` is the operator CLI. It imports `titan_chordpro.orchestrator.transcribe`
from the current environment, runs it with cache enabled by default, then passes the
resulting document to a small local `louvorja_slides.slja` exporter.

The exporter is deliberately independent from Titan internals where possible. It accepts
objects with the same shape as Titan's `ChordProDocument`, extracts lyric lines, groups
them into slides, renders `slides.lja` as CP1252 text with CRLF line endings, and writes a
ZIP archive containing:

- `slides.lja`
- `audio\<original-audio-filename>`
- `imagens\Capa.jpg`
- `imagens\slides.jpg`

The cover slide uses `imagens\Capa.jpg`. Every lyric slide uses
`imagens\slides.jpg`, matching the reference `.slja`.

## LouvorJA Format Notes

Observed from `102 Fala comigo.slja`, the official database, and strings in
`LouvorJA.exe`:

- `.slja` is a ZIP archive.
- `slides.lja` is an INI-like file.
- Text encoding is Windows CP1252.
- Line endings are CRLF.
- Slide text line breaks use `|`.
- Official slide timestamps use `HH:MM:SS`.
- Audio export uses the `[Geral]` `audio` key and stores media under `audio\`.

## Testing

Local tests cover the pure exporter:

- `HH:MM:SS` timestamp formatting.
- Lyric extraction and grouping.
- CP1252 `slides.lja` rendering.
- `.slja` ZIP members and embedded audio bytes.

The full ML path cannot be verified on this WSL2 machine because Titan's supported
runtime is macOS Apple Silicon.
