#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
VENV_DIR="${VENV_DIR:-"${ROOT_DIR}/.venv"}"

APT_PACKAGES=(
  python3.12-dev
  python3.12-venv
  build-essential
  ffmpeg
  git
)

missing_packages=()
if command -v dpkg-query >/dev/null 2>&1; then
  for package in "${APT_PACKAGES[@]}"; do
    if ! dpkg-query -W -f='${Status}' "${package}" 2>/dev/null | grep -q "install ok installed"; then
      missing_packages+=("${package}")
    fi
  done
else
  echo "warning: dpkg-query not found; skipping apt package check" >&2
fi

if ((${#missing_packages[@]} > 0)); then
  echo "Missing Linux packages required by the local engine build:" >&2
  printf '  %s\n' "${missing_packages[@]}" >&2
  echo >&2
  echo "Run this command, then run this script again:" >&2
  printf 'sudo apt-get update && sudo apt-get install -y' >&2
  printf ' %q' "${missing_packages[@]}" >&2
  echo >&2
  exit 2
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "error: ${PYTHON_BIN} was not found in PATH" >&2
  exit 2
fi

"${PYTHON_BIN}" - <<'PY'
import sys

if sys.version_info < (3, 12):
    version = ".".join(str(part) for part in sys.version_info[:3])
    raise SystemExit(f"Python 3.12+ is required, found {version}")
PY

cd "${ROOT_DIR}"
"${PYTHON_BIN}" -m venv "${VENV_DIR}"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip "setuptools<82" wheel
python -m pip install -r requirements.txt

python - <<'PY'
import importlib.util

required_modules = [
    "imageio_ffmpeg",
    "numpy",
    "pywhispercpp",
    "audio_separator",
    "audio_separator.separator",
    "onnxruntime",
    "torch",
    "torchaudio",
    "torchaudio.pipelines",
]

missing = [name for name in required_modules if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit(f"Missing Python modules after install: {', '.join(missing)}")

from torchaudio.pipelines import MMS_FA
import torch
import torchaudio


def _major_minor(version: str) -> tuple[int, int]:
    clean = version.split("+", 1)[0]
    major, minor, *_ = clean.split(".")
    return int(major), int(minor)


if _major_minor(torch.__version__) != _major_minor(torchaudio.__version__):
    raise SystemExit(
        "torch and torchaudio major/minor versions must match: "
        f"torch={torch.__version__}, torchaudio={torchaudio.__version__}"
    )

_ = MMS_FA.get_labels()

print("Local Linux engine dependencies are installed.")
PY
