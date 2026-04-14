#!/usr/bin/env bash
# scripts/setup_venv.sh — Create and activate a Python virtual environment,
# then install all project dependencies.
#
# Usage:
#   chmod +x scripts/setup_venv.sh
#   ./scripts/setup_venv.sh
#
# After running this script, activate the venv with:
#   source venv/bin/activate

set -euo pipefail

PYTHON=${PYTHON:-python3}
VENV_DIR=${VENV_DIR:-venv}
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Creating virtual environment in ${REPO_ROOT}/${VENV_DIR} …"
"${PYTHON}" -m venv "${REPO_ROOT}/${VENV_DIR}"

echo "==> Activating virtual environment …"
# shellcheck disable=SC1091
source "${REPO_ROOT}/${VENV_DIR}/bin/activate"

echo "==> Upgrading pip …"
pip install --quiet --upgrade pip

echo "==> Installing project (including dev extras) …"
pip install --quiet -e "${REPO_ROOT}[dev]"

echo ""
echo "✓  Setup complete."
echo "   Activate with:  source ${VENV_DIR}/bin/activate"
echo "   Run EOD:        market-agent run-eod --dry-run"
