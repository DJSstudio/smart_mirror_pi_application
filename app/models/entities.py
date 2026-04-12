"""Core data entities used throughout the application."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_file_url(value: str | Path | None) -> str:
    if not value:
        return ""
    text = str(value)
    if "://" in text:
        return text
    return Path(text).expanduser().resolve().as_uri()


def format_duration(seconds: float | None) -> str:
    if not seconds or seconds <= 0:
        return "--:--"
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Persistent records
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SessionRecord:
    id: str
    name: str
    started_at: str
    ended_at: str | None
    active: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "startedAt": self.started_at,
            "endedAt": self.ended_at or "",
            "active": self.active,
        }


@dataclass(frozen=True, slots=True)
class VideoRecord:
    id: str
    session_id: str
    title: str
    file_path: str
    thumbnail_path: str | None
    duration_seconds: float | None
    created_at: str
    camera_backend: str
    notes: str
    width: int | None
    height: int | None

    def created_label(self) -> str:
        try:
            stamp = datetime.fromisoformat(self.created_at)
            return stamp.strftime("%b %d, %Y  %H:%M")
        except ValueError:
            return self.created_at

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "title": self.title,
            "filePath": self.file_path,
            "thumbnailPath": self.thumbnail_path or "",
            "sourceUrl": _to_file_url(self.file_path),
            "thumbnailUrl": _to_file_url(self.thumbnail_path),
            "durationSeconds": self.duration_seconds or 0.0,
            "durationLabel": format_duration(self.duration_seconds),
            "createdAt": self.created_at,
            "createdLabel": self.created_label(),
            "cameraBackend": self.camera_backend,
            "notes": self.notes,
            "width": self.width or 0,
            "height": self.height or 0,
        }


# ---------------------------------------------------------------------------
# Transient camera / recording entities
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CameraPreview:
    """Live stream URLs and metadata from an active camera session."""
    control_preview_url: str   # URL for the control-screen preview pane
    mirror_preview_url: str    # URL for the mirror display
    backend: str               # "raspberry_pi" | "usb"
    recording: bool            # True if a capture file is being written


@dataclass(frozen=True, slots=True)
class CompletedCapture:
    """Raw capture file produced after recording stops."""
    file_path: Path
    file_format: str           # "h264" | "mp4"
    backend: str


@dataclass(frozen=True, slots=True)
class PreparedRecording:
    """MP4-remuxed file ready for review / saving."""
    file_path: Path
    backend: str
