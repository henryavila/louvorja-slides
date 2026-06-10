#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from louvorja_slides.document import transcript_to_document
from louvorja_slides.local_pipeline import LocalPipelineConfig, transcribe_audio_local
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
        "--lines-per-slide",
        type=int,
        default=2,
        help="Number of lyric lines per LouvorJA slide",
    )
    parser.add_argument(
        "--whisper-model",
        default="large-v3",
        choices=("medium", "large-v2", "large-v3"),
        help="Local Whisper model. The default prioritizes quality over speed.",
    )
    parser.add_argument(
        "--vocal-separation",
        default="htdemucs_ft",
        choices=("htdemucs_ft", "none"),
        help="Vocal separation stage. Use 'none' only as an explicit quality bypass.",
    )
    parser.add_argument(
        "--alignment",
        default="mms",
        choices=("mms", "none"),
        help="Forced alignment stage. Use 'none' only as an explicit quality bypass.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".louvorja-cache"),
        help="Directory for local transcription stage cache",
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

    title = args.title or audio_path.stem
    config = LocalPipelineConfig(
        language=args.language,
        cache_root=Path(args.cache_dir),
        whisper_model=args.whisper_model,
        vocal_separation=args.vocal_separation,
        alignment=args.alignment,
    )
    transcript = transcribe_audio_local(audio_path, config=config)
    doc = transcript_to_document(transcript, title=title)
    slides = extract_lyric_slides(doc, lines_per_slide=args.lines_per_slide)
    output_path = Path(args.output) if args.output is not None else audio_path.with_suffix(".slja")

    write_slja(audio_path=audio_path, output_path=output_path, slides=slides, title=title)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
