"""Playback service — orchestrates video playback and mirror display for gallery workflows.

Also acts as the bridge between the controller-screen UI (play/pause/seek
buttons, scrub bar, record button) and the mirror window's MediaPlayers /
QtCameraSession, since those live in different windows and can't directly
reference each other from QML.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.config.paths import AppPaths
from app.models.entities import VideoRecord
from app.services.camera_service import CameraService
from app.services.mirror_display_service import MirrorDisplayService
from app.services.qt_camera_session import QtCameraSession
from app.services.recording_service import RecordingService
from app.services.settings_service import SettingsService

LOGGER = logging.getLogger(__name__)


class PlaybackService(QObject):
    """Exposed to QML as `playbackService`."""

    changed = Signal()

    # Signals → mirror QML (MediaPlayer subscribes via Connections)
    playRequested = Signal()
    pauseRequested = Signal()
    seekRequested = Signal(int)   # absolute position in ms

    # Signals → controller QML (when mirror state changes)
    playbackStateChanged = Signal()
    # Emitted after a Live Compare recording is saved to the gallery; main.py
    # connects this to gallery_controller.refresh() so the new entry appears.
    videoSaved = Signal(str)   # video title
    # Emitted when a Live Compare recording fails to save; main.py wires this
    # to app_controller.showError so a lost clip is reported, not swallowed.
    saveFailed = Signal(str)   # error message
    # Private: marshals the bg save result (title, error) back to the GUI thread.
    _lcSaveResult = Signal(str, str)

    def __init__(
        self,
        *,
        camera_service: CameraService,
        mirror_display: MirrorDisplayService,
        settings: SettingsService,
        paths: AppPaths,
        recording_service: RecordingService,
    ) -> None:
        super().__init__()
        self._camera = camera_service
        self._mirror = mirror_display
        self._paths = paths
        self._recording_svc = recording_service
        # qt_camera_session is attached AFTER QGuiApplication exists (it
        # requires QGui).  Set via attach_qt_camera_session() in main.py.
        self._qt_camera: QtCameraSession | None = None
        self._mode = "idle"
        self._primary_source = ""
        self._secondary_source = ""
        self._primary_label = ""
        self._secondary_label = ""
        self._primary_video_id = ""
        # Mirror playback state — updated by mirror QML, read by controller
        self._mirror_position = 0
        self._mirror_duration = 0
        self._is_playing = True
        # Live Compare recording state
        self._lc_recording = False
        self._lc_recording_path: Path | None = None
        self._lcSaveResult.connect(self._on_lc_save_result)

    def attach_qt_camera_session(self, session: QtCameraSession) -> None:
        """Inject the Qt camera session after QGuiApplication exists."""
        self._qt_camera = session

    # ------------------------------------------------------------------
    # QML-readable properties
    # ------------------------------------------------------------------

    @Property(str, notify=changed)
    def mode(self) -> str:
        return self._mode

    @Property(str, notify=changed)
    def primarySource(self) -> str:
        return self._primary_source

    @Property(str, notify=changed)
    def secondarySource(self) -> str:
        return self._secondary_source

    @Property(str, notify=changed)
    def primaryLabel(self) -> str:
        return self._primary_label

    @Property(str, notify=changed)
    def secondaryLabel(self) -> str:
        return self._secondary_label

    @Property(str, notify=changed)
    def currentVideoId(self) -> str:
        return self._primary_video_id

    # ── Mirror playback state (updated by mirror QML) ─────────────
    @Property(int, notify=playbackStateChanged)
    def mirrorPosition(self) -> int:
        return self._mirror_position

    @Property(int, notify=playbackStateChanged)
    def mirrorDuration(self) -> int:
        return self._mirror_duration

    @Property(bool, notify=playbackStateChanged)
    def isPlaying(self) -> bool:
        return self._is_playing

    @Property(bool, notify=changed)
    def liveCompareRecording(self) -> bool:
        return self._lc_recording

    # ── Mirror reports state back ─────────────────────────────────
    @Slot(int)
    def setMirrorPosition(self, pos_ms: int) -> None:
        if pos_ms != self._mirror_position:
            self._mirror_position = pos_ms
            self.playbackStateChanged.emit()

    @Slot(int)
    def setMirrorDuration(self, dur_ms: int) -> None:
        if dur_ms != self._mirror_duration:
            self._mirror_duration = dur_ms
            self.playbackStateChanged.emit()

    @Slot(bool)
    def setMirrorPlaying(self, playing: bool) -> None:
        if playing != self._is_playing:
            self._is_playing = playing
            self.playbackStateChanged.emit()

    # ── Controller commands → mirror ──────────────────────────────
    @Slot()
    def requestPlay(self) -> None:
        self._is_playing = True
        self.playRequested.emit()
        self.playbackStateChanged.emit()

    @Slot()
    def requestPause(self) -> None:
        self._is_playing = False
        self.pauseRequested.emit()
        self.playbackStateChanged.emit()

    @Slot()
    def requestTogglePlayPause(self) -> None:
        if self._is_playing:
            self.requestPause()
        else:
            self.requestPlay()

    @Slot(int)
    def requestSeek(self, position_ms: int) -> None:
        position_ms = max(0, position_ms)
        if self._mirror_duration > 0:
            position_ms = min(position_ms, self._mirror_duration)
        self._mirror_position = position_ms
        self.seekRequested.emit(position_ms)
        self.playbackStateChanged.emit()

    @Slot(int)
    def requestSeekRelative(self, delta_ms: int) -> None:
        self.requestSeek(self._mirror_position + delta_ms)

    # ── Live Compare recording ────────────────────────────────────
    @Slot()
    def startLiveCompareRecording(self) -> None:
        """Begin recording the live camera feed during Live Compare."""
        if self._qt_camera is None:
            LOGGER.warning("Cannot start Live Compare recording — Qt camera not attached")
            return
        if self._mode != "live_compare" or self._lc_recording:
            return
        cap_path = self._paths.temp_dir / f"capture_lc_{int(time.time() * 1000)}.mp4"
        try:
            self._qt_camera.begin_recording(cap_path)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed to start Live Compare recording: %s", exc)
            return
        self._lc_recording = True
        self._lc_recording_path = cap_path
        self.changed.emit()

    @Slot()
    def stopLiveCompareRecording(self) -> None:
        """Stop the Live Compare recording and save the file to the gallery
        (no review screen — recording started on user tap, no warmup to trim).

        end_recording() runs on the GUI thread (it tears down session/Qt state
        and must finish before close_active() stops the camera); only the
        file/DB save is offloaded to a bg thread. The result is marshalled back
        via _lcSaveResult so a save failure is surfaced to the user via
        saveFailed instead of silently losing the clip.
        """
        if not self._lc_recording or self._qt_camera is None:
            return
        # Flip UI state now so the button updates immediately.
        self._lc_recording = False
        self._lc_recording_path = None
        self.changed.emit()

        # end_recording() finalizes the file AND tears down recording state on
        # the shared QCamera session (sink disconnect, writer join, ffmpeg
        # close).  It MUST run on the GUI thread — both because that teardown
        # touches Qt objects, and because it must complete BEFORE close_active()
        # (called right after this in the QML Close handler) stops the camera.
        # Running it on a bg thread raced close_active on the shared session and
        # let its discard unlink the file mid-save (corrupted/lost clip, crash).
        # Only the file/DB save below — which touches neither Qt nor the session
        # — is offloaded.  In practice end_recording is <1s (ffmpeg just writes
        # the MP4 trailer for an already-encoded stream).
        actual_path = self._qt_camera.end_recording()
        if actual_path is None or not actual_path.exists():
            LOGGER.warning("Live Compare recording produced no file")
            self.saveFailed.emit("Recording produced no file.")
            return

        recording_svc = self._recording_svc

        def _bg() -> None:
            title, error = "", ""
            try:
                from app.models.entities import CompletedCapture  # noqa: PLC0415
                capture = CompletedCapture(
                    file_path=actual_path,
                    file_format="mp4",
                    backend="usb_qt_lc",
                )
                prepared = recording_svc.prepare_review(capture, trim_start=0.0)
                video = recording_svc.save_prepared(prepared)
                LOGGER.info("Live Compare recording saved: %s", video.title)
                title = video.title
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Failed to save Live Compare recording: %s", exc)
                error = f"Couldn't save the recording: {exc}"
            self._lcSaveResult.emit(title, error)

        threading.Thread(target=_bg, daemon=True).start()

    @Slot(str, str)
    def _on_lc_save_result(self, title: str, error: str) -> None:
        """Runs on the GUI thread after the bg stop+save completes."""
        if error:
            self.saveFailed.emit(error)
        elif title:
            self.videoSaved.emit(title)

    # ------------------------------------------------------------------
    # Actions — decorated as @Slot so QML can call them directly
    # ------------------------------------------------------------------

    @Slot()
    def close_active(self) -> None:
        """Stop any active playback and return mirror to idle/black."""
        if self._mode == "live_compare":
            self._camera.stop(discard=True)
        self._mode = "idle"
        self._primary_source = ""
        self._secondary_source = ""
        self._primary_label = ""
        self._secondary_label = ""
        self._primary_video_id = ""
        self._mirror.show_idle_black()
        self.changed.emit()

    # ------------------------------------------------------------------
    # Called by GalleryController (Python-to-Python, Slot not strictly
    # required but added for completeness)
    # ------------------------------------------------------------------

    def open_video(self, video: VideoRecord) -> None:
        url = str(video.to_dict()["sourceUrl"])
        self._mode = "video"
        self._primary_source = url
        self._secondary_source = ""
        self._primary_label = video.title
        self._secondary_label = ""
        self._primary_video_id = video.id
        self._mirror.show_video(url)
        self.changed.emit()

    def open_compare(self, left: VideoRecord, right: VideoRecord) -> None:
        left_url  = str(left.to_dict()["sourceUrl"])
        right_url = str(right.to_dict()["sourceUrl"])
        self._mode = "compare"
        self._primary_source = left_url
        self._secondary_source = right_url
        self._primary_label = left.title
        self._secondary_label = right.title
        self._mirror.show_compare(left_url, right_url)
        self.changed.emit()

    def open_live_compare(self, video: VideoRecord) -> None:
        preview   = self._camera.start_preview_only()
        video_url = str(video.to_dict()["sourceUrl"])
        self._mode = "live_compare"
        self._primary_source = video_url
        self._secondary_source = preview.control_preview_url
        self._primary_label = video.title
        self._secondary_label = "Live"
        self._mirror.show_live_compare(video_url, preview.mirror_preview_url)
        self.changed.emit()
