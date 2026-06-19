from __future__ import annotations

import math
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from louvorja_slides.layout import LayoutConfig, LyricWord, plan_lyric_slides

DEFAULT_VERSION = "25.0.17424.39578"
DEFAULT_LETTER_SIZE = 20
DEFAULT_AUX_LETTER_SIZE = 10
DEFAULT_LETTER_COLOR = "#FFFFFF"
DEFAULT_AUX_LETTER_COLOR = "#EFB400"
DEFAULT_BACKGROUND_COLOR = "#000000"
DEFAULT_IMAGE_POSITION = 5
DEFAULT_COVER_IMAGE_MEMBER = "imagens\\Capa.jpg"
DEFAULT_LYRIC_IMAGE_MEMBER = "imagens\\slides.jpg"
DEFAULT_IMAGE_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "imagens"


@dataclass(frozen=True)
class Slide:
    lines: tuple[str, ...]
    start_seconds: float
    aux_text: str = ""


@dataclass(frozen=True)
class SljaArchive:
    title: str
    audio_member: str
    slides: tuple[Slide, ...]


def format_timestamp(seconds: float) -> str:
    total_seconds = max(0, math.floor(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def read_slja(path: Path, *, tick_rate: float = 192000.0) -> SljaArchive:
    """Read lyric slides from an existing LouvorJA archive."""
    with zipfile.ZipFile(path) as archive:
        text = archive.read("slides.lja").decode("cp1252", errors="replace")

    sections = _parse_lja_sections(text)
    geral = next((section for section in sections if section["name"] == "Geral"), {})
    title = ""
    slides: list[Slide] = []
    for section in sections:
        name = section["name"]
        if not name.startswith("Slide:"):
            continue
        if section.get("tipo") == "CAPA":
            title = section.get("letra", "")
            continue
        if section.get("tipo") != "LETRA":
            continue
        raw_text = section.get("letra", "")
        lines = tuple(part.strip() for part in raw_text.split("|") if part.strip())
        slides.append(
            Slide(
                lines=lines,
                start_seconds=_parse_lja_timestamp(section.get("tempo", "0"), tick_rate),
                aux_text=section.get("letra_aux", "").strip(),
            )
        )

    audio_member = geral.get("url_musica") or geral.get("audio") or ""
    return SljaArchive(title=title, audio_member=audio_member, slides=tuple(slides))


def extract_lyric_slides(
    doc: Any,
    lines_per_slide: int = 2,
    *,
    allow_auxiliary: bool = True,
    hard_max_chars_per_line: int = LayoutConfig().hard_max_chars_per_line,
) -> list[Slide]:
    if lines_per_slide < 1:
        raise ValueError("lines_per_slide must be >= 1")
    if lines_per_slide > 2:
        raise ValueError("lines_per_slide must be <= 2")
    if hard_max_chars_per_line < 1:
        raise ValueError("hard_max_chars_per_line must be >= 1")

    lyric_words: list[LyricWord] = []
    for section_index, section in enumerate(getattr(doc, "sections", [])):
        for line in getattr(section, "lines", []):
            if getattr(line, "line_type", None) != "lyric":
                continue
            text = _clean_lja_value(getattr(line, "text", ""))
            if not text:
                continue
            raw_line_index = getattr(line, "source_line_index", None)
            line_index = int(raw_line_index) if raw_line_index is not None else None
            raw_section_index = getattr(line, "source_section_index", None)
            source_section_index = (
                int(raw_section_index) if raw_section_index is not None else None
            )
            lyric_words.extend(
                _line_words(
                    line,
                    section,
                    text,
                    line_index=line_index,
                    section_index=source_section_index,
                )
            )

    if not lyric_words:
        return []

    plans = plan_lyric_slides(
        lyric_words,
        config=LayoutConfig(
            max_lines_per_slide=lines_per_slide,
            allow_auxiliary=allow_auxiliary,
            hard_max_chars_per_line=hard_max_chars_per_line,
        ),
    )
    return [
        Slide(lines=plan.lines, start_seconds=plan.start_seconds, aux_text=plan.aux_text)
        for plan in plans
    ]


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
        f"url_musica={audio_member}",
        "audio=1",
        "",
    ]

    _append_slide(
        lines,
        index=1,
        slide_type="CAPA",
        text=_clean_lja_value(title),
        aux_text=_clean_lja_value(title_aux or ""),
        image_member=DEFAULT_COVER_IMAGE_MEMBER,
        timestamp="00:00:00",
    )

    for index, slide in enumerate(slide_list, start=2):
        _append_slide(
            lines,
            index=index,
            slide_type="LETRA",
            text="|".join(_clean_lja_value(line) for line in slide.lines),
            aux_text=_clean_lja_value(slide.aux_text),
            image_member=DEFAULT_LYRIC_IMAGE_MEMBER,
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
    image_asset_dir: Path = DEFAULT_IMAGE_ASSET_DIR,
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
        _write_default_image(archive, image_asset_dir, "Capa.jpg", DEFAULT_COVER_IMAGE_MEMBER)
        _write_default_image(archive, image_asset_dir, "slides.jpg", DEFAULT_LYRIC_IMAGE_MEMBER)


def _append_slide(
    lines: list[str],
    *,
    index: int,
    slide_type: str,
    text: str,
    aux_text: str,
    image_member: str,
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
            f"imagem={image_member}",
            f"imagem_posicao={DEFAULT_IMAGE_POSITION}",
            f"tempo={timestamp}",
            "",
        ]
    )


def _write_default_image(
    archive: zipfile.ZipFile,
    image_asset_dir: Path,
    filename: str,
    member_name: str,
) -> None:
    image_path = Path(image_asset_dir) / filename
    archive.write(image_path, member_name)


def _line_start_seconds(line: Any, section: Any) -> float:
    words = list(getattr(line, "word_alignments", []) or [])
    if words:
        return float(getattr(words[0].timestamp, "start", 0.0))

    timestamp = getattr(section, "timestamp", None)
    if timestamp is not None:
        return float(getattr(timestamp, "start", 0.0))

    return 0.0


def _line_words(
    line: Any,
    section: Any,
    text: str,
    *,
    line_index: int | None = None,
    section_index: int | None = None,
) -> list[LyricWord]:
    aligned = list(getattr(line, "word_alignments", []) or [])
    text_parts = text.split()
    if aligned and len(aligned) >= len(text_parts):
        words: list[LyricWord] = []
        for word in aligned:
            word_text = _clean_lja_value(getattr(word, "text", ""))
            if not word_text:
                continue
            words.append(
                LyricWord(
                    text=word_text,
                    start=float(getattr(word.timestamp, "start", 0.0)),
                    end=float(
                        getattr(
                            word.timestamp,
                            "end",
                            getattr(word.timestamp, "start", 0.0),
                        )
                    ),
                    line_index=line_index,
                    section_index=section_index,
                )
            )
        return words

    start = _line_start_seconds(line, section)
    return [
        LyricWord(
            text=part,
            start=start + idx * 0.5,
            end=start + idx * 0.5 + 0.4,
            line_index=line_index,
            section_index=section_index,
        )
        for idx, part in enumerate(text_parts)
    ]


def _clean_lja_value(value: str) -> str:
    return " ".join(str(value).replace("|", " ").split())


def _parse_lja_sections(text: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip("\ufeff").strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = {"name": line[1:-1]}
            sections.append(current)
            continue
        if current is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        current[key.strip()] = value.strip()
    return sections


def _parse_lja_timestamp(value: str, tick_rate: float) -> float:
    raw = value.strip()
    if ":" in raw:
        parts = [int(part) for part in raw.split(":")]
        if len(parts) != 3:
            raise ValueError(f"invalid LouvorJA timestamp: {value!r}")
        return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    if not raw:
        return 0.0
    numeric = int(raw)
    if numeric > 10_000:
        return numeric / tick_rate
    return float(numeric)


def _safe_archive_filename(filename: str) -> str:
    raw = filename.replace("/", "_").replace("\\", "_").strip()
    if not raw:
        return "audio.mp3"

    path = Path(raw)
    suffix = path.suffix if path.suffix else ".mp3"
    stem = path.stem if path.stem else "audio"
    ascii_stem = (
        unicodedata.normalize("NFKD", stem)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    cleaned_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_stem).strip("._-")
    return f"{cleaned_stem or 'audio'}{suffix}"


def _audio_member_name(audio_name: str) -> str:
    return f"audio\\{_safe_archive_filename(audio_name)}"
