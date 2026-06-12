from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from louvorja_slides.engines import (
    AudioToDocumentConfig,
    LocalLinuxEngine,
    MacTitanEngine,
    select_engine,
)
from louvorja_slides.transcription import Transcript, TranscribedWord


class EngineSelectionTest(unittest.TestCase):
    def test_select_engine_uses_mac_titan_on_darwin(self) -> None:
        engine = select_engine("auto", platform_system="Darwin", platform_release="23.0")

        self.assertIsInstance(engine, MacTitanEngine)

    def test_select_engine_uses_local_linux_on_linux_and_wsl(self) -> None:
        linux = select_engine("auto", platform_system="Linux", platform_release="6.8.0")
        wsl = select_engine(
            "auto",
            platform_system="Linux",
            platform_release="5.15.153.1-microsoft-standard-WSL2",
        )

        self.assertIsInstance(linux, LocalLinuxEngine)
        self.assertIsInstance(wsl, LocalLinuxEngine)

    def test_select_engine_accepts_explicit_overrides(self) -> None:
        self.assertIsInstance(
            select_engine("titan", platform_system="Linux", platform_release="6.8.0"),
            MacTitanEngine,
        )
        self.assertIsInstance(
            select_engine("local", platform_system="Darwin", platform_release="23.0"),
            LocalLinuxEngine,
        )


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

        engine = LocalLinuxEngine(transcribe_fn=fake_transcribe)
        audio = Path("song.mp3")

        doc = engine.transcribe(audio, AudioToDocumentConfig(title="Minha musica"))

        self.assertEqual(calls[0][0], audio)
        self.assertEqual(doc.metadata.title, "Minha musica")
        self.assertIs(doc.transcript, transcript)
        self.assertEqual(doc.sections[0].lines[0].text, "Fala comigo")

    def test_mac_engine_delegates_to_titan_transcribe(self) -> None:
        doc = SimpleNamespace(metadata=SimpleNamespace(title="Titan"), sections=[])
        calls: list[tuple[Path, dict[str, object]]] = []

        def fake_titan(audio_path: Path, **kwargs: object) -> SimpleNamespace:
            calls.append((audio_path, kwargs))
            return doc

        engine = MacTitanEngine(transcribe_fn=fake_titan)
        config = AudioToDocumentConfig(
            language="pt",
            cache=False,
            force_mock=True,
            backend="mps",
            whisper_model="medium",
        )

        result = engine.transcribe(Path("song.mp3"), config)

        self.assertIs(result, doc)
        self.assertEqual(
            calls[0][1],
            {
                "language": "pt",
                "cache": False,
                "force_mock": True,
                "backend": "mps",
                "transcription_model_id": "medium",
            },
        )


if __name__ == "__main__":
    unittest.main()
