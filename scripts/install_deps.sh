#!/usr/bin/env bash
# install_deps.sh — Install system dependencies on Raspberry Pi OS.
#
# Supports:
#   Trixie  (Debian 13) — recommended, full Qt Multimedia support
#   Bookworm (Debian 12) — limited: video playback will NOT work
set -euo pipefail

VERSION_CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME:-unknown}")"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== Smart Mirror Pi — dependency installer ==="
echo "Detected OS: ${VERSION_CODENAME}"
echo ""

sudo apt-get update

# ── Common packages (both Bookworm and Trixie) ────────────────────────────
COMMON_PKGS=(
    python3-pip
    python3-venv
    ffmpeg
    v4l-utils
    fonts-noto
    fonts-noto-cjk
    rpicam-apps
    # Input device tools (touch-to-screen mapping on Wayland)
    libinput-tools
    # v4l2loopback: virtual video device used for shared camera access
    # (ffmpeg writes the camera frames to /dev/video10, QCamera reads them
    #  for low-latency preview while ffmpeg also encodes to the recording file)
    v4l2loopback-dkms
    # GStreamer (needed for Qt Multimedia on Trixie)
    gstreamer1.0-plugins-base
    gstreamer1.0-plugins-good
    gstreamer1.0-plugins-bad
    gstreamer1.0-plugins-ugly
    gstreamer1.0-libav
    gstreamer1.0-tools
    # X11/xcb support (for single-screen dev or X11 fallback)
    libxcb-cursor0
    libxcb-icccm4
    libxcb-image0
    libxcb-keysyms1
    libxcb-randr0
    libxcb-render-util0
    libxcb-shape0
    libxcb-xinerama0
    libxcb-xkb1
    libxkbcommon-x11-0
)

if [[ "${VERSION_CODENAME}" == "trixie" ]]; then
    echo "--- Trixie: installing system PySide6 + Qt Multimedia ---"

    # System PySide6 is built against the same FFmpeg/GStreamer that ships
    # with Trixie, so Qt Multimedia works out of the box.
    TRIXIE_PKGS=(
        # PySide6 from system (properly linked against system Qt 6.8)
        python3-pyside6.qtcore
        python3-pyside6.qtgui
        python3-pyside6.qtwidgets
        python3-pyside6.qtopengl
        python3-pyside6.qtqml
        python3-pyside6.qtquick
        python3-pyside6.qtmultimedia
        python3-pyside6.qtnetwork
        # QML modules needed at runtime
        qml6-module-qtquick
        qml6-module-qtquick-controls
        qml6-module-qtquick-layouts
        qml6-module-qtquick-templates
        qml6-module-qtquick-window
        qml6-module-qtmultimedia
        # Qt Multimedia libraries + GStreamer bridge
        qt6-multimedia-dev
        libqt6multimedia6
    )

    sudo apt-get install -y "${COMMON_PKGS[@]}" "${TRIXIE_PKGS[@]}"

    echo ""
    echo "--- Creating Python venv with --system-site-packages ---"
    # Use --system-site-packages so the venv sees system PySide6.
    # pip-only deps (if any) can still be installed inside the venv.
    python3 -m venv --system-site-packages "${REPO_ROOT}/venv"
    "${REPO_ROOT}/venv/bin/pip" install --upgrade pip

    # Install non-Qt pip dependencies (skip PySide6 — it comes from the system)
    if [ -f "${REPO_ROOT}/requirements.txt" ]; then
        "${REPO_ROOT}/venv/bin/pip" install --ignore-installed PySide6 \
            -r "${REPO_ROOT}/requirements.txt" 2>/dev/null || true
    fi

else
    echo "--- Bookworm: installing base packages ---"
    echo ""
    echo "⚠  WARNING: On Bookworm, pip-PySide6's Qt Multimedia backend is"
    echo "   broken (FFmpeg 4/5 ABI mismatch). Video playback will NOT work."
    echo "   Upgrade to Raspberry Pi OS Trixie for full functionality."
    echo "   See: https://www.raspberrypi.com/software/"
    echo ""

    BOOKWORM_PKGS=(
        libgstreamer1.0-dev
        libqt6multimedia6
        libqt6multimediawidgets6
        libqt6opengl6-dev
        qt6-multimedia-dev
    )

    sudo apt-get install -y "${COMMON_PKGS[@]}" "${BOOKWORM_PKGS[@]}"

    echo ""
    echo "--- Creating Python virtual environment ---"
    python3 -m venv "${REPO_ROOT}/venv"
    "${REPO_ROOT}/venv/bin/pip" install --upgrade pip
    "${REPO_ROOT}/venv/bin/pip" install -r "${REPO_ROOT}/requirements.txt"
fi

echo ""
echo "--- Configuring v4l2loopback to load at boot ---"
# Persistent module load + options so /dev/video10 exists after every reboot.
# video_nr=10 → fixed device path so the app always knows where to find it.
# exclusive_caps=0 is intentional: Qt enumerates cameras before the CSI feeder
# starts. With exclusive_caps=1 the node is OUTPUT-only at that point, so Qt
# never caches it and the app falls back to the delayed UDP preview.
# card_label gives it a friendly name in QMediaDevices.
sudo tee /etc/modules-load.d/v4l2loopback.conf >/dev/null <<'EOF'
v4l2loopback
EOF
sudo tee /etc/modprobe.d/v4l2loopback.conf >/dev/null <<'EOF'
options v4l2loopback video_nr=10 card_label=MirrorPreview exclusive_caps=0
EOF
# Load now without reboot
sudo modprobe -r v4l2loopback 2>/dev/null || true
sudo modprobe v4l2loopback video_nr=10 card_label=MirrorPreview exclusive_caps=0
loopback_caps="$(cat /sys/module/v4l2loopback/parameters/exclusive_caps 2>/dev/null || true)"
if [[ "${loopback_caps}" != "N" && "${loopback_caps}" != "0" ]]; then
    echo "ERROR: v4l2loopback is still loaded with exclusive_caps enabled."
    echo "Stop the smart-mirror service, unload v4l2loopback, and rerun this installer."
    exit 1
fi
echo "  v4l2loopback loaded; /dev/video10 is the preview pipe."

echo ""
echo "=== Done! ==="
echo "  Run the app:  bash scripts/run_dev.sh"
