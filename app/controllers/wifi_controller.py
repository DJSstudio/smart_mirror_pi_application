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

    def __init__(self, wifi_service: WifiService) -> None:
        super().__init__()
        self._service = wifi_service
        self._networks: list[dict] = []
        self._current_ssid: str = ""
        self._status: str = "idle"
        self._error: str = ""
        self._available: bool = wifi_service.is_available()

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
            try:
                nets = self._service.scan()
                self._networks = [n.to_dict() for n in nets]
                self._current_ssid = self._service.current_ssid()
                self._status = "idle"
                LOGGER.debug("WiFi scan complete: %d networks", len(self._networks))
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("WiFi scan failed: %s", exc)
                self._error = str(exc)
                self._status = "error"
            self.changed.emit()

        threading.Thread(target=_do, daemon=True, name="WifiScan").start()

    @Slot(str, str)
    def connectToNetwork(self, ssid: str, password: str) -> None:
        """Connect to *ssid* with *password* (pass empty string for open networks)."""
        if not self._available or self._status == "connecting":
            return
        self._status = "connecting"
        self._error = ""
        self.changed.emit()

        def _do() -> None:
            try:
                ok, msg = self._service.connect(ssid, password)
                if ok:
                    self._current_ssid = ssid
                    self._status = "connected"
                    LOGGER.info("WiFi: connected to %s", ssid)
                else:
                    self._error = msg
                    self._status = "error"
                    LOGGER.warning("WiFi: connection failed: %s", msg)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("WiFi: connect error: %s", exc)
                self._error = str(exc)
                self._status = "error"
            self.changed.emit()

        threading.Thread(target=_do, daemon=True, name="WifiConnect").start()
