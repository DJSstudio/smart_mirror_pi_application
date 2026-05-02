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

# ── Qt Multimedia backend ──────────────────────────────────────────────────
# Qt 6.5+ defaults to the bundled FFmpeg backend, which logs
# "No HW decoder found" on Pi and then stalls (no V4L2M2M/VAAPI support
# for our libx264 stream).  Force GStreamer instead — it has proper Pi
# support and the plugins are already installed on Trixie.
export QT_MEDIA_BACKEND="${QT_MEDIA_BACKEND:-gstreamer}"

# ── GStreamer hints for Raspberry Pi ───────────────────────────────────────
if [ "${QT_QPA_PLATFORM}" = "wayland" ]; then
    export GST_GL_WINDOW="${GST_GL_WINDOW:-wayland}"
    export GST_GL_PLATFORM="${GST_GL_PLATFORM:-egl}"
fi

# ── H.264 decoder selection ───────────────────────────────────────────────
# Pi 4: prefer hardware decoder (v4l2h264dec) — handles 1080p@30 with near-
#       zero CPU. Crashes only on all-I-frame zerolatency streams; we use
#       normal GOP so it's safe.
# Pi 5: no V4L2M2M H.264 decoder hardware; GStreamer falls back to
#       avdec_h264 (software). The Pi 5 CPU handles this comfortably.
# Other (dev machines): leave defaults — usually have hardware accel.
PI_MODEL="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || echo '')"
if [ -z "${GST_PLUGIN_FEATURE_RANK:-}" ]; then
    case "${PI_MODEL}" in
        *"Raspberry Pi 4"*)
            export GST_PLUGIN_FEATURE_RANK="v4l2h264dec:512,avdec_h264:256"
            echo "Detected Pi 4 — using hardware H.264 decoder"
            ;;
        *"Raspberry Pi 5"*)
            echo "Detected Pi 5 — using software H.264 decoder (no V4L2M2M on Pi 5)"
            ;;
        *)
            echo "Non-Pi platform (${PI_MODEL:-unknown}) — using GStreamer defaults"
            ;;
    esac
fi

export PYTHONUNBUFFERED=1

# ── Touch device (eglfs only) ──────────────────────────────────────────────
# On eglfs (no display server) Qt reads touch from the device specified in
# QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS.  Auto-detect the first touch-capable
# input device so the touchscreen always maps to the control window.
if [ "${QT_QPA_PLATFORM}" = "eglfs" ] && [ -z "${QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS:-}" ]; then
    for sysfs_name in /sys/class/input/event*/device/name; do
        dev_name="$(cat "${sysfs_name}" 2>/dev/null || true)"
        case "$(echo "${dev_name}" | tr '[:upper:]' '[:lower:]')" in
            *touch*|*goodix*|*ft5*|*waveshare*|*eeti*|*ilitek*)
                event_node="$(basename "$(dirname "$(dirname "${sysfs_name}")")")"
                export QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS="/dev/input/${event_node}"
                echo "Touch device: /dev/input/${event_node} (${dev_name})"
                break
                ;;
        esac
    done
fi

exec "${PYTHON}" -m app.main "$@"
