#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update
sudo apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  ffmpeg \
  mpv \
  qml6-module-qtquick \
  qml6-module-qtquick-controls \
  qml6-module-qtmultimedia \
  libegl1 \
  libgles2

if ! command -v rpicam-vid >/dev/null 2>&1; then
  echo "Install the package that provides rpicam-vid on your Pi image before using the CSI camera."
fi
