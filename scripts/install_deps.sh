#!/usr/bin/env bash
# install_deps.sh — Install system dependencies on Raspberry Pi OS (Debian Bookworm)
set -euo pipefail

echo "=== Smart Mirror Pi — dependency installer ==="
echo "Requires: Raspberry Pi OS (Bookworm) or Debian 12+"
echo ""

sudo apt-get update

echo "--- Installing system packages ---"
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    ffmpeg \
    libgstreamer1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    libqt6multimedia6 \
    libqt6multimediawidgets6 \
    libqt6opengl6-dev \
    qt6-multimedia-dev \
    fonts-noto \
    fonts-noto-cjk \
    v4l-utils \
    rpicam-apps \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0

echo ""
echo "--- Creating Python virtual environment ---"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

python3 -m venv "${REPO_ROOT}/venv"
"${REPO_ROOT}/venv/bin/pip" install --upgrade pip
"${REPO_ROOT}/venv/bin/pip" install -r "${REPO_ROOT}/requirements.txt"

echo ""
echo "=== Done! Run the app with: ==="
echo "  cd ${REPO_ROOT}"
echo "  ./venv/bin/python -m app.main"
