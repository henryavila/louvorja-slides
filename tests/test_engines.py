from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from louvorja_slides.engines import (
    AudioToDocumentConfig,
    LocalEngine,
    select_engine,
)
from louvorja_slides.transcription import Transcript, TranscribedWord


class EngineSelectionTest(unittest.TestCase):
    def test_select_engine_uses_local_on_darwin(self) -> None:
        engine = select_engine("auto", platform_system="Darwin", platform_release="23.0")

        self.assertIsInstance(engine, LocalEngine)

    def test_select_engine_uses_local_on_linux_and_wsl(self) -> None:
        linux = select_engine("auto", platform_system="Linux", platform_release="6.8.0")
        wsl = select_engine(
            "auto",
            platform_system="Linux",
            platform_release="5.15.153.1-microsoft-standard-WSL2",
        )

        self.assertIsInstance(linux, LocalEngine)
        self.assertIsInstance(wsl, LocalEngine)

    def test_select_engine_accepts_explicit_overrides(self) -> None:
        self.assertIsInstance(
            select_engine("local", platform_system="Darwin", platform_release="23.0"),
            LocalEngine,
        )

    def test_select_engine_rejects_titan_runtime_dependency(self) -> None:
        with self.assertRaisesRegex(ValueError, "reference-only"):
            select_engine("titan", platform_system="Darwin", platform_release="23.0")


class EngineContractTest(unittest.TestCase):
    def test_local_engine_converts_transcript_to_document(self) -> None:
        transcript = Transcript(
            words=[
                TranscribedWord("Fala", 1.0, 1.3),
                TranscribedWord("comigo", 1.4, 1.8),
            ],
            detected_language="pt",
            duration_seconds=5.0,
        )
        calls: list[tuple[Path, AudioToDocumentConfig]] = []

        def fake_transcribe(audio_path: Path, config: AudioToDocumentConfig) -> Transcript:
            calls.append((audio_path, config))
            return transcript

        engine = LocalEngine(transcribe_fn=fake_transcribe)
        audio = Path("song.mp3")

        doc = engine.transcribe(audio, AudioToDocumentConfig(title="Minha musica"))

        self.assertEqual(calls[0][0], audio)
        self.assertEqual(doc.metadata.title, "Minha musica")
        self.assertIs(doc.transcript, transcript)
        self.assertEqual(doc.sections[0].lines[0].text, "Fala comigo")

    def test_local_engine_rejects_mock_device(self) -> None:
        def fake_transcribe(audio_path: Path, config: AudioToDocumentConfig) -> Transcript:
            raise AssertionError("the local engine must reject mock before transcribing")

        engine = LocalEngine(transcribe_fn=fake_transcribe)

        with self.assertRaisesRegex(ValueError, "mock"):
            engine.transcribe(Path("song.mp3"), AudioToDocumentConfig(force_mock=True))

    def test_local_engine_forwards_backend_device_to_pipeline(self) -> None:
        transcript = Transcript(
            words=[TranscribedWord("Fala", 1.0, 1.3)],
            detected_language="pt",
            duration_seconds=5.0,
        )
        calls: list[object] = []

        class FakeLocalPipelineConfig:
            def __init__(self, **kwargs: object) -> None:
                self.__dict__.update(kwargs)

        def fake_transcribe_audio_local(
            audio_path: Path, *, config: object
        ) -> Transcript:
            calls.append(config)
            return transcript

        fake_module = ModuleType("louvorja_slides.local_pipeline")
        fake_module.LocalPipelineConfig = FakeLocalPipelineConfig
        fake_module.transcribe_audio_local = fake_transcribe_audio_local

        with patch.dict(sys.modules, {"louvorja_slides.local_pipeline": fake_module}):
            LocalEngine().transcribe(
                Path("song.mp3"),
                AudioToDocumentConfig(backend="mps"),
            )

        pipeline_config = calls[0]
        self.assertEqual(pipeline_config.device, "mps")


if __name__ == "__main__":
    unittest.main()
