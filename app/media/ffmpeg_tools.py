from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path


LOGGER = logging.getLogger(__name__)


def require_command(binary: str) -> str:
    resolved = shutil.which(binary)
    if not resolved:
        raise RuntimeError(f"Required command not found in PATH: {binary}")
    return resolved


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    LOGGER.debug("Running command: %s", " ".join(command))
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def probe_duration(video_path: Path) -> float | None:
    ffprobe = require_command("ffprobe")
    try:
        result = run_command(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(video_path),
            ]
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Unable to probe duration for %s: %s", video_path, exc)
        return None
    try:
        payload = json.loads(result.stdout or "{}")
        duration = float(payload["format"]["duration"])
    except Exception:  # noqa: BLE001
        return None
    return duration


def probe_dimensions(video_path: Path) -> tuple[int | None, int | None]:
    ffprobe = require_command("ffprobe")
    try:
        result = run_command(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                str(video_path),
            ]
        )
        payload = json.loads(result.stdout or "{}")
        stream = (payload.get("streams") or [{}])[0]
        return int(stream.get("width") or 0) or None, int(stream.get("height") or 0) or None
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Unable to probe dimensions for %s: %s", video_path, exc)
        return None, None


def remux_h264_to_mp4(input_path: Path, output_path: Path, fps: int) -> None:
    ffmpeg = require_command("ffmpeg")
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-fflags",
            "+genpts",
            "-r",
            str(fps),
            "-i",
            str(input_path),
            "-c:v",
            "copy",
            "-movflags",
            "+faststart",
            "-y",
            str(output_path),
        ]
    )


def generate_thumbnail(video_path: Path, output_path: Path) -> Path:
    ffmpeg = require_command("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-ss",
            "1.0",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            "scale=640:-1",
            "-y",
            str(output_path),
        ]
    )
    return output_path


def safe_unlink(path: Path | None) -> None:
    if path and path.exists():
        path.unlink(missing_ok=True)
