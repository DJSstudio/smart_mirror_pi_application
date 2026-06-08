#!/usr/bin/env python3
"""camera_doctor.py — diagnose USB-camera capture, independently of the app.

The app captures through Qt's QCamera + QMediaCaptureSession (GStreamer backend).
When that fails ("camerabin ... FAILURE PLAYING") it's hard to tell whether the
problem is the camera, a specific pixel format (MJPEG vs raw YUYV), or the
Qt/GStreamer install on this Pi.

This script reproduces the app's exact capture path with NO widgets and NO
display, and reports — per format strategy — whether the camera reaches Active
and actually delivers frames. It needs only PySide6.QtMultimedia (which the app
already uses), NOT QtMultimediaWidgets (which scripts/test_qcamera.py needed and
which isn't installed on the Pi).

Run on the Pi, matching the app's Qt environment:

    QT_MEDIA_BACKEND=gstreamer QT_QPA_PLATFORM=offscreen \\
        python3 scripts/camera_doctor.py

Notes:
  * If 'offscreen' misbehaves, drop it and run on the Pi's display session.
  * Pass a device index to test a specific camera:  python3 scripts/camera_doctor.py 1
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import (
    QCamera,
    QMediaCaptureSession,
    QMediaDevices,
    QVideoSink,
)

TEST_SECONDS = 3


def _is_mjpeg(fmt) -> bool:
    return "jpeg" in fmt.pixelFormat().name.lower()


def _label(fmt) -> str:
    r = fmt.resolution()
    return f"{r.width()}x{r.height()}@{fmt.maxFrameRate():.0f} {fmt.pixelFormat().name}"


def _run_loop(app, ms: int) -> None:
    """Spin the Qt event loop for *ms* milliseconds, then return."""
    QTimer.singleShot(ms, app.quit)
    app.exec()


def _try_strategy(app, device, fmt, title: str) -> bool:
    print(f"\n--- {title} ---")
    cam = QCamera(device)
    session = QMediaCaptureSession()
    sink = QVideoSink()
    stats = {"frames": 0, "first": "", "error": ""}

    def on_frame(frame):
        stats["frames"] += 1
        if not stats["first"] and frame.isValid():
            stats["first"] = f"{frame.width()}x{frame.height()} {frame.pixelFormat().name}"

    def on_error(err, msg):
        stats["error"] = f"{err} {msg}".strip()

    sink.videoFrameChanged.connect(on_frame)
    cam.errorOccurred.connect(on_error)
    session.setCamera(cam)
    session.setVideoSink(sink)

    if fmt is not None:
        cam.setCameraFormat(fmt)
        print(f"  forcing format : {_label(fmt)}")
    else:
        print("  format         : camera DEFAULT (no setCameraFormat — like test_qcamera.py)")

    cam.start()
    _run_loop(app, TEST_SECONDS * 1000)
    active = cam.isActive()
    cam.stop()
    session.setCamera(None)
    for obj in (cam, session, sink):
        obj.deleteLater()
    _run_loop(app, 400)  # let the device release before the next test

    ok = active and stats["frames"] > 0
    print(f"  active={active}  frames={stats['frames']}  "
          f"first_frame={stats['first'] or '(none)'}")
    print(f"  error={stats['error'] or '(none)'}")
    print(f"  => {'WORKS' if ok else 'FAILS'}")
    return ok


def main() -> int:
    # Strip our own arg so QGuiApplication doesn't try to parse it.
    idx = 0
    argv = list(sys.argv)
    if len(argv) > 1 and argv[1].isdigit():
        idx = int(argv.pop(1))

    app = QGuiApplication(argv)
    print(f"Qt media backend : {os.environ.get('QT_MEDIA_BACKEND', '(default)')}")
    print(f"Qt platform      : {os.environ.get('QT_QPA_PLATFORM', '(default)')}")

    cams = QMediaDevices.videoInputs()
    if not cams:
        print("\nERROR: Qt sees NO cameras (QMediaDevices.videoInputs() is empty).")
        print("  => The camera/driver isn't visible to Qt at all — not a format issue.")
        print("     Check `v4l2-ctl --list-devices` and that the USB cam is plugged in.")
        return 1

    if idx >= len(cams):
        print(f"\nERROR: requested camera index {idx} but only {len(cams)} found.")
        return 1

    device = cams[idx]
    print(f"\nCamera [{idx}]: {device.description()}")
    fmts = device.videoFormats()
    print(f"Advertised formats ({len(fmts)}):")
    for f in fmts:
        print(f"  {_label(f)}")

    raw = [f for f in fmts if not _is_mjpeg(f)]
    mj = [f for f in fmts if _is_mjpeg(f)]

    def biggest(lst):
        return max(lst, key=lambda f: f.resolution().width() * f.resolution().height())

    results: dict[str, bool] = {}
    results["default"] = _try_strategy(app, device, None, "DEFAULT format (camera's choice)")
    if raw:
        results["raw/YUYV"] = _try_strategy(app, device, biggest(raw), "RAW / YUYV (largest)")
    if mj:
        results["MJPEG"] = _try_strategy(app, device, biggest(mj), "MJPEG (largest)")

    print("\n==================== SUMMARY ====================")
    for k, v in results.items():
        print(f"  {k:12}: {'WORKS' if v else 'FAILS'}")
    print("=================================================")

    raw_ok = results.get("raw/YUYV")
    mj_ok = results.get("MJPEG")
    if not any(results.values()):
        print("DIAGNOSIS: Qt can't start ANY format → the Qt/GStreamer camera stack on")
        print("  this Pi is broken (environment issue — matches 'old commits fail too').")
        print("  Try: sudo apt install --reinstall gstreamer1.0-plugins-good "
              "gstreamer1.0-plugins-bad gstreamer1.0-libav python3-pyside6.qtmultimedia")
        print("  Meanwhile use the ffmpeg backend:  camera_backend = usb_ffmpeg")
    elif raw_ok and mj_ok is False:
        print("DIAGNOSIS: RAW works, MJPEG fails → the app's MJPEG selection is the problem.")
        print("  Fix: force YUYV in the QCamera path (camera_pixel_format=raw), or use")
        print("  camera_backend=usb_ffmpeg for full-res MJPEG via ffmpeg.")
    elif mj_ok:
        print("DIAGNOSIS: MJPEG works here in isolation → the failure is app-specific")
        print("  (sink wiring / timing), not the camera, format, or environment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
