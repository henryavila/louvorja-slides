from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "install_linux_local_engine.sh"


class InstallScriptTest(unittest.TestCase):
    def test_linux_install_script_is_valid_bash(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_linux_install_script_documents_required_apt_dependencies(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("python3.12-dev", text)
        self.assertIn("python3.12-venv", text)
        self.assertIn("build-essential", text)
        self.assertIn("sudo apt-get install", text)
        self.assertIn("setuptools<82", text)
        self.assertIn("python -m pip install -r requirements.txt", text)
        self.assertIn("audio_separator.separator", text)

    def test_linux_install_script_verifies_torchaudio_alignment_stack(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "torch==2.11.0",
            (ROOT / "requirements.txt").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "torchaudio==2.11.0",
            (ROOT / "requirements.txt").read_text(encoding="utf-8"),
        )
        self.assertIn("torchaudio", text)
        self.assertIn("torchaudio.pipelines", text)
        self.assertIn("MMS_FA", text)
        self.assertIn("torch.__version__", text)
        self.assertIn("torchaudio.__version__", text)


if __name__ == "__main__":
    unittest.main()
