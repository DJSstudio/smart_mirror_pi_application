"""WiFi controller — exposed to QML as ``wifiController``.

Status values:
  "idle"        — ready, no operation in progress
  "scanning"    — network scan running in background
  "connecting"  — connect attempt in progress
  "connected"   — last connect succeeded (transient; becomes "idle" on next scan)
  "error"       — last operation failed; errorMessage has details
  "unavailable" — nmcli not found on this system
"""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.services.wifi_service import WifiService

LOGGER = logging.getLogger(__name__)


class WifiController(QObject):
    changed = Signal()
    # Private signals marshal worker-thread results back to the GUI thread so
    # QML-bound state is only ever mutated on the thread that owns it.
    _scanResult = Signal(list, str, str)     # networks, current_ssid, error
    _connectResult = Signal(str, str, str)   # current_ssid, status, error

    def __init__(self, wifi_service: WifiService) -> None:
        super().__init__()
        self._service = wifi_service
        self._networks: list[dict] = []
        self._current_ssid: str = ""
        self._status: str = "idle"
        self._error: str = ""
        self._available: bool = wifi_service.is_available()
        self._scanResult.connect(self._on_scan_result)
        self._connectResult.connect(self._on_connect_result)

        if not self._available:
            self._status = "unavailable"
        else:
            # Cheap non-rescan read to populate current SSID on startup.
            try:
                self._current_ssid = wifi_service.current_ssid()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # QML properties
    # ------------------------------------------------------------------

    @Property("QVariantList", notify=changed)
    def networks(self) -> list:
        return self._networks

    @Property(str, notify=changed)
    def currentSsid(self) -> str:
        return self._current_ssid

    @Property(str, notify=changed)
    def status(self) -> str:
        return self._status

    @Property(str, notify=changed)
    def errorMessage(self) -> str:
        return self._error

    @Property(bool, notify=changed)
    def available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot()
    def scan(self) -> None:
        """Trigger a fresh network scan (takes ~3 s on Pi)."""
        if not self._available or self._status in ("scanning", "connecting"):
            return
        self._status = "scanning"
        self._error = ""
        self.changed.emit()

        def _do() -> None:
            networks: list[dict] = []
            current = self._current_ssid
            error = ""
            try:
                nets = self._service.scan()
                networks = [n.to_dict() for n in nets]
                current = self._service.current_ssid()
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("WiFi scan failed: %s", exc)
                error = str(exc)
            self._scanResult.emit(networks, current, error)

        threading.Thread(target=_do, daemon=True, name="WifiScan").start()

    @Slot(list, str, str)
    def _on_scan_result(self, networks: list, current_ssid: str, error: str) -> None:
        """Apply scan results on the GUI thread."""
        if error:
            self._error = error
            self._status = "error"
        else:
            self._networks = networks
            self._current_ssid = current_ssid
            self._status = "idle"
            LOGGER.debug("WiFi scan complete: %d networks", len(networks))
        self.changed.emit()

    @Slot(str, str)
    def connectToNetwork(self, ssid: str, password: str) -> None:
        """Connect to *ssid* with *password* (pass empty string for open networks)."""
        if not self._available or self._status == "connecting":
            return
        self._status = "connecting"
        self._error = ""
        self.changed.emit()

        def _do() -> None:
            current = self._current_ssid
            status = "error"
            error = ""
            try:
                ok, msg = self._service.connect(ssid, password)
                if ok:
                    current = ssid
                    status = "connected"
                    LOGGER.info("WiFi: connected to %s", ssid)
                else:
                    error = msg
                    LOGGER.warning("WiFi: connection failed: %s", msg)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("WiFi: connect error: %s", exc)
                error = str(exc)
            self._connectResult.emit(current, status, error)

        threading.Thread(target=_do, daemon=True, name="WifiConnect").start()

    @Slot(str, str, str)
    def _on_connect_result(self, current_ssid: str, status: str, error: str) -> None:
        """Apply connect results on the GUI thread."""
        self._current_ssid = current_ssid
        self._status = status
        self._error = error
        self.changed.emit()
