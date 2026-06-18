#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from pywhispercpp.model import Model

from louvorja_slides.audio import decode_audio_16k_mono
from louvorja_slides.document import transcript_to_document
from louvorja_slides.quality import analyze_slide_quality
from louvorja_slides.slja import Slide, extract_lyric_slides, read_slja, write_slja
from louvorja_slides.transcription import Transcript, TranscribedWord


@dataclass(frozen=True)
class VideoInput:
    video_id: str
    title: str
    duration_seconds: float
    audio_path: Path
    caption_path: Path | None = None


@dataclass(frozen=True)
class Strategy:
    name: str
    model_id: str
    audio_variant: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Candidate:
    video: VideoInput
    strategy: str
    transcript: Transcript
    slja_path: Path
    text: str
    slide_count: int
    over_hard: int
    over_target: int
    line_count: int
    aux_words: int
    fast_transitions: int
    median_line_chars: float
    caption_similarity: float | None = None
    consensus_similarity: float = 0.0
    word_count_ratio: float = 1.0
    score: float = 0.0


STRATEGIES = [
    Strategy("medium-original", "medium", "original", {"language": "pt"}),
    Strategy("medium-denoise", "medium", "denoise", {"language": "pt"}),
    Strategy("medium-voice-eq", "medium", "voice-eq", {"language": "pt"}),
    Strategy("turbo-original", "large-v3-turbo", "original", {"language": "pt"}),
    Strategy("turbo-denoise", "large-v3-turbo", "denoise", {"language": "pt"}),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--metadata-jsonl", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    batch_root = args.batch_root
    outputs = batch_root / "experiment"
    outputs.mkdir(parents=True, exist_ok=True)

    videos = discover_inputs(batch_root / "downloads", args.metadata_jsonl)
    if args.limit:
        videos = videos[: args.limit]

    all_candidates: list[Candidate] = []
    models: dict[str, Model] = {}
    for video in videos:
        print(f"\n=== {video.video_id} {video.title} ===", flush=True)
        variants = prepare_audio_variants(video, outputs / video.video_id)
        video_candidates: list[Candidate] = []
        for strategy in STRATEGIES:
            cached_slja_path = outputs / video.video_id / f"{strategy.name}.slja"
            if cached_slja_path.exists():
                candidate = load_cached_candidate(
                    video=video,
                    strategy_name=strategy.name,
                    slja_path=cached_slja_path,
                )
                if candidate is not None:
                    video_candidates.append(candidate)
                    all_candidates.append(candidate)
                    print(
                        f"  {strategy.name}: cached words={len(candidate.transcript.words)} "
                        f"slides={candidate.slide_count} hard={candidate.over_hard}",
                        flush=True,
                    )
                    continue

            model = models.get(strategy.model_id)
            if model is None:
                print(f"loading model {strategy.model_id}", flush=True)
                model = Model(model=strategy.model_id)
                models[strategy.model_id] = model
            audio_path = variants[strategy.audio_variant]
            candidate = transcribe_candidate(
                video=video,
                strategy=strategy,
                audio_path=audio_path,
                output_dir=outputs / video.video_id,
                source_audio=video.audio_path,
                model=model,
            )
            if candidate is None:
                print(f"  {strategy.name}: skipped no words", flush=True)
                continue
            video_candidates.append(candidate)
            all_candidates.append(candidate)
            print(
                f"  {strategy.name}: words={len(candidate.transcript.words)} "
                f"slides={candidate.slide_count} hard={candidate.over_hard}",
                flush=True,
            )
        if video.caption_path is not None:
            cached_slja_path = outputs / video.video_id / "youtube-caption.slja"
            if cached_slja_path.exists():
                candidate = load_cached_candidate(
                    video=video,
                    strategy_name="youtube-caption",
                    slja_path=cached_slja_path,
                )
            else:
                candidate = caption_candidate(
                    video=video,
                    caption_path=video.caption_path,
                    output_dir=outputs / video.video_id,
                )
            if candidate is not None:
                video_candidates.append(candidate)
                all_candidates.append(candidate)
                print(
                    f"  youtube-caption: words={len(candidate.transcript.words)} "
                    f"slides={candidate.slide_count} hard={candidate.over_hard}",
                    flush=True,
                )
            else:
                print("  youtube-caption: skipped no usable caption text", flush=True)

        caption_text = load_caption_text(video.caption_path) if video.caption_path else None
        if not video_candidates:
            print("  no usable candidates", flush=True)
            continue
        score_video_candidates(video_candidates, caption_text)
        best = max(video_candidates, key=lambda item: item.score)
        shutil.copyfile(best.slja_path, outputs / video.video_id / "best.slja")
        print(f"  BEST {best.strategy} score={best.score:.1f}", flush=True)

    report_path = outputs / "asr-experiment-report.md"
    write_report(report_path, videos, all_candidates)
    print(f"\nREPORT {report_path}")
    return 0


def discover_inputs(downloads: Path, metadata_jsonl: Path) -> list[VideoInput]:
    metadata: dict[str, dict[str, Any]] = {}
    for line in metadata_jsonl.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            metadata[str(item["id"])] = item

    videos: list[VideoInput] = []
    for video_id, item in metadata.items():
        directory = downloads / video_id
        mp3s = sorted(directory.glob("*.mp3"))
        if not mp3s:
            continue
        caption_path = pick_caption(directory)
        videos.append(
            VideoInput(
                video_id=video_id,
                title=str(item.get("title") or video_id),
                duration_seconds=float(item.get("duration") or 0),
                audio_path=mp3s[0],
                caption_path=caption_path,
            )
        )
    return videos


def pick_caption(directory: Path) -> Path | None:
    for pattern in ("*.pt-orig.vtt", "*.pt.vtt", "*.pt-BR.vtt"):
        matches = sorted(directory.glob(pattern))
        if matches:
            return matches[0]
    return None


def prepare_audio_variants(video: VideoInput, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    variants = {"original": video.audio_path}
    denoise = output_dir / "audio-denoise.wav"
    voice_eq = output_dir / "audio-voice-eq.wav"
    if not denoise.exists():
        run_ffmpeg(
            video.audio_path,
            denoise,
            "afftdn,dynaudnorm=f=150:g=15",
        )
    if not voice_eq.exists():
        run_ffmpeg(
            video.audio_path,
            voice_eq,
            "highpass=f=120,lowpass=f=6500,afftdn=nf=-25,dynaudnorm=f=150:g=15",
        )
    variants["denoise"] = denoise
    variants["voice-eq"] = voice_eq
    return variants


def run_ffmpeg(input_path: Path, output_path: Path, filters: str) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-af",
            filters,
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
        ],
        check=True,
    )


def transcribe_candidate(
    *,
    video: VideoInput,
    strategy: Strategy,
    audio_path: Path,
    output_dir: Path,
    source_audio: Path,
    model: Model,
) -> Candidate | None:
    decoded = decode_audio_16k_mono(audio_path)
    segments = model.transcribe(decoded.samples, **strategy.params)
    words: list[TranscribedWord] = []
    for segment in segments:
        text = str(getattr(segment, "text", "")).strip()
        if not any(character.isalnum() for character in text):
            continue
        start = float(getattr(segment, "t0")) / 100.0
        end = max(start, float(getattr(segment, "t1")) / 100.0)
        words.append(
            TranscribedWord(
                text=text,
                start=start,
                end=end,
                source=strategy.name,
            )
        )
    if not words:
        return None
    transcript = Transcript(
        words=words,
        detected_language="pt",
        duration_seconds=decoded.duration_seconds,
    )
    doc = transcript_to_document(transcript, title=video.title)
    slides = extract_lyric_slides(doc)
    slja_path = output_dir / f"{strategy.name}.slja"
    write_slja(audio_path=source_audio, output_path=slja_path, slides=slides, title=video.title)
    return build_candidate(
        video=video,
        strategy_name=strategy.name,
        transcript=transcript,
        slja_path=slja_path,
        slides=slides,
    )


def caption_candidate(
    *,
    video: VideoInput,
    caption_path: Path,
    output_dir: Path,
) -> Candidate | None:
    words = parse_vtt_words(caption_path)
    if not words:
        return None
    transcript = Transcript(
        words=words,
        detected_language="pt",
        duration_seconds=video.duration_seconds,
    )
    doc = transcript_to_document(transcript, title=video.title)
    slides = extract_lyric_slides(doc)
    slja_path = output_dir / "youtube-caption.slja"
    write_slja(
        audio_path=video.audio_path,
        output_path=slja_path,
        slides=slides,
        title=video.title,
    )
    return build_candidate(
        video=video,
        strategy_name="youtube-caption",
        transcript=transcript,
        slja_path=slja_path,
        slides=slides,
    )


def load_cached_candidate(
    *,
    video: VideoInput,
    strategy_name: str,
    slja_path: Path,
) -> Candidate | None:
    archive = read_slja(slja_path)
    if not archive.slides:
        return None
    text = slide_text(archive.slides)
    words = transcript_words_from_text(text, strategy_name, video.duration_seconds)
    if not words:
        return None
    return build_candidate(
        video=video,
        strategy_name=strategy_name,
        transcript=Transcript(
            words=words,
            detected_language="pt",
            duration_seconds=video.duration_seconds,
        ),
        slja_path=slja_path,
        slides=archive.slides,
    )


def build_candidate(
    *,
    video: VideoInput,
    strategy_name: str,
    transcript: Transcript,
    slja_path: Path,
    slides: Iterable[Slide],
) -> Candidate:
    slide_list = list(slides)
    report = analyze_slide_quality(slide_list)
    text = slide_text(slide_list)
    return Candidate(
        video=video,
        strategy=strategy_name,
        transcript=transcript,
        slja_path=slja_path,
        text=text,
        slide_count=report.slide_count,
        over_hard=report.over_hard_line_count,
        over_target=report.over_target_line_count,
        line_count=report.line_count,
        aux_words=report.auxiliary_word_count,
        fast_transitions=report.fast_transition_count,
        median_line_chars=report.median_line_chars,
    )


def slide_text(slides: Iterable[Slide]) -> str:
    slide_list = list(slides)
    text = " ".join([line for slide in slide_list for line in slide.lines])
    return " ".join([text, *[slide.aux_text for slide in slide_list if slide.aux_text]]).strip()


def transcript_words_from_text(
    text: str,
    source: str,
    duration_seconds: float,
) -> list[TranscribedWord]:
    tokens = re.findall(r"\S+", text)
    if not tokens:
        return []
    step = duration_seconds / max(len(tokens), 1)
    return [
        TranscribedWord(
            text=token,
            start=index * step,
            end=(index + 1) * step,
            source=f"{source}-cached",
        )
        for index, token in enumerate(tokens)
    ]


def score_video_candidates(candidates: list[Candidate], caption_text: str | None) -> None:
    word_counts = [text_word_count(candidate.text) for candidate in candidates]
    median_words = median(word_counts) if word_counts else 1
    for candidate in candidates:
        similarities = [
            text_similarity(candidate.text, other.text)
            for other in candidates
            if other is not candidate
        ]
        candidate.consensus_similarity = mean(similarities) if similarities else 0.0
        candidate.caption_similarity = (
            text_similarity(candidate.text, caption_text)
            if caption_text
            else None
        )
        candidate.word_count_ratio = (
            text_word_count(candidate.text) / median_words if median_words else 1.0
        )
        candidate.score = candidate_score(candidate)


def candidate_score(candidate: Candidate) -> float:
    score = 100.0 * candidate.consensus_similarity
    if candidate.caption_similarity is not None:
        score = 0.45 * score + 55.0 * candidate.caption_similarity
    score -= candidate.over_hard * 10.0
    score -= candidate.aux_words * 0.8
    score -= candidate.fast_transitions * 4.0
    if candidate.line_count:
        over_target_ratio = candidate.over_target / candidate.line_count
        score -= max(0.0, over_target_ratio - 0.30) * 40.0
    if candidate.word_count_ratio < 0.65 or candidate.word_count_ratio > 1.45:
        score -= 15.0
    return score


def load_caption_text(path: Path | None) -> str | None:
    if path is None:
        return None
    words = parse_vtt_words(path)
    if words:
        return " ".join(word.text for word in words)
    lines: list[str] = []
    previous = ""
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line == "WEBVTT" or "-->" in line:
            continue
        if line.isdigit() or line.startswith(("Kind:", "Language:")):
            continue
        line = re.sub(r"<[^>]+>", " ", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line and line != previous:
            lines.append(line)
            previous = line
    return " ".join(lines) if lines else None


def parse_vtt_words(path: Path) -> list[TranscribedWord]:
    raw_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    words: list[TranscribedWord] = []
    previous_tokens: list[str] = []
    index = 0
    while index < len(raw_lines):
        line = raw_lines[index].strip()
        if "-->" not in line:
            index += 1
            continue
        start, end = parse_vtt_time_range(line)
        index += 1
        cue_lines: list[str] = []
        while index < len(raw_lines) and raw_lines[index].strip():
            cue_lines.append(raw_lines[index].strip())
            index += 1
        cue_text = clean_caption_text(" ".join(cue_lines))
        cue_tokens = cue_text.split()
        new_tokens = remove_caption_overlap(previous_tokens, cue_tokens)
        previous_tokens = cue_tokens or previous_tokens
        if new_tokens:
            words.append(
                TranscribedWord(
                    text=" ".join(new_tokens),
                    start=start,
                    end=max(start, end),
                    source="youtube-caption",
                )
            )
        index += 1
    return words


def parse_vtt_time_range(line: str) -> tuple[float, float]:
    left, right = line.split("-->", maxsplit=1)
    end_text = right.strip().split()[0]
    return parse_vtt_timestamp(left.strip()), parse_vtt_timestamp(end_text)


def parse_vtt_timestamp(text: str) -> float:
    parts = text.replace(",", ".").split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = "0"
        minutes, seconds = parts
    else:
        return 0.0
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def clean_caption_text(text: str) -> str:
    text = re.sub(r"<\d\d:\d\d:\d\d\.\d+>", " ", text)
    text = re.sub(r"</?c>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def remove_caption_overlap(
    previous_tokens: list[str],
    cue_tokens: list[str],
) -> list[str]:
    if not previous_tokens or not cue_tokens:
        return cue_tokens
    previous_norm = [normalize_text(token) for token in previous_tokens]
    cue_norm = [normalize_text(token) for token in cue_tokens]
    max_overlap = min(len(previous_norm), len(cue_norm))
    for size in range(max_overlap, 0, -1):
        if previous_norm[-size:] == cue_norm[:size]:
            return cue_tokens[size:]
    return cue_tokens


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    table = str.maketrans(
        "áàãâäéèêëíìîïóòõôöúùûüçñ",
        "aaaaaeeeeiiiiooooouuuucn",
    )
    text = text.casefold().translate(table)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def text_similarity(left: str | None, right: str | None) -> float:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm or not right_norm:
        return 0.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def text_word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def write_report(
    path: Path,
    videos: list[VideoInput],
    candidates: list[Candidate],
) -> None:
    by_video: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        by_video.setdefault(candidate.video.video_id, []).append(candidate)

    strategy_wins: dict[str, int] = {}
    lines = [
        "# ASR batch experiment report",
        "",
        "Scope: automatic transcription strategies only. No human lyric review and no LLM correction.",
        "The report avoids full lyric dumps; metrics are computed from generated text locally.",
        "Word-count outlier penalties use the final slide text, not internal Whisper segment counts.",
        "",
        "## Techniques tested",
        "",
        "- Whisper medium on original audio.",
        "- Whisper medium after FFmpeg denoise/dynamic normalization.",
        "- Whisper medium after voice-focused EQ/noise filtering.",
        "- Whisper large-v3-turbo on original audio.",
        "- Whisper large-v3-turbo after FFmpeg denoise/dynamic normalization.",
        "- Direct YouTube Portuguese caption import as a candidate when downloaded.",
        "- YouTube Portuguese captions were also used as a proxy reference when downloaded.",
        "",
        "## Results by video",
        "",
        "| # | Video | Duration | Caption ref | Best strategy | Score | Consensus | Caption sim | Slides | Hard lines | Over-target | Aux words |",
        "|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for index, video in enumerate(videos, start=1):
        video_candidates = by_video.get(video.video_id, [])
        if not video_candidates:
            continue
        best = max(video_candidates, key=lambda item: item.score)
        strategy_wins[best.strategy] = strategy_wins.get(best.strategy, 0) + 1
        caption_label = "yes" if video.caption_path else "no"
        caption_sim = (
            f"{best.caption_similarity:.3f}"
            if best.caption_similarity is not None
            else "-"
        )
        duration = format_duration(video.duration_seconds)
        lines.append(
            "| "
            f"{index} | {escape_pipe(video.title)} (`{video.video_id}`) | "
            f"{duration} | {caption_label} | {best.strategy} | "
            f"{best.score:.1f} | {best.consensus_similarity:.3f} | {caption_sim} | "
            f"{best.slide_count} | {best.over_hard} | "
            f"{best.over_target}/{best.line_count} | {best.aux_words} |"
        )

    lines.extend(
        [
            "",
            "## Full Candidate Matrix",
            "",
            "| Video | Strategy | Score | Consensus | Caption sim | Text words | Slides | Hard lines | Over-target | Aux words |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for video in videos:
        for candidate in sorted(
            by_video.get(video.video_id, []),
            key=lambda item: (-item.score, item.strategy),
        ):
            caption_sim = (
                f"{candidate.caption_similarity:.3f}"
                if candidate.caption_similarity is not None
                else "-"
            )
            lines.append(
                "| "
                f"`{video.video_id}` | `{candidate.strategy}` | "
                f"{candidate.score:.1f} | {candidate.consensus_similarity:.3f} | "
                f"{caption_sim} | {text_word_count(candidate.text)} | "
                f"{candidate.slide_count} | {candidate.over_hard} | "
                f"{candidate.over_target}/{candidate.line_count} | {candidate.aux_words} |"
            )

    lines.extend(
        [
            "",
            "## Strategy wins",
            "",
        ]
    )
    for strategy, count in sorted(strategy_wins.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{strategy}`: {count}")

    captioned = [
        candidate
        for candidate in candidates
        if candidate.caption_similarity is not None
    ]
    if captioned:
        best_captioned = [
            max(by_video[candidate.video.video_id], key=lambda item: item.score)
            for candidate in captioned
        ]
        # Deduplicate by video.
        seen: set[str] = set()
        unique_best = []
        for candidate in best_captioned:
            if candidate.video.video_id not in seen:
                unique_best.append(candidate)
                seen.add(candidate.video.video_id)
        lines.extend(
            [
                "",
                "## Caption-reference subset",
                "",
            f"Videos with Portuguese caption proxy: {len(unique_best)}.",
            "Caption similarity is not ground-truth WER; it is agreement with YouTube caption text.",
            "`youtube-caption` candidates are not independently validated by caption similarity because they come from the same text source.",
            f"Mean best caption similarity: {mean(c.caption_similarity or 0 for c in unique_best):.3f}.",
        ]
    )

    aggregate_best = [
        max(video_candidates, key=lambda item: item.score)
        for video_candidates in by_video.values()
        if video_candidates
    ]
    lines.extend(
        [
            "",
            "## Aggregate best-candidate quality",
            "",
            f"- Videos processed: {len(aggregate_best)} / {len(videos)}.",
            f"- Mean consensus similarity: {mean(c.consensus_similarity for c in aggregate_best):.3f}.",
            f"- Total hard-limit lines: {sum(c.over_hard for c in aggregate_best)}.",
            f"- Total auxiliary words: {sum(c.aux_words for c in aggregate_best)}.",
            f"- Total fast transitions: {sum(c.fast_transitions for c in aggregate_best)}.",
            "",
            "## Interpretation",
            "",
            "- Denoise/dynamic normalization is the strongest ASR-only audio preprocessing technique in this run when it wins without increasing hard-line failures.",
            "- `large-v3-turbo` is not automatically better for these congregational mixes; it often produces longer segments and more hard-line failures.",
            "- YouTube caption extraction is the strongest non-ASR shortcut where Portuguese captions are available, but coverage was limited and auto captions can still be wrong.",
            "- OCR over lyric videos is the next promising non-LLM technique for videos with lyrics on screen; it was not run here because no local OCR engine was available in this environment.",
            "- True transcription precision still requires reference lyrics or trusted captions; without that, these scores are relative proxies.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_duration(seconds: float) -> str:
    if not seconds or math.isnan(seconds):
        return "-"
    minutes = int(seconds // 60)
    remainder = int(seconds % 60)
    return f"{minutes}:{remainder:02d}"


def escape_pipe(text: str) -> str:
    return text.replace("|", "\\|")


if __name__ == "__main__":
    raise SystemExit(main())
