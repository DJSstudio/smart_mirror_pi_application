#!/usr/bin/env python3
"""pi_smoke_test.py — on-device validation for the integration/all-fixes branch.

The whole-codebase audit flagged several camera/display issues that CANNOT be
verified on a dev machine (no PySide6, no camera, no second screen). This script
exercises the *real* app code on the Pi and checks each of them:

  Camera capture (drives the app's actual QtCameraSession):
    * recording isn't garbled / sheared      → raw-frame STRIDE finding
    * recorded duration matches wall time     → wallclock-PTS finding
    * requested resolution/fps honored        → format-selection finding
    * camera opened AND delivered frames       → silent-QCamera-error finding
    * extracted frames aren't black            → silent-failure finding
  Playback:
    * QMediaPlayer can decode the clip        → QT_MEDIA_BACKEND=ffmpeg flip
  Display:
    * screen count / geometry, two-screen present
  Data layer:
    * DB init + transaction + WAL checkpoint, atomic settings write — run on
      the Pi's own Python/sqlite

It writes the recorded clip + a few extracted frames to an output dir so you
can EYEBALL them — a sheared/garbled frame is the signature of the stride bug
and only a human can reliably spot it.

Run on the Pi in the app's Qt environment:

    source venv/bin/activate                 # the app's venv
    QT_MEDIA_BACKEND=ffmpeg python3 scripts/pi_smoke_test.py
    # scripts/run_dev.sh already exports QT_MEDIA_BACKEND=ffmpeg

Over SSH with no display, camera+playback still work via offscreen:
    QT_QPA_PLATFORM=offscreen QT_MEDIA_BACKEND=ffmpeg python3 scripts/pi_smoke_test.py
    # (the display/screen check is only meaningful in the real graphical session)

Options:
    --seconds N        record length (default 6)
    --width/--height/--fps   requested capture format (default 1280x720@30)
    --device HINT      camera device hint (default: auto)
    --out DIR          where to write clip + frames (default: ./pi_smoke_out)
    --no-keep          delete the output dir on exit
    --skip-camera / --skip-playback / --skip-display / --skip-db
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# (status, name, detail) — status in {PASS, WARN, FAIL, INFO}
RESULTS: list[tuple[str, str, str]] = []


def _log(status: str, name: str, detail: str = "") -> None:
    RESULTS.append((status, name, detail))
    line = f"[{status:4}] {name}"
    if detail:
        line += f" — {detail}"
    print(line, flush=True)


def _header(title: str) -> None:
    print(f"\n{'=' * 64}\n  {title}\n{'=' * 64}", flush=True)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# ffprobe / ffmpeg helpers
# ---------------------------------------------------------------------------

def _ffprobe(path: Path) -> dict:
    out = _run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ])
    try:
        return json.loads(out.stdout)
    except Exception:  # noqa: BLE001
        return {}


def _avg_luma(path: Path, frame_n: int = 15) -> float | None:
    """Average luma (YAVG) of one decoded frame. ~16 == black (limited range)."""
    out = _run([
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-vf", f"select=eq(n\\,{frame_n}),signalstats,metadata=print",
        "-frames:v", "1", "-an", "-f", "null", "-",
    ])
    m = re.search(r"YAVG=([\d.]+)", out.stderr)
    return float(m.group(1)) if m else None


def _extract_frames(path: Path, outdir: Path, count: int = 3) -> list[Path]:
    pattern = str(outdir / "frame_%02d.jpg")
    _run([
        "ffmpeg", "-hide_banner", "-y", "-i", str(path),
        "-vf", "fps=1", "-frames:v", str(count), "-q:v", "3", pattern,
    ])
    return sorted(outdir.glob("frame_*.jpg"))


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_env() -> bool:
    _header("Environment")
    ok = True
    for binary in ("ffmpeg", "ffprobe"):
        path = shutil.which(binary)
        _log("PASS" if path else "FAIL", f"{binary} present", path or "NOT FOUND")
        ok = ok and bool(path)
    _log("INFO", "rpicam-vid present", shutil.which("rpicam-vid") or "(absent — fine for USB-only)")
    _log("INFO", "QT_MEDIA_BACKEND", os.environ.get("QT_MEDIA_BACKEND", "(default — should be 'ffmpeg')"))
    _log("INFO", "QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "(default)"))
    try:
        import PySide6  # noqa: PLC0415
        _log("PASS", "PySide6 import", getattr(PySide6, "__version__", "?"))
    except Exception as exc:  # noqa: BLE001
        _log("FAIL", "PySide6 import", str(exc))
        return False
    try:
        from PySide6.QtMultimedia import QMediaPlayer  # noqa: F401,PLC0415
        _log("PASS", "QtMultimedia import", "")
    except Exception as exc:  # noqa: BLE001
        _log("FAIL", "QtMultimedia import", str(exc))
        ok = False
    try:
        free_mb = shutil.disk_usage(REPO).free // (1024 * 1024)
        _log("PASS" if free_mb > 500 else "WARN", "disk free", f"{free_mb} MB")
    except OSError as exc:
        _log("WARN", "disk free", str(exc))
    return ok


def check_display(app) -> None:
    _header("Display / screens")
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        _log("INFO", "display check", "running offscreen — screen list is not the real hardware")
    screens = app.screens()
    _log("INFO", "screens detected", str(len(screens)))
    for i, s in enumerate(screens):
        g = s.geometry()
        _log("INFO", f"screen[{i}]",
             f"{s.name()}  {g.width()}x{g.height()} @({g.x()},{g.y()})  {s.devicePixelRatio():.1f}x")
    if len(screens) < 2:
        _log("WARN", "two-screen layout",
             "only 1 screen — kiosk needs control + mirror; in single-screen mode the "
             "mirror window currently covers the control UI (audit finding)")
    else:
        _log("PASS", "two-screen layout", f"{len(screens)} screens present")


def test_camera(app, args, outdir: Path):
    _header("Camera capture pipeline")
    from PySide6.QtCore import QTimer  # noqa: PLC0415
    from PySide6.QtMultimedia import QMediaDevices  # noqa: PLC0415
    from app.services.qt_camera_session import QtCameraSession  # noqa: PLC0415

    cams = QMediaDevices.videoInputs()
    if not cams:
        _log("FAIL", "camera enumeration", "Qt sees NO cameras (QMediaDevices.videoInputs() empty)")
        return None
    _log("PASS", "camera enumeration", f"{len(cams)} camera(s)")
    dev = cams[0]
    fmts = dev.videoFormats()
    has_mjpeg = any("jpeg" in f.pixelFormat().name.lower() for f in fmts)
    _log("INFO", "camera", dev.description())
    _log("INFO" if has_mjpeg else "WARN", "capture code path",
         "MJPEG available → passthrough path"
         if has_mjpeg else
         "NO MJPEG → RAW path (the stride finding applies — EYEBALL frames closely)")

    session = QtCameraSession()
    session.prime_devices()
    clip = outdir / "smoke_clip.mp4"
    err: dict[str, str] = {}
    try:
        session.start_recording(
            device_hint=args.device or None,
            width=args.width, height=args.height, fps=args.fps,
            bitrate=8_000_000, output_path=clip,
        )
    except Exception as exc:  # noqa: BLE001
        _log("FAIL", "start_recording", str(exc))
        return None

    def _finish() -> None:
        try:
            session.stop()
        except Exception as exc:  # noqa: BLE001
            err["stop"] = str(exc)
        app.quit()

    print(f"  recording ~{args.seconds}s … wave at the camera", flush=True)
    QTimer.singleShot(int(args.seconds * 1000), _finish)
    app.exec()
    if err.get("stop"):
        _log("WARN", "session.stop()", err["stop"])

    if not clip.exists() or clip.stat().st_size < 1024:
        _log("FAIL", "recording produced a file",
             "missing or <1KB — camera likely opened but delivered no frames "
             "(silent QCamera failure)")
        return None
    _log("PASS", "recording produced a file", f"{clip.stat().st_size // 1024} KB → {clip}")

    info = _ffprobe(clip)
    streams = info.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if vstream is None:
        _log("FAIL", "recording is a valid video", "ffprobe found no video stream")
        return clip

    # Duration — the wallclock-PTS finding: should be roughly the wall time we
    # recorded (minus camera warm-up). Wildly off (≈0, or >>seconds) = PTS bug.
    try:
        dur = float(info.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        dur = 0.0
    lo, hi = args.seconds * 0.3, args.seconds * 1.8
    if dur <= 0.5:
        _log("FAIL", "recorded duration", f"{dur:.2f}s — no real content / PTS broken")
    elif lo <= dur <= hi:
        _log("PASS", "recorded duration", f"{dur:.2f}s (recorded ~{args.seconds}s)")
    else:
        _log("WARN", "recorded duration",
             f"{dur:.2f}s vs ~{args.seconds}s requested — suspect wallclock-PTS handling")

    # Resolution — the format-selection finding.
    w, h = vstream.get("width"), vstream.get("height")
    if (w, h) == (args.width, args.height):
        _log("PASS", "recorded resolution", f"{w}x{h} (matches request)")
    else:
        _log("WARN", "recorded resolution",
             f"{w}x{h} but requested {args.width}x{args.height} — format selection picked closest")
    afr = vstream.get("avg_frame_rate", "0/0")
    try:
        num, den = afr.split("/")
        fps_val = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps_val = 0.0
    note = "" if abs(fps_val - args.fps) <= 5 else f" (requested {args.fps} — fps setting may be ignored)"
    _log("INFO", "recorded fps", f"{fps_val:.1f}{note}")

    # Black / no-content check (silent-failure finding).
    luma = _avg_luma(clip)
    if luma is None:
        _log("WARN", "frame content (luma)", "could not measure")
    elif luma < 18.0:
        _log("FAIL", "frame content (luma)", f"YAVG={luma:.1f} — frames look BLACK (camera delivered nothing useful)")
    else:
        _log("PASS", "frame content (luma)", f"YAVG={luma:.1f} (not black)")

    frames = _extract_frames(clip, outdir)
    if frames:
        tiny = all(f.stat().st_size < 2048 for f in frames)
        _log("WARN" if tiny else "PASS", "extracted frames",
             f"{len(frames)} written to {outdir} — OPEN THEM: clean image, or sheared/garbled/wrong-colors?")
    else:
        _log("WARN", "extracted frames", "ffmpeg could not extract frames")
    return clip


def test_playback(app, clip: Path) -> None:
    _header("Playback (QMediaPlayer / QT_MEDIA_BACKEND)")
    from PySide6.QtCore import QTimer, QUrl  # noqa: PLC0415
    from PySide6.QtMultimedia import QMediaPlayer, QVideoSink  # noqa: PLC0415

    player = QMediaPlayer()
    sink = QVideoSink()
    player.setVideoSink(sink)
    state = {"frames": 0, "status": "", "err": ""}
    sink.videoFrameChanged.connect(lambda _f: state.__setitem__("frames", state["frames"] + 1))
    player.mediaStatusChanged.connect(lambda s: state.__setitem__("status", str(s)))
    player.errorOccurred.connect(lambda _e, m: state.__setitem__("err", m))
    player.setSource(QUrl.fromLocalFile(str(clip)))
    player.play()
    QTimer.singleShot(3000, app.quit)
    app.exec()
    try:
        player.stop()
    except Exception:  # noqa: BLE001
        pass
    if state["err"]:
        _log("FAIL", "QMediaPlayer decode", state["err"])
    elif state["frames"] > 0:
        _log("PASS", "QMediaPlayer decode", f"{state['frames']} frames decoded (ffmpeg backend OK)")
    else:
        _log("WARN", "QMediaPlayer decode", f"0 frames decoded; status={state['status']}")


def test_db(outdir: Path) -> None:
    _header("Data layer (DB + settings)")
    from app.database.connection import DatabaseManager  # noqa: PLC0415
    from app.services.settings_service import SettingsService  # noqa: PLC0415

    try:
        db = DatabaseManager(outdir / "smoke.db")
        db.initialize()
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO sessions (id,name,started_at,active,device_id) "
                "VALUES ('x','smoke','2026-01-01T00:00:00+00:00',0,'')"
            )
            conn.commit()
        n = db.connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        db.checkpoint()
        db.close()
        _log("PASS" if n == 1 else "FAIL", "DB init/transaction/checkpoint", f"{n} row")
    except Exception as exc:  # noqa: BLE001
        _log("FAIL", "DB init/transaction/checkpoint", str(exc))

    try:
        cfg = outdir / "settings.json"
        paths_stub = type("P", (), {"config_path": cfg})()
        s = SettingsService(paths_stub)
        s.set("camera_width", 1920)
        reloaded = SettingsService(paths_stub).get("camera_width")
        no_tmp = not (outdir / "settings.json.tmp").exists()
        _log("PASS" if reloaded == 1920 and no_tmp else "FAIL",
             "settings atomic write", f"reloaded={reloaded}, no .tmp left={no_tmp}")
    except Exception as exc:  # noqa: BLE001
        _log("FAIL", "settings atomic write", str(exc))


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="On-Pi smoke test for integration/all-fixes")
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--device", default="")
    ap.add_argument("--out", default=str(REPO / "pi_smoke_out"))
    ap.add_argument("--keep", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--skip-camera", action="store_true")
    ap.add_argument("--skip-playback", action="store_true")
    ap.add_argument("--skip-display", action="store_true")
    ap.add_argument("--skip-db", action="store_true")
    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    env_ok = check_env()
    clip = None
    app = None
    if env_ok and not (args.skip_camera and args.skip_playback and args.skip_display):
        from PySide6.QtGui import QGuiApplication  # noqa: PLC0415
        app = QGuiApplication(sys.argv[:1])

    if app is not None and not args.skip_display:
        check_display(app)
    if app is not None and not args.skip_camera:
        clip = test_camera(app, args, outdir)
    if app is not None and not args.skip_playback:
        if clip is not None:
            test_playback(app, clip)
        else:
            _log("INFO", "playback", "skipped — no clip was recorded")
    if not args.skip_db:
        test_db(outdir)

    # Summary
    _header("SUMMARY")
    counts = Counter(s for s, _, _ in RESULTS)
    for status, name, detail in RESULTS:
        if status in ("FAIL", "WARN"):
            print(f"  {status}: {name}" + (f" — {detail}" if detail else ""))
    print(f"\n  PASS={counts['PASS']}  WARN={counts['WARN']}  FAIL={counts['FAIL']}  INFO={counts['INFO']}")

    print("\n  MANUAL CHECKS automation can't do — please verify by hand:")
    print(f"   1. Open {outdir}/frame_*.jpg — is the image CLEAN, or sheared/")
    print("      diagonally-skewed/wrong-colors? (raw-frame stride bug)")
    print("   2. On the kiosk: mirror content on the MIRROR screen, UI on the")
    print("      control screen? (Wayland window placement)")
    print("   3. Portrait mirror (orientation 90/270): does recorded VIDEO play")
    print("      upright on the mirror, or sideways? (orientation-not-applied bug)")
    print("   4. Power-cycle the mirror TV while the app runs — does the mirror")
    print("      window return to it? (HDMI hotplug)")
    print("   5. Live Compare: record, then tap the back arrow / a nav item —")
    print("      is the clip SAVED to the gallery (not lost)? (navigate-away fix)")

    if not args.keep:
        shutil.rmtree(outdir, ignore_errors=True)
    else:
        print(f"\n  Artifacts kept in: {outdir}")

    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
