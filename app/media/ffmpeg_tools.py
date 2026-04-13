"""ffmpeg / ffprobe wrappers."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def _require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise RuntimeError(f"Required binary not found in PATH: {binary}")
    return path


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    LOGGER.debug("$ %s", " ".join(cmd))
    return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)


# ---------------------------------------------------------------------------
# Probing
# ---------------------------------------------------------------------------

def probe_duration(path: Path) -> float | None:
    try:
        result = _run([
            _require("ffprobe"),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(path),
        ])
        payload = json.loads(result.stdout or "{}")
        return float(payload["format"]["duration"])
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("probe_duration failed for %s: %s", path, exc)
        return None


def probe_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        result = _run([
            _require("ffprobe"),
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            str(path),
        ])
        payload = json.loads(result.stdout or "{}")
        stream = (payload.get("streams") or [{}])[0]
        w = int(stream.get("width") or 0) or None
        h = int(stream.get("height") or 0) or None
        return w, h
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("probe_dimensions failed for %s: %s", path, exc)
        return None, None


# ---------------------------------------------------------------------------
# Transformations
# ---------------------------------------------------------------------------

def remux_h264_to_mp4(src: Path, dst: Path, fps: int, trim_start: float = 0.0) -> None:
    """Wrap a raw H.264 stream in an MP4 container (no re-encode).

    If trim_start > 0, the first trim_start seconds are dropped via output
    seek (-ss after -i).  Output seek is used because raw H.264 has no
    container index for fast input seeking.
    """
    cmd = [
        _require("ffmpeg"),
        "-hide_banner", "-loglevel", "warning",
        "-fflags", "+genpts",
        "-r", str(fps),
        "-i", str(src),
    ]
    if trim_start > 0:
        cmd += ["-ss", str(trim_start)]
    cmd += ["-c:v", "copy", "-movflags", "+faststart", "-y", str(dst)]
    _run(cmd)


def trim_mp4(src: Path, dst: Path, start_seconds: float) -> None:
    """Copy src → dst, discarding the first start_seconds via fast input seek.

    MP4 containers have an index, so -ss before -i jumps straight to the
    nearest keyframe without decoding discarded frames.
    """
    _run([
        _require("ffmpeg"),
        "-hide_banner", "-loglevel", "warning",
        "-ss", str(start_seconds),
        "-i", str(src),
        "-c:v", "copy",
        "-movflags", "+faststart",
        "-y", str(dst),
    ])


def generate_thumbnail(src: Path, dst: Path, seek: float = 1.0) -> Path:
    """Extract a single frame and save as JPEG."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    _run([
        _require("ffmpeg"),
        "-hide_banner", "-loglevel", "warning",
        "-ss", str(seek),
        "-i", str(src),
        "-frames:v", "1",
        "-vf", "scale=640:-1",
        "-y", str(dst),
    ])
    return dst


def safe_unlink(path: Path | None) -> None:
    if path:
        path.unlink(missing_ok=True)
