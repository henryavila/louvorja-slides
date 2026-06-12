#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from louvorja_slides.engines import AudioToDocumentConfig, select_engine
from louvorja_slides.quality import enforce_quality
from louvorja_slides.slja import extract_lyric_slides, write_slja

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".mp4"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a LouvorJA .slja archive from a local MP3/MP4 audio file."
    )
    parser.add_argument("audio", type=Path, help="Input .mp3 or .mp4 file")
    parser.add_argument("--output", type=Path, default=None, help="Output .slja path")
    parser.add_argument("--title", default=None, help="Song title for the cover slide")
    parser.add_argument("--language", default="pt", help="Transcription language code")
    parser.add_argument(
        "--engine",
        choices=("auto", "local", "titan"),
        default="auto",
        help="Transcription engine. auto uses Titan on macOS and local ML on Linux/WSL.",
    )
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
        help=(
            "Backend preference. 'mock' is Titan-only (packaging smoke tests); "
            "on the local engine, cpu/cuda select the forced-alignment device."
        ),
    )
    parser.add_argument(
        "--whisper-model",
        default=None,
        choices=("tiny", "base", "small", "medium", "large-v2", "large-v3"),
        help="Override the Whisper model size.",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable stage cache")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".louvorja-cache"),
        help="Local/Titan stage cache directory",
    )
    parser.add_argument(
        "--vocal-separation",
        choices=("htdemucs_ft", "none"),
        default="htdemucs_ft",
        help="Local engine vocal separation stage",
    )
    parser.add_argument(
        "--alignment",
        choices=("mms", "none"),
        default="none",
        help="Local engine forced alignment stage",
    )
    parser.add_argument(
        "--quality-gate",
        choices=("fail", "warn", "off"),
        default="fail",
        help="Reject, warn, or ignore poor generated slide/transcript quality.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return run(args)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def run(args: argparse.Namespace) -> int:
    audio_path = Path(args.audio)
    if not audio_path.exists():
        raise FileNotFoundError(f"audio file not found: {audio_path}")
    if audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
        raise ValueError(f"unsupported audio extension {audio_path.suffix!r}; expected {allowed}")

    force_mock = args.device == "mock"
    backend = args.device if args.device not in ("auto", "mock") else None

    engine = select_engine(args.engine)
    doc = engine.transcribe(
        audio_path,
        AudioToDocumentConfig(
            language=args.language,
            cache=not args.no_cache,
            cache_root=Path(args.cache_dir),
            title=args.title,
            force_mock=force_mock,
            backend=backend,
            whisper_model=args.whisper_model,
            vocal_separation=args.vocal_separation,
            alignment=args.alignment,
        ),
    )

    title = args.title or _document_title(doc) or audio_path.stem
    slides = extract_lyric_slides(doc, lines_per_slide=args.lines_per_slide)
    enforce_quality(
        slides=slides,
        transcript=getattr(doc, "transcript", None),
        mode=args.quality_gate,
    )
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
