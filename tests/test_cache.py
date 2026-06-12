from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from louvorja_slides.cache import audio_sha256, cache_key, cache_path, load_json, save_json


class CacheTest(unittest.TestCase):
    def test_audio_sha256_uses_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "song.mp3"
            path.write_bytes(b"abc")

            self.assertEqual(audio_sha256(path), "ba7816bf8f01cfea")

    def test_save_and_load_json_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = cache_path(Path(tmp), "abc123", "transcript", variant="large-v3")
            save_json(path, {"words": [{"text": "Fala"}]})

            self.assertEqual(load_json(path), {"words": [{"text": "Fala"}]})

    def test_cache_key_changes_when_quality_config_changes(self) -> None:
        self.assertNotEqual(
            cache_key({"whisper_model": "medium", "alignment": "mms"}),
            cache_key({"whisper_model": "large-v3", "alignment": "mms"}),
        )

    def test_save_json_uses_unique_temp_files_per_write(self) -> None:
        temp_names: list[str] = []
        real_replace = os.replace

        def spy_replace(src: object, dst: object) -> None:
            temp_names.append(Path(str(src)).name)
            real_replace(src, dst)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "payload.json"
            with patch("louvorja_slides.cache.os.replace", side_effect=spy_replace):
                save_json(path, {"value": 1})
                save_json(path, {"value": 2})

            self.assertEqual(load_json(path), {"value": 2})
            self.assertEqual(len(temp_names), 2)
            self.assertNotEqual(
                temp_names[0],
                temp_names[1],
                "concurrent writers must not share one predictable temp file",
            )
            self.assertNotIn("payload.json.tmp", temp_names)
            leftovers = [p.name for p in Path(tmp).iterdir() if p.name != "payload.json"]
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
