from __future__ import annotations

import math
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

DEFAULT_VERSION = "25.0.17424.39578"
DEFAULT_LETTER_SIZE = 20
DEFAULT_AUX_LETTER_SIZE = 10
DEFAULT_LETTER_COLOR = "#FFFFFF"
DEFAULT_AUX_LETTER_COLOR = "#EFB400"
DEFAULT_BACKGROUND_COLOR = "#000000"


@dataclass(frozen=True)
class Slide:
    lines: tuple[str, ...]
    start_seconds: float


def format_timestamp(seconds: float) -> str:
    total_seconds = max(0, math.floor(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def extract_lyric_slides(doc: Any, lines_per_slide: int = 2) -> list[Slide]:
    if lines_per_slide < 1:
        raise ValueError("lines_per_slide must be >= 1")

    lyric_lines: list[tuple[str, float]] = []
    for section in getattr(doc, "sections", []):
        for line in getattr(section, "lines", []):
            if getattr(line, "line_type", None) != "lyric":
                continue
            text = _clean_lja_value(getattr(line, "text", ""))
            if not text:
                continue
            lyric_lines.append((text, _line_start_seconds(line, section)))

    slides: list[Slide] = []
    for i in range(0, len(lyric_lines), lines_per_slide):
        group = lyric_lines[i : i + lines_per_slide]
        slides.append(Slide(lines=tuple(text for text, _start in group), start_seconds=group[0][1]))
    return slides


def render_lja(
    *,
    slides: Iterable[Slide],
    title: str,
    audio_name: str,
    version: str = DEFAULT_VERSION,
    title_aux: str | None = None,
) -> bytes:
    slide_list = list(slides)
    audio_member = _audio_member_name(audio_name)

    lines: list[str] = [
        "[Geral]",
        f"slides={len(slide_list) + 1}",
        f"versao={version}",
        f"audio={audio_member}",
        "",
    ]

    _append_slide(
        lines,
        index=1,
        slide_type="CAPA",
        text=_clean_lja_value(title),
        aux_text=_clean_lja_value(title_aux or ""),
        timestamp="00:00:00",
    )

    for index, slide in enumerate(slide_list, start=2):
        _append_slide(
            lines,
            index=index,
            slide_type="LETRA",
            text="|".join(_clean_lja_value(line) for line in slide.lines),
            aux_text="",
            timestamp=format_timestamp(slide.start_seconds),
        )

    text = "\r\n".join(lines)
    if not text.endswith("\r\n"):
        text += "\r\n"
    return text.encode("cp1252", errors="replace")


def write_slja(
    *,
    audio_path: Path,
    output_path: Path,
    slides: Iterable[Slide],
    title: str,
    version: str = DEFAULT_VERSION,
    title_aux: str | None = None,
) -> None:
    audio_path = Path(audio_path)
    output_path = Path(output_path)
    audio_name = _safe_archive_filename(audio_path.name)
    lja_data = render_lja(
        slides=slides,
        title=title,
        audio_name=audio_name,
        version=version,
        title_aux=title_aux,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("slides.lja", lja_data)
        archive.write(audio_path, _audio_member_name(audio_name))


def _append_slide(
    lines: list[str],
    *,
    index: int,
    slide_type: str,
    text: str,
    aux_text: str,
    timestamp: str,
) -> None:
    lines.extend(
        [
            f"[Slide:{index}]",
            f"tipo={slide_type}",
            f"letra={text}",
            "fundo_letra=1",
            f"tamanho_letra={DEFAULT_LETTER_SIZE}",
            f"cor_letra={DEFAULT_LETTER_COLOR}",
            f"cor_fundo={DEFAULT_BACKGROUND_COLOR}",
        ]
    )
    if aux_text:
        lines.append(f"letra_aux={aux_text}")
    lines.extend(
        [
            f"tamanho_letra_aux={DEFAULT_AUX_LETTER_SIZE}",
            f"cor_letra_aux={DEFAULT_AUX_LETTER_COLOR}",
            f"tempo={timestamp}",
            "",
        ]
    )


def _line_start_seconds(line: Any, section: Any) -> float:
    words = list(getattr(line, "word_alignments", []) or [])
    if words:
        return float(getattr(words[0].timestamp, "start", 0.0))

    timestamp = getattr(section, "timestamp", None)
    if timestamp is not None:
        return float(getattr(timestamp, "start", 0.0))

    return 0.0


def _clean_lja_value(value: str) -> str:
    return " ".join(str(value).replace("|", " ").split())


def _safe_archive_filename(filename: str) -> str:
    cleaned = filename.replace("/", "_").replace("\\", "_").strip()
    return cleaned or "audio.mp3"


def _audio_member_name(audio_name: str) -> str:
    return f"audio\\{_safe_archive_filename(audio_name)}"
