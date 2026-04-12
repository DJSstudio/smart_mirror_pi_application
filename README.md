# Smart Mirror Pi

Debian-first Raspberry Pi smart mirror application built from scratch with `PySide6 + QML`, local Python services, and SQLite. The current repository does not reuse the old Android-migrated Linux code; it only mirrors the product behavior and UI intent from the reference repos.

## What this app does

- Runs two persistent top-level windows:
  - `ControlWindow` on Display 1 for all interaction
  - `MirrorWindow` on Display 2 as fullscreen output-only surface
- Keeps the mirror black by default
- Activates the mirror only for:
  - recording preview
  - video playback
  - compare
  - live compare
- Returns the mirror to black after those workflows end
- Stores sessions and recorded looks in local SQLite

## Repository layout

- `app/`: Python application code, QML, services, controllers, platform adapters
- `config/`: default JSON configuration
- `systemd/`: systemd service unit
- `scripts/`: install, run, and autostart helpers

## Runtime dependencies

Install Python dependencies with:

```bash
python3 -m pip install -r requirements.txt
```

Install Pi system packages with:

```bash
./scripts/install_pi_dependencies.sh
```

You also need the Raspberry Pi camera userspace that provides `rpicam-vid` if you want CSI camera support. USB webcam fallback uses `/dev/video*` through `ffmpeg`.

## Running locally

```bash
./scripts/run_dev.sh
```

The app stores data under:

- `~/.local/share/smart-mirror-pi/data/videos`
- `~/.local/share/smart-mirror-pi/data/thumbnails`
- `~/.local/share/smart-mirror-pi/data/smart_mirror.sqlite3`
- `~/.local/share/smart-mirror-pi/logs/smart_mirror.log`

## Screen assignment

Default config lives in [`config/smart_mirror.json`](config/smart_mirror.json).

Key settings:

- `control_screen_index`
- `mirror_screen_index`
- `camera_backend`
- `camera_device`
- `mirror_orientation_degrees`
- `compare_fill_crop`

User overrides are written to `~/.config/smart-mirror-pi/config.json` from the Settings page.

## Camera architecture

- `RaspberryPiCameraAdapter`
  - uses `rpicam-vid`
  - streams low-latency H.264 preview to local UDP ports
  - records H.264, then remuxes to MP4 for review/save
- `UsbCameraAdapter`
  - uses `ffmpeg` and `v4l2`
  - previews to UDP and records directly to MP4

The control window and mirror window use separate preview URLs, so live preview, record preview, and live compare stay split cleanly across the two screens.

## Mirror state model

- Boot: idle black
- Home/dashboard: idle black
- Start recording: active
- Stop recording: idle black
- Open playback: active
- Close playback: idle black
- Open compare: active
- Close compare: idle black
- Open live compare: active
- Close live compare: idle black

The mirror window is never destroyed during runtime. It stays resident and only changes render mode.

## Autostart on boot

Review [`systemd/smart-mirror.service`](systemd/smart-mirror.service), then install it:

```bash
./scripts/setup_autostart.sh
```

Before enabling:

1. Set the correct service `User=` if your Pi user is not `pi`.
2. Make sure the repo lives at the final target path.
3. Create the virtualenv and install `requirements.txt`.

## Notes

- The QML shell is production-oriented but still expects the Pi to have a working graphical session and Qt Multimedia backend.
- If only one screen is connected, the app will still run, but control and mirror will land on the same display.
- `mpv` is listed as a dependency for field debugging and optional fallback workflows, though the current implementation uses Qt Multimedia for playback surfaces.
