# Audio To SLJA Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local CLI that converts an audio file into a LouvorJA `.slja` archive using `titan-chordpro-lib` as a dependency.

**Architecture:** Keep all LouvorJA-specific code in this repository. Use Titan only through its public `transcribe()` function, then convert the returned document shape into LouvorJA slides and package the archive.

**Tech Stack:** Python 3.12, stdlib `argparse`, `zipfile`, `unittest`, local editable dependency on `../titan-chordpro-lib`.

---

### Task 1: Exporter Tests

**Files:**
- Create: `tests/test_slja.py`
- Create: `louvorja_slides/__init__.py`
- Create: `louvorja_slides/slja.py`

**Step 1: Write failing tests**

Cover:

- `format_timestamp(0) == "00:00:00"`
- `format_timestamp(65.9) == "00:01:05"` so slide cues do not start late.
- Rendering includes `[Geral]`, `audio=audio\song.mp3`, and lyric lines separated by `|`.
- ZIP output contains `slides.lja` and `audio\song.mp3`.

**Step 2: Run tests**

Run: `python3 -m unittest tests.test_slja -v`

Expected: tests fail because `louvorja_slides.slja` does not exist.

**Step 3: Implement exporter**

Implement small dataclasses/functions:

- `Slide`
- `format_timestamp(seconds)`
- `extract_lyric_slides(doc, lines_per_slide=2)`
- `render_lja(slides, title, audio_name, ...)`
- `write_slja(audio_path, output_path, slides, title, ...)`

**Step 4: Run tests**

Run: `python3 -m unittest tests.test_slja -v`

Expected: pass.

### Task 2: CLI

**Files:**
- Create: `audio_to_slja.py`
- Create: `requirements.txt`
- Create: `README.md`
- Test: `tests/test_cli.py`

**Step 1: Write failing CLI tests**

Use `unittest.mock` to patch `audio_to_slja.transcribe` and assert the CLI writes a `.slja`
without running ML.

**Step 2: Run tests**

Run: `python3 -m unittest tests.test_cli -v`

Expected: fail because `audio_to_slja.py` does not exist.

**Step 3: Implement CLI**

CLI options:

- positional `audio`
- `--output`
- `--title`
- `--language`, default `pt`
- `--lines-per-slide`, default `2`
- `--device`, choices `auto`, `mps`, `cuda`, `cpu`, `mock`
- `--whisper-model`
- `--no-cache`

**Step 4: Run tests**

Run: `python3 -m unittest discover -s tests -v`

Expected: pass.

### Task 3: Local Verification

**Files:**
- No new files unless tests expose a gap.

**Step 1: Run full local test suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: pass.

**Step 2: Inspect archive shape**

Create a tiny dummy audio fixture in a temp directory during tests and verify the archive
contains valid CP1252 `slides.lja` and embedded audio bytes.

**Step 3: Document Mac command**

README should show:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -e ../titan-chordpro-lib[mac]
python audio_to_slja.py song.mp3 --title "Song" --output song.slja
```

Do not claim the ML path passes on Linux/WSL.
