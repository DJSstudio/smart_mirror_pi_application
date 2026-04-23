# Changelog

All notable changes to Smart Mirror Pi are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- **Session gallery security** — "View on Phone" QR now issues a 30-minute
  device-gated session token. The new `/session/<token>` route requires the
  scanning device to match the session owner; only that device can browse the
  private gallery via the QR link. The open `/` route remains available for
  LAN staff access (see README Security section).
- **Export token device verification** — `/export/<token>` now requires the
  scanning device's `device_id` to match the session owner before issuing a
  one-time 60-second download token.
- **Token-bucket rate limiting** — sensitive API endpoints (`/api/qr/confirm`,
  `/api/qr/choice`, `/api/export/verify`, `/api/session/videos`) are limited
  to 10 requests/burst, 1 req/sec refill per IP.
- **Mirror framing guide** — static 25%/75% crosshair overlay on the mirror
  display during live preview to help users frame their outfit.
- **End session from Dashboard** — "New Session" tile on the dashboard ends
  the current session and starts a fresh one immediately.
- **Settings → End Session redirect** — tapping End Session in Settings now
  navigates back to QR login rather than staying on the Settings page.
- **Premium UI redesign** — charcoal (`#1C1917`) / gold (`#C4956A`) / off-white
  (`#F7F5F2`) design language across all pages; larger nav buttons (88 px wide,
  72 px per item); hero tiles on Dashboard with full-bleed thumbnail for My
  Looks.
- **LICENSE** — MIT licence file.
- **`pyproject.toml`** — Ruff, Mypy, and Pytest configuration consolidated;
  package declared as `smart-mirror-pi` with `smart-mirror` entry-point.
- **`requirements.lock`** — Pinned dependency versions for reproducible Pi
  installs.
- **`scripts/run.sh`** — Production launcher (no dev flags); called by systemd.
- **`.env.example`** — Documents all shell-level environment variables used by
  the launch scripts.
- **Unit tests** — 41 tests covering `SessionService`, `GalleryService`, and
  `ShareServer` (token logic + rate limiting).
- **GitHub Actions CI** — Lint (Ruff), format check, Mypy type check, and
  Pytest on every push/PR to `main`.

### Changed
- **Systemd service** — Added `StartLimitBurst=5` / `StartLimitIntervalSec=300`
  to prevent crash-loop CPU burn; added `SyslogIdentifier=smart-mirror`;
  `ExecStart` now calls `scripts/run.sh` (production script).
- **`.gitignore`** — Expanded to cover venv, data, secrets, editor artefacts.
- **`RaspberryPiCameraAdapter.is_available`** — Narrowed broad `except Exception`
  to `(OSError, subprocess.TimeoutExpired, ValueError)`.

### Security
- Removed "Continue without scan" bypass button from the QR login page.
- Fixed client-side early-return bug in export HTML that blocked phones with
  no `localStorage` access (e.g. private-browsing mode).
- Session gallery gated behind device-verified 30-minute token.
- One-time download tokens expire after 60 seconds and are consumed on use.
- Rate limiting on all QR/export/session API endpoints.
