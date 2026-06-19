#!/usr/bin/env bash
set -euo pipefail

# RenegadeFM Ultimate - Installer
PIP_BIN=${PIP_BIN:-pip3}
PYTHON_BIN=${PYTHON_BIN:-python3}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_PATH="$SCRIPT_DIR/file_manage.py"

echo "------------------------------------------"
echo "   RenegadeFM Ultimate - Installation"
echo "------------------------------------------"

# 1. Kontrola pip3
if ! command -v "$PIP_BIN" >/dev/null 2>&1; then
  echo "[ERR] pip3 nebyl nalezen. Nainstaluj ho: pkg install python-pip"
  exit 1
fi

# 2. Instalace závislostí
echo "[1/3] Instaluji závislosti..."
"$PIP_BIN" install --upgrade prompt_toolkit --break-system-packages

# 3. Vytvoření spouštěče rfm
echo "[2/3] Vytvářím spouštěč 'rfm'..."

# Detekce bin složky
if [[ -n "${PREFIX:-}" ]]; then
    BIN_DIR="$PREFIX/bin"
elif [[ -d "$HOME/.local/bin" ]]; then
    BIN_DIR="$HOME/.local/bin"
else
    BIN_DIR="/usr/local/bin"
fi

RFM_BIN="$BIN_DIR/rfm"

cat <<EOF > "$RFM_BIN"
#!/usr/bin/env bash
# RenegadeFM Launcher
$PYTHON_BIN "$APP_PATH" "\$@"
EOF

chmod +x "$RFM_BIN"

# 4. Kontrola rfm v PATH
echo "[3/3] Kontrola konfigurace..."
if ! command -v rfm >/dev/null 2>&1; then
    echo "[WARN] Složka $BIN_DIR není v tvé PATH."
    echo "       Přidej ji do ~/.bashrc nebo ~/.zshrc:"
    echo "       export PATH=\$PATH:$BIN_DIR"
fi

echo "------------------------------------------"
echo "[OK] Instalace dokončena!"
echo "Nyní můžeš spustit správce příkazem: rfm"
echo "------------------------------------------"
