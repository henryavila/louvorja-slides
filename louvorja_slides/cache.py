from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def audio_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def cache_key(mapping: dict[str, Any]) -> str:
    data = json.dumps(mapping, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def cache_path(root: Path, audio_id: str, stage: str, variant: str) -> Path:
    return Path(root) / audio_id / stage / f"{variant}.json"


def load_json(path: Path) -> dict[str, Any] | None:
    path = Path(path)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"cache payload must be an object: {path}")
    return data


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    temp_path.replace(path)
