#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable

from louvorja_slides.slja import extract_lyric_slides, write_slja

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".mp4"}
TranscribeFn = Callable[..., Any]


def load_transcribe() -> TranscribeFn:
    try:
        from titan_chordpro.orchestrator import transcribe
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "titan-chordpro-lib is not installed. Install the local dependency with "
            "`pip install -e ../titan-chordpro-lib[mac]` on the Mac."
        ) from exc
    return transcribe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a LouvorJA .slja archive from a local MP3/MP4 audio file."
    )
    parser.add_argument("audio", type=Path, help="Input .mp3 or .mp4 file")
    parser.add_argument("--output", type=Path, default=None, help="Output .slja path")
    parser.add_argument("--title", default=None, help="Song title for the cover slide")
    parser.add_argument("--language", default="pt", help="Transcription language code")
    parser.add_argument(
        "--lines-per-slide",
        type=int,
        default=2,
        help="Number of lyric lines per LouvorJA slide",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "mps", "cuda", "cpu", "mock"),
        default="auto",
        help="Titan backend preference. Use 'mock' for packaging smoke tests.",
    )
    parser.add_argument(
        "--whisper-model",
        default=None,
        choices=("tiny", "base", "small", "medium", "large-v2", "large-v3"),
        help="Override Titan's whisper.cpp model size.",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable Titan stage cache")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return run(args, transcribe_fn=load_transcribe())
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def run(args: argparse.Namespace, transcribe_fn: TranscribeFn) -> int:
    audio_path = Path(args.audio)
    if not audio_path.exists():
        raise FileNotFoundError(f"audio file not found: {audio_path}")
    if audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
        raise ValueError(f"unsupported audio extension {audio_path.suffix!r}; expected {allowed}")

    force_mock = args.device == "mock"
    backend = args.device if args.device not in ("auto", "mock") else None

    engine_kwargs: dict[str, Any] = {}
    if args.whisper_model is not None:
        engine_kwargs["transcription_model_id"] = args.whisper_model

    doc = transcribe_fn(
        audio_path,
        language=args.language,
        cache=not args.no_cache,
        force_mock=force_mock,
        backend=backend,
        **engine_kwargs,
    )

    title = args.title or _document_title(doc) or audio_path.stem
    slides = extract_lyric_slides(doc, lines_per_slide=args.lines_per_slide)
    output_path = Path(args.output) if args.output is not None else audio_path.with_suffix(".slja")

    write_slja(audio_path=audio_path, output_path=output_path, slides=slides, title=title)
    print(f"Wrote {output_path}")
    return 0


def _document_title(doc: Any) -> str | None:
    metadata = getattr(doc, "metadata", None)
    title = getattr(metadata, "title", None)
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


if __name__ == "__main__":
    raise SystemExit(main())
