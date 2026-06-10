from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from louvorja_slides.cache import audio_sha256, cache_key, cache_path, save_json
from louvorja_slides.local_pipeline import LocalPipelineConfig, transcribe_audio_local
from louvorja_slides.transcription import Transcript, TranscribedWord


class LocalPipelineTest(unittest.TestCase):
    def test_pipeline_uses_separation_decode_whisper_and_alignment(self) -> None:
        events = []

        def fake_separate(audio_path: Path, **kwargs: object) -> Path:
            events.append("separate")
            return audio_path.with_suffix(".vocals.wav")

        def fake_decode(audio_path: Path):
            events.append(f"decode:{audio_path.name}")
            return type(
                "Decoded",
                (),
                {
                    "samples": np.zeros(16000, dtype=np.float32),
                    "sample_rate": 16000,
                    "duration_seconds": 10.0,
                },
            )()

        class FakeTranscriber:
            def transcribe_samples(self, **kwargs: object) -> Transcript:
                events.append("whisper")
                return Transcript(
                    words=[TranscribedWord("Fala", 1.0, 1.5, source="whisper")],
                    detected_language="pt",
                    duration_seconds=10.0,
                )

        class FakeAligner:
            def align_transcript(self, transcript: Transcript, **kwargs: object) -> Transcript:
                events.append("align")
                return Transcript(
                    words=[TranscribedWord("Fala", 1.1, 1.6, source="mms_align")],
                    detected_language="pt",
                    duration_seconds=10.0,
                )

        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "song.mp3"
            audio.write_bytes(b"audio")
            transcript = transcribe_audio_local(
                audio,
                config=LocalPipelineConfig(cache_root=Path(tmp) / ".cache"),
                separate_vocals_fn=fake_separate,
                decode_fn=fake_decode,
                transcriber=FakeTranscriber(),
                aligner=FakeAligner(),
            )

        self.assertEqual(events, ["separate", "decode:song.vocals.wav", "whisper", "align"])
        self.assertEqual(transcript.words[0].source, "mms_align")

    def test_pipeline_returns_aligned_cache_without_loading_ml_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")
            audio_id = audio_sha256(audio)
            config = LocalPipelineConfig(cache_root=root / ".cache")
            variant = cache_key(config.cache_identity(stage="aligned"))
            cached = Transcript(
                words=[TranscribedWord("Cached", 1.0, 1.2, source="mms_align")],
                detected_language="pt",
                duration_seconds=2.0,
            )
            save_json(cache_path(config.cache_root, audio_id, "transcript", variant), cached.to_dict())

            transcript = transcribe_audio_local(
                audio,
                config=config,
                separate_vocals_fn=lambda *args, **kwargs: self.fail("separation should not run"),
                decode_fn=lambda *args, **kwargs: self.fail("decode should not run"),
                transcriber=object(),
                aligner=object(),
            )

        self.assertEqual(transcript.words[0].text, "Cached")

    def test_pipeline_uses_raw_cache_but_still_runs_alignment(self) -> None:
        events = []

        def fake_decode(audio_path: Path):
            events.append("decode")
            return type(
                "Decoded",
                (),
                {
                    "samples": np.zeros(16000, dtype=np.float32),
                    "sample_rate": 16000,
                    "duration_seconds": 10.0,
                },
            )()

        class FakeAligner:
            def align_transcript(self, transcript: Transcript, **kwargs: object) -> Transcript:
                events.append("align")
                return transcript

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")
            audio_id = audio_sha256(audio)
            config = LocalPipelineConfig(cache_root=root / ".cache", vocal_separation="none")
            raw_variant = cache_key(config.cache_identity(stage="raw"))
            raw = Transcript(
                words=[TranscribedWord("Raw", 1.0, 1.2, source="whisper")],
                detected_language="pt",
                duration_seconds=2.0,
            )
            save_json(cache_path(config.cache_root, audio_id, "transcript", raw_variant), raw.to_dict())

            transcript = transcribe_audio_local(
                audio,
                config=config,
                decode_fn=fake_decode,
                transcriber=object(),
                aligner=FakeAligner(),
            )

        self.assertEqual(events, ["decode", "align"])
        self.assertEqual(transcript.words[0].text, "Raw")

    def test_pipeline_returns_raw_cache_without_running_separation_when_alignment_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "song.mp3"
            audio.write_bytes(b"audio")
            audio_id = audio_sha256(audio)
            config = LocalPipelineConfig(cache_root=root / ".cache", alignment="none")
            raw_variant = cache_key(config.cache_identity(stage="raw"))
            raw = Transcript(
                words=[TranscribedWord("Raw", 1.0, 1.2, source="whisper")],
                detected_language="pt",
                duration_seconds=2.0,
            )
            save_json(cache_path(config.cache_root, audio_id, "transcript", raw_variant), raw.to_dict())

            transcript = transcribe_audio_local(
                audio,
                config=config,
                separate_vocals_fn=lambda *args, **kwargs: self.fail("separation should not run"),
                decode_fn=lambda *args, **kwargs: self.fail("decode should not run"),
            )

        self.assertEqual(transcript.words[0].text, "Raw")

    def test_cache_variant_changes_with_whisper_model(self) -> None:
        medium = LocalPipelineConfig(whisper_model="medium")
        large = LocalPipelineConfig(whisper_model="large-v3")

        self.assertNotEqual(
            cache_key(medium.cache_identity(stage="raw")),
            cache_key(large.cache_identity(stage="raw")),
        )


if __name__ == "__main__":
    unittest.main()
