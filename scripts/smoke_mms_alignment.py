#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from louvorja_slides.alignment import MmsForcedAligner
from louvorja_slides.audio import decode_audio_16k_mono
from louvorja_slides.transcription import Transcript, TranscribedWord


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test MMS alignment on a short audio file"
    )
    parser.add_argument("audio", type=Path)
    parser.add_argument("--words", required=True, help="Whitespace-separated transcript text")
    parser.add_argument("--language", default="pt")
    args = parser.parse_args()

    decoded = decode_audio_16k_mono(args.audio)
    tokens = args.words.split()
    words = [
        TranscribedWord(
            text=token,
            start=index * 0.5,
            end=index * 0.5 + 0.2,
            source="manual",
        )
        for index, token in enumerate(tokens)
    ]
    transcript = Transcript(
        words=words,
        detected_language=args.language,
        duration_seconds=decoded.duration_seconds,
    )

    aligned = MmsForcedAligner().align_transcript(
        transcript,
        samples=decoded.samples,
        language=args.language,
    )

    print(f"words={len(aligned.words)} phonemes={len(aligned.phonemes or [])}")
    for word in aligned.words[:20]:
        print(f"{word.start:.2f}-{word.end:.2f} {word.text} {word.source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
