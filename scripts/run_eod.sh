#!/usr/bin/env bash
# scripts/run_eod.sh — Activate the venv and run the EOD market research pipeline.
#
# Usage (manual):
#   ./scripts/run_eod.sh
#
# Usage (cron — see scripts/cron.example):
#   30 21 * * 1-5 /path/to/scripts/run_eod.sh >> /path/to/logs/eod.log 2>&1

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${REPO_ROOT}/venv"
LOG_DIR="${REPO_ROOT}/logs"

# Load .env if present (so the script works outside the venv activation)
if [[ -f "${REPO_ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${REPO_ROOT}/.env"
    set +a
fi

# Activate venv
if [[ ! -f "${VENV_DIR}/bin/activate" ]]; then
    echo "ERROR: venv not found at ${VENV_DIR}.  Run ./scripts/setup_venv.sh first." >&2
    exit 1
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

mkdir -p "${LOG_DIR}"

echo "==> Starting EOD pipeline at $(date)"
market-agent run-eod "$@"
echo "==> EOD pipeline finished at $(date)"
