#!/usr/bin/env bash
# setup_loopback.sh — ensure the /dev/video10 v4l2loopback "MirrorPreview" device
# exists and is pinned to the app's configured camera resolution.
#
# The Pi CSI low-latency preview reads the camera through /dev/video10; the
# device format MUST match the app's camera_width/height/fps or Qt segfaults on
# a size mismatch.  This makes that setup automatic, so launching only needs
# run_dev.sh / run.sh — no manual modprobe / set-caps.
#
# Idempotent and safe to run before every launch: it skips work already done
# (so no needless sudo prompt) and exits 0 (non-fatal) if v4l2loopback isn't
# available — the app then falls back to the (laggy) UDP MPEG-TS path.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEV=/dev/video10

if ! command -v v4l2loopback-ctl >/dev/null 2>&1; then
    echo "  [loopback] v4l2loopback-ctl not found — skipping (app uses UDP fallback)"
    exit 0
fi

# Target resolution/fps from the app config (fallback to 2K@30 if unreadable).
PY="${REPO_ROOT}/venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3 || true)"
DIMS="$("$PY" -c "import json;d=json.load(open('${REPO_ROOT}/config/settings.json'));print(d.get('camera_width',2560),d.get('camera_height',1440),d.get('camera_fps',30))" 2>/dev/null || echo '2560 1440 30')"
read -r W H FPS <<< "$DIMS"

run_root() { if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi; }

# 1) Load the module if the device node is missing (needs root).
if [ ! -e "$DEV" ]; then
    echo "  [loopback] loading v4l2loopback → ${DEV}"
    run_root modprobe -r v4l2loopback 2>/dev/null || true
    if ! run_root modprobe v4l2loopback video_nr=10 card_label=MirrorPreview exclusive_caps=0; then
        echo "  [loopback] could not load module — app uses UDP fallback"
        exit 0
    fi
fi

# 2) Pin the format to the app config — but only if it isn't already, so repeat
#    launches don't trigger a needless sudo prompt.
CUR="$(v4l2-ctl -d "$DEV" --get-fmt-video 2>/dev/null | grep -oE '[0-9]+/[0-9]+' | head -1 || true)"
if [ "$CUR" = "${W}/${H}" ]; then
    echo "  [loopback] ${DEV} already ${W}x${H}"
    exit 0
fi

CAPS="YU12:${W}x${H}@${FPS}/1"
# Try without sudo first (works if the user is in the 'video' group), else sudo.
if v4l2loopback-ctl set-caps "$DEV" "$CAPS" 2>/dev/null \
   || run_root v4l2loopback-ctl set-caps "$DEV" "$CAPS"; then
    echo "  [loopback] pinned ${DEV} = ${CAPS}"
else
    echo "  [loopback] WARNING: could not pin ${DEV}; app uses UDP fallback"
fi
exit 0
