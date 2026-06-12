from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
