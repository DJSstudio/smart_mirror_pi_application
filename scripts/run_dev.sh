#!/usr/bin/env bash
# run_dev.sh — Launch the app from the repo root in development mode.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

# ── GStreamer Qt6 bridge check ─────────────────────────────────────────────
# Qt Multimedia requires the gstreamer1.0-qt6 package on Linux.
# Without it you'll get "No QtMultimedia backends found" and video preview
# will be completely broken.  Run with --install-gstreamer to fix automatically.
GSTREAMER_PKGS=(
    gstreamer1.0-plugins-base
    gstreamer1.0-plugins-good
    gstreamer1.0-plugins-bad
    gstreamer1.0-plugins-ugly
    gstreamer1.0-libav
    gstreamer1.0-tools
    gstreamer1.0-qt6
)

if [[ "${1:-}" == "--install-gstreamer" ]]; then
    echo "=== Installing GStreamer packages ==="
    sudo apt-get update
    sudo apt-get install -y "${GSTREAMER_PKGS[@]}"
    echo "=== Done. Re-run without --install-gstreamer to start the app. ==="
    exit 0
fi

# Warn (don't block) if the Qt6 bridge isn't installed
if command -v dpkg-query &>/dev/null; then
    if ! dpkg-query -W -f='${Status}' gstreamer1.0-qt6 2>/dev/null | grep -q "install ok installed"; then
        echo ""
        echo "⚠  WARNING: gstreamer1.0-qt6 is not installed."
        echo "   Video preview will not work (Qt Multimedia backend missing)."
        echo "   Fix with:  bash scripts/run_dev.sh --install-gstreamer"
        echo ""
    fi
fi

# Prefer the venv if it exists, otherwise use the system Python
if [ -x "${REPO_ROOT}/venv/bin/python" ]; then
    PYTHON="${REPO_ROOT}/venv/bin/python"
else
    PYTHON="$(command -v python3)"
fi

# ── Qt platform auto-detection ─────────────────────────────────────────────
# Priority: explicit env override → Wayland → X11 → eglfs (Pi framebuffer)
if [ -z "${QT_QPA_PLATFORM:-}" ]; then
    if [ -n "${WAYLAND_DISPLAY:-}" ]; then
        export QT_QPA_PLATFORM="wayland"
    elif [ -n "${DISPLAY:-}" ]; then
        export QT_QPA_PLATFORM="xcb"
    else
        # No display server — use eglfs (Pi direct framebuffer, no X11 needed)
        export QT_QPA_PLATFORM="eglfs"
        export QT_QPA_EGLFS_ALWAYS_SET_MODE=1
    fi
fi

echo "Using Qt platform: ${QT_QPA_PLATFORM}"

# ── System library path — helps pip-PySide6 find system GStreamer ──────────
# pip-PySide6 bundles its own Qt but links GStreamer dynamically at runtime.
# Without this, dlopen("libgstreamer-1.0.so.0") silently fails on ARM64 Pi.
export LD_LIBRARY_PATH="/usr/lib/aarch64-linux-gnu:/usr/lib/aarch64-linux-gnu/gstreamer-1.0${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

# ── GStreamer hints for Raspberry Pi ───────────────────────────────────────
# On Pi Wayland the GStreamer GL sink needs to know which EGL platform to use.
# Without this the video pipeline can negotiate successfully but output a blank
# (all-black) frame to the VideoOutput surface.
if [ "${QT_QPA_PLATFORM}" = "wayland" ]; then
    export GST_GL_WINDOW="${GST_GL_WINDOW:-wayland}"
    export GST_GL_PLATFORM="${GST_GL_PLATFORM:-egl}"
fi
# Force GStreamer to use the correct Qt multimedia backend when multiple are present.
export GST_PLUGIN_FEATURE_RANK="${GST_PLUGIN_FEATURE_RANK:-glimagesink:257}"

export PYTHONUNBUFFERED=1

exec "${PYTHON}" -m app.main "$@"
