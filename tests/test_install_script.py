from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "install_linux_local_engine.sh"


def _write_dpkg_query_stub(directory: Path, missing_package: str | None) -> None:
    stub = directory / "dpkg-query"
    condition = (
        f'if [ "${{!#}}" = "{missing_package}" ]; then exit 1; fi\n'
        if missing_package is not None
        else ""
    )
    stub.write_text(
        "#!/usr/bin/env bash\n" + condition + 'printf "install ok installed"\n',
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)


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

    def test_linux_install_script_exits_2_when_apt_packages_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stub_dir = Path(tmp) / "bin"
            stub_dir.mkdir()
            _write_dpkg_query_stub(stub_dir, missing_package="build-essential")

            result = subprocess.run(
                ["bash", str(SCRIPT)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "PATH": f"{stub_dir}:{os.environ['PATH']}"},
            )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("build-essential", result.stderr)
        self.assertIn("sudo apt-get", result.stderr)

    def test_linux_install_script_exits_2_when_python_binary_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stub_dir = Path(tmp) / "bin"
            stub_dir.mkdir()
            _write_dpkg_query_stub(stub_dir, missing_package=None)

            result = subprocess.run(
                ["bash", str(SCRIPT)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env={
                    **os.environ,
                    "PATH": f"{stub_dir}:{os.environ['PATH']}",
                    "PYTHON_BIN": "definitely-missing-python-binary",
                },
            )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("definitely-missing-python-binary", result.stderr)

    def test_linux_install_script_offers_optional_model_prefetch(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("--prefetch-models", text)
        self.assertIn("MMS_FA.get_model()", text)

    def test_linux_install_script_rejects_unknown_options(self) -> None:
        result = subprocess.run(
            ["bash", str(SCRIPT), "--definitely-unknown-option"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("--definitely-unknown-option", result.stderr)


if __name__ == "__main__":
    unittest.main()
