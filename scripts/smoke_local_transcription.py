#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from louvorja_slides.local_pipeline import LocalPipelineConfig, transcribe_audio_local


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--language", default="pt")
    parser.add_argument("--whisper-model", default="large-v3")
    parser.add_argument(
        "--vocal-separation",
        default="htdemucs_ft",
        choices=("htdemucs_ft", "none"),
    )
    parser.add_argument("--alignment", default="mms", choices=("mms", "none"))
    args = parser.parse_args()

    transcript = transcribe_audio_local(
        args.audio,
        config=LocalPipelineConfig(
            language=args.language,
            whisper_model=args.whisper_model,
            vocal_separation=args.vocal_separation,
            alignment=args.alignment,
        ),
    )
    for word in transcript.words[:80]:
        print(f"{word.start:8.2f} {word.end:8.2f} {word.text}")
    print(f"words={len(transcript.words)} duration={transcript.duration_seconds:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
