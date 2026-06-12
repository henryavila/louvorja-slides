from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from louvorja_slides import local_pipeline
from louvorja_slides.cache import audio_sha256, cache_key, cache_path, load_json, save_json
from louvorja_slides.local_pipeline import LocalPipelineConfig, transcribe_audio_local
from louvorja_slides.transcription import Transcript, TranscribedPhoneme, TranscribedWord


class LocalPipelineTest(unittest.TestCase):
    def test_pipeline_uses_separation_decode_whisper_and_alignment_when_enabled(self) -> None:
        events: list[str] = []

        def fake_separate(audio_path: Path, **kwargs: object) -> Path:
            events.append("separate")
            return audio_path.with_suffix(".vocals.wav")

        def fake_decode(audio_path: Path) -> object:
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
                    detected_language=transcript.detected_language,
                    duration_seconds=transcript.duration_seconds,
                )

        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "song.mp3"
            audio.write_bytes(b"audio")
            transcript = transcribe_audio_local(
                audio,
                config=LocalPipelineConfig(
                    cache_root=Path(tmp) / ".cache",
                    alignment="mms",
                ),
                separate_vocals_fn=fake_separate,
                decode_fn=fake_decode,
                transcriber=FakeTranscriber(),
                aligner=FakeAligner(),
            )

        self.assertEqual(events, ["separate", "decode:song.vocals.wav", "whisper", "align"])
        self.assertEqual(transcript.words[0].source, "mms_align")

    def test_pipeline_can_skip_quality_stages_explicitly(self) -> None:
        events: list[str] = []

        def fake_decode(audio_path: Path) -> object:
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

        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "song.mp3"
            audio.write_bytes(b"audio")
            transcript = transcribe_audio_local(
                audio,
                config=LocalPipelineConfig(
                    cache_root=Path(tmp) / ".cache",
                    vocal_separation="none",
                    alignment="none",
                ),
                decode_fn=fake_decode,
                transcriber=FakeTranscriber(),
            )

        self.assertEqual(events, ["decode:song.mp3", "whisper"])
        self.assertEqual(transcript.words[0].source, "whisper")

    def test_pipeline_cache_distinguishes_phoneme_schema_for_aligned_transcripts(
        self,
    ) -> None:
        events: list[str] = []

        def fake_decode(audio_path: Path) -> object:
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

        class FakeTranscriber:
            def transcribe_samples(self, **kwargs: object) -> Transcript:
                events.append("whisper")
                return Transcript(
                    words=[TranscribedWord("Fala", 1.0, 1.5, source="whisper")],
                    detected_language="pt",
                    duration_seconds=10.0,
                )

        class FakeAligner:
            def align_transcript(
                self,
                transcript: Transcript,
                **kwargs: object,
            ) -> Transcript:
                events.append("align")
                return Transcript(
                    words=[TranscribedWord("Fala", 1.1, 1.6, source="mms_align")],
                    detected_language=transcript.detected_language,
                    duration_seconds=transcript.duration_seconds,
                    phonemes=[
                        TranscribedPhoneme(
                            symbol="f",
                            start=1.1,
                            end=1.2,
                            parent_word_idx=0,
                            source="mms_align",
                        )
                    ],
                )

        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "song.mp3"
            audio.write_bytes(b"audio")
            cache_root = Path(tmp) / ".cache"
            audio_id = audio_sha256(audio)
            config = LocalPipelineConfig(
                cache_root=cache_root,
                whisper_model="medium",
                vocal_separation="none",
                alignment="mms",
            )

            schema_2_variant = cache_key(
                {
                    "schema": 2,
                    "sample_rate": 16000,
                    "whisper_token_timestamps": True,
                    "whisper_max_len": 1,
                    "whisper_split_on_word": True,
                    "whisper_entropy_thold": 2.2,
                    "whisper_no_speech_thold": 0.7,
                    "stage": "aligned",
                    "language": config.language,
                    "whisper_model": config.whisper_model,
                    "vocal_separation": config.vocal_separation,
                    "alignment": config.alignment,
                }
            )
            save_json(
                cache_path(cache_root, audio_id, "transcript", schema_2_variant),
                Transcript(
                    words=[TranscribedWord("Fala", 9.0, 9.0, source="old_cache")],
                    detected_language="pt",
                    duration_seconds=10.0,
                    phonemes=[
                        TranscribedPhoneme(
                            symbol="24",
                            start=9.0,
                            end=9.1,
                            parent_word_idx=0,
                            source="mms_align",
                        )
                    ],
                ).to_dict(),
            )

            transcript = transcribe_audio_local(
                audio,
                config=config,
                decode_fn=fake_decode,
                transcriber=FakeTranscriber(),
                aligner=FakeAligner(),
            )

            current_variant = local_pipeline._variant(
                stage="aligned",
                language=config.language,
                whisper_model=config.whisper_model,
                vocal_separation=config.vocal_separation,
                alignment=config.alignment,
            )
            cached = load_json(
                cache_path(cache_root, audio_id, "transcript", current_variant)
            )

        self.assertEqual(events, ["decode", "whisper", "align"])
        self.assertEqual(len(transcript.phonemes or []), 1)
        self.assertIsInstance((cached or {}).get("phonemes"), list)


if __name__ == "__main__":
    unittest.main()
