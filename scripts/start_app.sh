#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Missing virtualenv at ${VENV_DIR}" >&2
  exit 1
fi

source "${VENV_DIR}/bin/activate"
export PYTHONUNBUFFERED=1
exec python -m app.main
