#!/usr/bin/env bash
# run.sh — Production launcher for Smart Mirror Pi.
#
# Called by systemd/smart-mirror.service.  Sets up the display environment,
# picks the correct Qt platform backend, and exec's the app.
#
# Do NOT add --dev flags or debug overrides here.  Use run_dev.sh for that.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

# ── Python interpreter ────────────────────────────────────────────────────
# Prefer the project venv; fall back to system python3.
if [ -x "${REPO_ROOT}/venv/bin/python" ]; then
    PYTHON="${REPO_ROOT}/venv/bin/python"
else
    PYTHON="$(command -v python3)"
fi

# ── Qt platform ───────────────────────────────────────────────────────────
# Honour an explicit override (e.g. from the systemd unit's Environment=).
# Otherwise probe the available display servers in priority order.
if [ -z "${QT_QPA_PLATFORM:-}" ]; then
    if [ -n "${WAYLAND_DISPLAY:-}" ]; then
        export QT_QPA_PLATFORM="wayland"
    elif [ -n "${DISPLAY:-}" ]; then
        export QT_QPA_PLATFORM="xcb"
    else
        # Headless Pi (no Wayland/X11) — use eglfs for direct framebuffer.
        export QT_QPA_PLATFORM="eglfs"
        export QT_QPA_EGLFS_ALWAYS_SET_MODE=1
    fi
fi

# ── Qt Multimedia backend ─────────────────────────────────────────────────
# Force GStreamer; the bundled FFmpeg backend stalls on Pi hardware.
export QT_MEDIA_BACKEND="${QT_MEDIA_BACKEND:-gstreamer}"

# ── GStreamer GL hints (Wayland only) ─────────────────────────────────────
if [ "${QT_QPA_PLATFORM}" = "wayland" ]; then
    export GST_GL_WINDOW="${GST_GL_WINDOW:-wayland}"
    export GST_GL_PLATFORM="${GST_GL_PLATFORM:-egl}"
fi

# Prefer software H264 decoder over the Pi V4L2M2M path which crashes on
# -tune zerolatency streams.
export GST_PLUGIN_FEATURE_RANK="${GST_PLUGIN_FEATURE_RANK:-avdec_h264:256,v4l2h264dec:50}"

export PYTHONUNBUFFERED=1

exec "${PYTHON}" -m app.main "$@"
