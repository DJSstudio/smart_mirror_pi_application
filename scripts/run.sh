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

# ── H.264 decoder selection ───────────────────────────────────────────────
# Pi 4: prefer hardware decoder (v4l2h264dec). Pi 5: no V4L2M2M H.264 decoder
# hardware — fall back to software (avdec_h264), which the Pi 5 CPU handles.
PI_MODEL="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || echo '')"
if [ -z "${GST_PLUGIN_FEATURE_RANK:-}" ]; then
    case "${PI_MODEL}" in
        *"Raspberry Pi 4"*)
            export GST_PLUGIN_FEATURE_RANK="v4l2h264dec:512,avdec_h264:256"
            ;;
    esac
fi

export PYTHONUNBUFFERED=1

exec "${PYTHON}" -m app.main "$@"
