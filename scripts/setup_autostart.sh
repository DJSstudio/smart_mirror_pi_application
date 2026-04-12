#!/usr/bin/env bash
# setup_autostart.sh — Install and enable the systemd user service for autostart.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="smart-mirror"
SERVICE_SRC="${REPO_ROOT}/systemd/${SERVICE_NAME}.service"
SERVICE_DST="${HOME}/.config/systemd/user/${SERVICE_NAME}.service"

if [ ! -f "${SERVICE_SRC}" ]; then
    echo "ERROR: Service file not found: ${SERVICE_SRC}"
    exit 1
fi

echo "Installing service unit to ${SERVICE_DST}…"
mkdir -p "$(dirname "${SERVICE_DST}")"

# Patch WorkingDirectory and ExecStart with the actual path
sed "s|/home/pi/smart_mirror_pi|${REPO_ROOT}|g" "${SERVICE_SRC}" > "${SERVICE_DST}"

echo "Enabling and starting service…"
systemctl --user daemon-reload
systemctl --user enable --now "${SERVICE_NAME}.service"

echo ""
echo "=== Autostart configured ==="
echo "Status:  systemctl --user status ${SERVICE_NAME}"
echo "Logs:    journalctl --user -u ${SERVICE_NAME} -f"
echo "Disable: systemctl --user disable --now ${SERVICE_NAME}"
