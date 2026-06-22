#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from louvorja_slides.cache import audio_sha256, cache_key, cache_path, load_json, save_json
from louvorja_slides.consensus import build_phase1_consensus, format_consensus_report
from louvorja_slides.engines import AudioToDocumentConfig, select_engine
from louvorja_slides.lyrics import (
    LYRICS_ALIGNMENT_REVISION,
    LyricsAlignmentResult,
    align_lyrics_to_transcript,
    parse_lyrics,
    transcript_to_lyrics_document,
)
from louvorja_slides.quality import enforce_quality
from louvorja_slides.slja import extract_lyric_slides, read_slja, write_slja
from louvorja_slides.transcription import Transcript

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".mp4"}
SUPPORTED_INPUT_EXTENSIONS = SUPPORTED_AUDIO_EXTENSIONS | {".slja"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a LouvorJA .slja archive from local MP3/MP4 audio, "
            "or validate an existing .slja archive."
        )
    )
    parser.add_argument("audio", type=Path, help="Input .mp3, .mp4, or .slja file")
    parser.add_argument("--output", type=Path, default=None, help="Output .slja path")
    parser.add_argument("--title", default=None, help="Song title for the cover slide")
    parser.add_argument("--language", default="pt", help="Transcription language code")
    parser.add_argument(
        "--engine",
        choices=("auto", "local"),
        default="auto",
        help="Transcription engine. auto uses the local ML pipeline on every OS.",
    )
    parser.add_argument(
        "--lines-per-slide",
        type=int,
        default=2,
        help="Number of lyric lines per LouvorJA slide",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "mps", "cuda", "cpu"),
        default="auto",
        help="Backend preference for local forced alignment.",
    )
    parser.add_argument(
        "--whisper-model",
        default=None,
        choices=("tiny", "base", "small", "medium", "large-v2", "large-v3", "large-v3-turbo"),
        help="Override the Whisper model size.",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable stage cache")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".louvorja-cache"),
        help="Local stage cache directory",
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
    parser.add_argument(
        "--lyrics-file",
        type=Path,
        default=None,
        help="Plaintext expected lyrics to use as the displayed words.",
    )
    parser.add_argument(
        "--lyrics-text",
        default=None,
        help="Inline expected lyrics text to use as the displayed words.",
    )
    parser.add_argument(
        "--lyrics-mode",
        choices=("asr", "lyrics-first"),
        default=None,
        help="Use ASR text or expected lyrics as the generated slide text.",
    )
    parser.add_argument(
        "--transcription-strategy",
        choices=("asr", "consensus"),
        default="asr",
        help="Use one ASR pass or the automatic phrase-level consensus engine.",
    )
    parser.add_argument(
        "--consensus-phase",
        choices=("1", "2", "3", "4", "full"),
        default="1",
        help="Consensus implementation phase to run. Only phase 1 is currently implemented.",
    )
    parser.add_argument(
        "--youtube-caption-file",
        type=Path,
        default=None,
        help="Optional Portuguese YouTube VTT caption candidate for consensus.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Consensus report path. Defaults to <output>.consensus-report.md.",
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
    if audio_path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_INPUT_EXTENSIONS))
        raise ValueError(f"unsupported audio extension {audio_path.suffix!r}; expected {allowed}")
    if audio_path.suffix.lower() == ".slja":
        if _has_lyrics_options(args):
            raise ValueError("lyrics-first options are only supported for audio input")
        if _has_audio_only_options(args):
            raise ValueError("generation options are only supported for audio input")
        archive = read_slja(audio_path)
        slide_report, _transcript_report = enforce_quality(
            slides=archive.slides,
            mode=args.quality_gate,
        )
        print(
            "SLJA quality: "
            f"{slide_report.slide_count} lyric slides, "
            f"{slide_report.empty_slide_count} empty, "
            f"{slide_report.over_hard_line_count} over hard line limit, "
            f"{slide_report.fast_transition_count}/{slide_report.transition_count} fast transitions"
        )
        return 0

    if args.transcription_strategy == "consensus" and _has_lyrics_options(args):
        raise ValueError("consensus strategy cannot use lyrics-first/manual lyrics options")
    if args.transcription_strategy != "consensus" and (
        args.youtube_caption_file is not None or args.report_path is not None
    ):
        raise ValueError("--youtube-caption-file and --report-path require consensus strategy")
    if args.transcription_strategy == "consensus" and args.consensus_phase != "1":
        raise ValueError("only consensus phase 1 is implemented")
    lyrics_text = _read_lyrics_text(args)
    lyrics_mode = _resolve_lyrics_mode(args, lyrics_text)
    force_mock = False
    backend = args.device if args.device != "auto" else None

    engine = select_engine(args.engine)
    engine_config = AudioToDocumentConfig(
        language=args.language,
        cache=not args.no_cache,
        cache_root=Path(args.cache_dir),
        title=args.title,
        force_mock=force_mock,
        backend=backend,
        whisper_model=args.whisper_model,
        vocal_separation=args.vocal_separation,
        alignment=args.alignment,
    )
    consensus_result = None
    if args.transcription_strategy == "consensus":
        consensus_result = build_phase1_consensus(
            audio_path=audio_path,
            engine=engine,
            base_config=engine_config,
            title=args.title or audio_path.stem,
            youtube_caption_path=args.youtube_caption_file,
        )
        doc = consensus_result.document
    else:
        doc = engine.transcribe(audio_path, engine_config)

    title = args.title or _document_title(doc) or audio_path.stem
    lyrics_report = None
    if lyrics_mode == "lyrics-first":
        doc, lyrics_report = _apply_lyrics_first(
            audio_path=audio_path,
            doc=doc,
            lyrics_text=lyrics_text,
            language=args.language,
            cache=not args.no_cache,
            cache_root=Path(args.cache_dir),
            title=title,
        )

    slides = extract_lyric_slides(
        doc,
        lines_per_slide=args.lines_per_slide,
        allow_auxiliary=args.transcription_strategy != "consensus",
        hard_max_chars_per_line=34,
    )
    slide_report, _transcript_report = enforce_quality(
        slides=slides,
        transcript=getattr(doc, "transcript", None),
        lyrics_alignment=lyrics_report,
        mode=args.quality_gate,
    )
    output_path = Path(args.output) if args.output is not None else audio_path.with_suffix(".slja")

    write_slja(audio_path=audio_path, output_path=output_path, slides=slides, title=title)
    print(f"Wrote {output_path}")
    if consensus_result is not None:
        report_path = (
            Path(args.report_path)
            if args.report_path is not None
            else output_path.with_suffix(".consensus-report.md")
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            format_consensus_report(
                consensus_result,
                slides=slides,
                slide_report=slide_report,
            ),
            encoding="utf-8",
        )
        print(f"Wrote report {report_path}")
    return 0


def _document_title(doc: Any) -> str | None:
    metadata = getattr(doc, "metadata", None)
    title = getattr(metadata, "title", None)
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


def _has_lyrics_options(args: argparse.Namespace) -> bool:
    return (
        args.lyrics_file is not None
        or args.lyrics_text is not None
        or args.lyrics_mode is not None
    )


def _has_audio_only_options(args: argparse.Namespace) -> bool:
    return (
        _has_lyrics_options(args)
        or args.transcription_strategy != "asr"
        or args.consensus_phase != "1"
        or args.youtube_caption_file is not None
        or args.report_path is not None
    )


def _read_lyrics_text(args: argparse.Namespace) -> str | None:
    if args.lyrics_file is not None and args.lyrics_text is not None:
        raise ValueError("use only one of --lyrics-file or --lyrics-text")
    if args.lyrics_file is not None:
        return Path(args.lyrics_file).read_text(encoding="utf-8-sig")
    if args.lyrics_text is not None:
        return str(args.lyrics_text)
    return None


def _resolve_lyrics_mode(args: argparse.Namespace, lyrics_text: str | None) -> str:
    mode = args.lyrics_mode or ("lyrics-first" if lyrics_text is not None else "asr")
    if mode == "lyrics-first" and lyrics_text is None:
        raise ValueError("--lyrics-mode lyrics-first requires --lyrics-file or --lyrics-text")
    if mode == "asr" and lyrics_text is not None:
        raise ValueError("lyrics text was provided but --lyrics-mode asr disables it")
    return mode


def _apply_lyrics_first(
    *,
    audio_path: Path,
    doc: Any,
    lyrics_text: str | None,
    language: str,
    cache: bool,
    cache_root: Path,
    title: str,
) -> tuple[Any, Any]:
    if lyrics_text is None:
        raise ValueError("lyrics-first mode requires lyrics text")

    source_transcript = getattr(doc, "transcript", None)
    if not isinstance(source_transcript, Transcript):
        raise ValueError("lyrics-first mode requires an engine transcript")

    parsed = parse_lyrics(lyrics_text)
    result = _load_or_create_lyrics_alignment(
        audio_path=audio_path,
        transcript=source_transcript,
        lyrics=parsed,
        lyrics_text=lyrics_text,
        language=language,
        cache=cache,
        cache_root=cache_root,
    )
    return (
        transcript_to_lyrics_document(result.transcript, parsed, title=title),
        result.report,
    )


def _load_or_create_lyrics_alignment(
    *,
    audio_path: Path,
    transcript: Transcript,
    lyrics: Any,
    lyrics_text: str,
    language: str,
    cache: bool,
    cache_root: Path,
) -> LyricsAlignmentResult:
    cache_file: Path | None = None
    if cache:
        audio_id = audio_sha256(audio_path)
        variant = _lyrics_cache_variant(
            language=language,
            lyrics_text=lyrics_text,
            transcript=transcript,
        )
        cache_file = cache_path(cache_root, audio_id, "lyrics-aligned", variant)
        cached = _load_cached_lyrics_alignment(cache_file)
        if cached is not None:
            return cached

    result = align_lyrics_to_transcript(transcript, lyrics)
    if cache and cache_file is not None:
        save_json(cache_file, result.to_dict())
    return result


def _load_cached_lyrics_alignment(path: Path) -> LyricsAlignmentResult | None:
    try:
        cached = load_json(path)
        return LyricsAlignmentResult.from_dict(cached) if cached is not None else None
    except (KeyError, TypeError, ValueError):
        path.unlink(missing_ok=True)
        return None


def _lyrics_cache_variant(
    *,
    language: str,
    lyrics_text: str,
    transcript: Transcript,
) -> str:
    return cache_key(
        {
            "schema": 1,
            "stage": "lyrics-aligned",
            "language": language,
            "lyrics_alignment_revision": LYRICS_ALIGNMENT_REVISION,
            "lyrics_hash": cache_key({"lyrics_text": lyrics_text}),
            "source_transcript_hash": cache_key(transcript.to_dict()),
        }
    )


if __name__ == "__main__":
    raise SystemExit(main())
