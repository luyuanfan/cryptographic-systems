#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 1; }

python3 -m venv "$VENV"

"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$ROOT/requirements.txt"

"$VENV/bin/python3" -c "import numpy, pandas, unidecode" || {
    echo "ERROR: dependency install succeeded but import failed"
    exit 1
}

chmod a+x "$ROOT"/bin/vigenere-encrypt \
        "$ROOT"/bin/vigenere-decrypt \
        "$ROOT"/bin/vigenere-keylength \
        "$ROOT"/bin/vigenere-cryptanalyze

echo "Build complete."
exit 0