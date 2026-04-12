#!/usr/bin/env bash
# run_dev.sh — Launch the app from the repo root in development mode.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

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

# ── GStreamer hints for Raspberry Pi ───────────────────────────────────────
# On Pi Wayland the GStreamer GL sink needs to know which EGL platform to use.
# Without this the video pipeline can negotiate successfully but output a blank
# (all-black) frame to the VideoOutput surface.
if [ "${QT_QPA_PLATFORM}" = "wayland" ]; then
    export GST_GL_WINDOW="${GST_GL_WINDOW:-wayland}"
    export GST_GL_PLATFORM="${GST_GL_PLATFORM:-egl}"
fi

export PYTHONUNBUFFERED=1

exec "${PYTHON}" -m app.main "$@"
