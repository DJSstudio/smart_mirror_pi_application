#!/usr/bin/env python3
"""Standalone QCamera test — verifies the architecture before we rewrite.

Opens the USB camera using Qt's native QCamera + QMediaCaptureSession,
displays it fullscreen with QVideoOutput.  No ffmpeg, no UDP, no MPEGTS.

If this preview is smooth and responsive (laptop-quality), we have green
light to rewrite the USB camera path to use this architecture.

Run:
    bash scripts/run_dev.sh   # or just to set Qt env, then:
    python3 scripts/test_qcamera.py

Press Esc or close the window to quit.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


def main() -> int:
    app = QApplication(sys.argv)

    cameras = QMediaDevices.videoInputs()
    if not cameras:
        print("ERROR: No cameras detected by QMediaDevices.", file=sys.stderr)
        print("Make sure the USB camera is plugged in and accessible at /dev/video*",
              file=sys.stderr)
        return 1

    print(f"Found {len(cameras)} camera(s):")
    for i, dev in enumerate(cameras):
        print(f"  [{i}] {dev.description()}  id={dev.id().data().decode(errors='replace')}")
        for fmt in dev.videoFormats():
            print(f"        {fmt.resolution().width()}x{fmt.resolution().height()} "
                  f"@ {fmt.maxFrameRate():.0f}fps  pixel={fmt.pixelFormat().name}")

    selected = cameras[0]
    print(f"\nUsing: {selected.description()}")

    window = QWidget()
    window.setWindowTitle("QCamera test")

    label = QLabel(f"Camera: {selected.description()}\n"
                   "Wave at the camera — does the preview feel real-time?\n"
                   "Esc to quit.")
    label.setStyleSheet("color: white; background: #222; padding: 10px; font-size: 14px;")

    video = QVideoWidget()

    layout = QVBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(label)
    layout.addWidget(video, stretch=1)

    capture = QMediaCaptureSession()
    camera = QCamera(selected)
    capture.setCamera(camera)
    capture.setVideoOutput(video)
    camera.start()

    def keypress(event):
        if event.key() == Qt.Key.Key_Escape:
            app.quit()

    window.keyPressEvent = keypress
    window.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
