#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_SRC="${ROOT_DIR}/systemd/smart-mirror.service"
SERVICE_DEST="/etc/systemd/system/smart-mirror.service"

sudo cp "${SERVICE_SRC}" "${SERVICE_DEST}"
sudo sed -i "s|/opt/smart-mirror-pi|${ROOT_DIR}|g" "${SERVICE_DEST}"
sudo systemctl daemon-reload
sudo systemctl enable smart-mirror.service
sudo systemctl restart smart-mirror.service
