# Smart Mirror Pi

A production-grade Debian-native smart mirror application for Raspberry Pi.  
Built with PySide6 + QML, SQLite, ffmpeg, and rpicam-vid.

---

## Architecture overview

```
smart_mirror_pi/
├── app/
│   ├── main.py                  ← Entry point
│   ├── config/                  ← Paths, logging, settings schema
│   ├── models/                  ← Data entities (dataclasses)
│   ├── database/                ← SQLite connection + repositories
│   ├── services/                ← Core domain services
│   │   ├── camera_service.py
│   │   ├── recording_service.py
│   │   ├── mirror_display_service.py   ← Mirror state machine
│   │   ├── playback_service.py
│   │   ├── gallery_service.py
│   │   ├── session_service.py
│   │   ├── settings_service.py
│   │   └── screen_manager.py
│   ├── controllers/             ← QML-facing Python controllers
│   ├── platform/                ← Camera adapters (Pi CSI, USB)
│   ├── media/                   ← ffmpeg/ffprobe wrappers
│   └── qml/
│       ├── ControlWindow.qml    ← Display 1 (controls + navigation)
│       ├── MirrorWindow.qml     ← Display 2 (always exists, defaults black)
│       ├── components/          ← Reusable QML components
│       └── pages/               ← Individual page views
├── config/
│   └── settings.json            ← Persistent settings
├── data/                        ← Created at runtime
│   ├── videos/
│   ├── thumbnails/
│   ├── temp/
│   ├── logs/
│   └── smart_mirror.db
├── systemd/
│   └── smart-mirror.service     ← systemd user service
├── scripts/
│   ├── install_deps.sh          ← One-shot dependency installer
│   ├── setup_autostart.sh       ← Enable systemd service
│   ├── run.sh                   ← Production launcher (called by systemd)
│   └── run_dev.sh               ← Development launch helper
├── requirements.txt
├── requirements.lock            ← Pinned versions for reproducible Pi installs
└── .env.example                 ← Shell-level environment variable reference
```

---

## Two-screen model

| Display   | Window          | Default state  | Activates when…                    |
|-----------|-----------------|----------------|------------------------------------|
| Display 1 | ControlWindow   | Always visible | Boot                               |
| Display 2 | MirrorWindow    | Pure black     | Recording / playback / compare starts |

The MirrorWindow **never** closes or re-opens; it transitions between idle (black) and active states via `MirrorDisplayService`.

### Mirror states

| State          | Trigger                        |
|----------------|--------------------------------|
| `idle`         | Boot, after any feature ends   |
| `live_preview` | Recording starts               |
| `video`        | Video playback opens           |
| `compare`      | Compare workflow opens         |
| `live_compare` | Live compare workflow opens    |
| `test_pattern` | Settings → Test Mirror         |

---

## Raspberry Pi setup

### 1. Flash Raspberry Pi OS (Bookworm 64-bit)

Use Raspberry Pi Imager.  Enable SSH, set hostname, Wi-Fi, user `pi`.

### 2. Clone the repo

```bash
cd ~
git clone <your-repo-url> smart_mirror_pi
cd smart_mirror_pi
```

### 3. Install system dependencies

```bash
chmod +x scripts/install_deps.sh
./scripts/install_deps.sh
```

This installs: ffmpeg, rpicam-apps, Qt6 multimedia libs, Noto fonts, v4l-utils, and creates a Python venv.

### 4. Run once to verify

```bash
chmod +x scripts/run_dev.sh
./scripts/run_dev.sh
```

Two windows will appear.  If you only have one screen, both are placed on it (mirror stays black below the UI).

### 5. Configure screens

Open **Settings → Screens** in the UI and set:
- Control screen index: the index of your touch/control display
- Mirror screen index: the index of the mirror/secondary display

Then press **Apply Screen Assignment**.

### 6. Enable autostart on boot

```bash
chmod +x scripts/setup_autostart.sh
./scripts/setup_autostart.sh
```

On next boot the app launches automatically under the graphical session.

```bash
# Check status
systemctl --user status smart-mirror

# Watch live logs
journalctl --user -u smart-mirror -f

# Disable autostart
systemctl --user disable --now smart-mirror
```

---

## Configuration

Edit `config/settings.json` (or use the Settings screen in the UI):

| Key                         | Default       | Description                              |
|-----------------------------|---------------|------------------------------------------|
| `camera_backend`            | `"auto"`      | `"auto"` / `"raspberry_pi"` / `"usb"`   |
| `camera_device`             | `""`          | Explicit `/dev/videoN` path              |
| `camera_width`              | `1280`        | Capture resolution width                 |
| `camera_height`             | `720`         | Capture resolution height                |
| `camera_fps`                | `30`          | Frames per second                        |
| `camera_bitrate`            | `8000000`     | Encoding bitrate (bps)                   |
| `mirror_orientation_degrees`| `0`           | 0 / 90 / 180 / 270                       |
| `compare_fill_crop`         | `true`        | Crop-to-fill compare panes               |
| `control_screen_index`      | `0`           | Qt screen index for control window       |
| `mirror_screen_index`       | `1`           | Qt screen index for mirror window        |
| `log_level`                 | `"INFO"`      | `DEBUG` / `INFO` / `WARNING`             |

---

## Camera backends

### Raspberry Pi CSI camera (rpicam-vid)
- Requires `rpicam-apps` and the camera enabled in `raspi-config`
- Pipeline: `rpicam-vid` → `ffmpeg tee` → UDP preview streams + H.264 capture file
- Capture is remuxed H.264 → MP4 before review/save

### USB webcam (V4L2 via ffmpeg)
- Auto-detects `/dev/video*` devices
- Pipeline: `ffmpeg -f v4l2` → UDP preview streams + MP4 capture
- No remux needed (output is already MP4)

---

## Workflow summary

### Record a look
1. **Dashboard → Record a Look**
2. 3-second countdown (mirror stays black)
3. Camera starts → live preview on **mirror** + small preview on control screen
4. Press **Stop Recording**
5. Mirror returns to black; clip is remuxed for review
6. Review clip locally, press **Save Look** or **Discard**
7. Saved → gallery

### Gallery → Compare
1. **Gallery** — long-press two cards to select them
2. **Compare** → synchronized side-by-side on both screens

### Gallery → Live Compare
1. **Gallery** — long-press one card to select it
2. **Live Compare** → saved video (left) + live camera (right) on mirror

---

## Development notes

```bash
# Activate venv
source venv/bin/activate

# Run with debug logging
LOG_LEVEL=DEBUG ./scripts/run_dev.sh

# Single-screen development (no Raspberry Pi)
# The app works on any Linux desktop with a webcam.
# Set mirror_screen_index = 0 so both windows share one screen.
```

### System dependencies for macOS development

```bash
brew install ffmpeg
pip install PySide6
# Note: rpicam-vid is Pi-only; the USB adapter works with any webcam
```

---

## Security model

The embedded HTTP server is designed for **LAN use inside a retail store**.
It is **not safe to expose directly to the internet** — there is no TLS, no
authentication at the network layer, and no user account system.

### Open routes (accessible to any device on the LAN)

| Route | What it serves |
|---|---|
| `GET /` | Simple HTML gallery listing the session's recordings |
| `GET /api/videos` | JSON array of current session videos |
| `GET /download/<video_id>` | Raw video file stream (video IDs are UUIDs, not guessable) |

These routes are intentionally open so that staff on the same network can view
recordings without scanning a QR code.  If your network is untrusted, point
`config/settings.json` → `"server_host"` to a specific LAN interface instead
of `0.0.0.0`, or add firewall rules to restrict port access.

### Session-gated route ("View on Phone" QR)

`GET /session/<token>` — the QR code shown after tapping "View on Phone"
contains a 30-minute single-use token.  The page performs a device-identity
check: only the mobile that originally scanned the QR is admitted.

### Export-gated route ("Share This Look" QR)

`GET /export/<token>` — 10-minute export token, also device-gated.  After
the device verifies its identity, a one-time 60-second download token
(`/export/dl/<dl_token>`) is issued.  Download tokens are consumed on first
use.

### Rate limiting

All QR/export/session API endpoints are rate-limited to **10 requests/burst,
1 request/second** per IP address using a token-bucket algorithm.  HTTP `429`
is returned when the limit is exceeded.

---

## Logs

Log files are written to `data/logs/smart_mirror.log` with rotation (5 MB, 3 backups).  
Live logs: `journalctl --user -u smart-mirror -f`
