#!/usr/bin/env bash
set -euo pipefail

# Simple installer for RenegadeFM dependencies
PIP_BIN=${PIP_BIN:-pip3}

if ! command -v "$PIP_BIN" >/dev/null 2>&1; then
  echo "[ERR] pip3 nebyl nalezen. Nainstaluj ho nebo nastav PIP_BIN."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[INFO] Instaluji závislosti z requirements.txt"
"$PIP_BIN" install -r requirements.txt

echo "[OK] Hotovo. Spusť aplikaci: python3 file_manage.py"
