from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping


def audio_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def cache_key(mapping: Mapping[str, Any]) -> str:
    payload = json.dumps(mapping, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def cache_path(root: Path, audio_id: str, stage: str, variant: str) -> Path:
    safe_stage = _safe_part(stage)
    safe_variant = _safe_part(variant)
    return Path(root) / _safe_part(audio_id) / safe_stage / f"{safe_variant}.json"


def load_json(path: Path) -> dict[str, Any] | None:
    path = Path(path)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"cache payload must be a JSON object: {path}")
    return payload


def save_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        delete=False,
    ) as handle:
        tmp_path = Path(handle.name)
        json.dump(payload, handle, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    tmp_path.replace(path)


def _safe_part(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(value))
    return cleaned or "cache"
