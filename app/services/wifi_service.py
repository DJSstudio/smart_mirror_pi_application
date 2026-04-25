"""WiFi management service using nmcli (NetworkManager CLI).

Provides scan, connect, and current-SSID queries.
Falls back gracefully when nmcli is not available (dev machines, etc.).
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class WifiNetwork:
    ssid: str
    signal: int     # 0–100
    secured: bool
    in_use: bool

    def to_dict(self) -> dict:
        return {
            "ssid": self.ssid,
            "signal": self.signal,
            "secured": self.secured,
            "inUse": self.in_use,
        }


class WifiService:
    """Thin wrapper around nmcli for listing and joining WiFi networks."""

    @staticmethod
    def is_available() -> bool:
        return shutil.which("nmcli") is not None

    def scan(self) -> list[WifiNetwork]:
        """Return visible networks sorted by signal strength (strongest first).

        Passes --rescan yes so the adapter does a fresh scan (~3 s on Pi).
        Duplicate SSIDs are de-duplicated, keeping the strongest entry.
        """
        result = subprocess.run(
            [
                "nmcli", "--terse",
                "--fields", "IN-USE,SSID,SIGNAL,SECURITY",
                "dev", "wifi", "list",
                "--rescan", "yes",
            ],
            capture_output=True, text=True, timeout=20,
        )
        networks: dict[str, WifiNetwork] = {}
        for line in result.stdout.splitlines():
            # nmcli -t separates with ":" and escapes literal ":" in SSIDs as "\:"
            parts = line.split(":")
            if len(parts) < 3:
                continue
            in_use = parts[0].strip() == "*"
            ssid = parts[1].strip()
            if not ssid or ssid == "--":
                continue
            try:
                signal = int(parts[2].strip())
            except ValueError:
                signal = 0
            secured = len(parts) > 3 and bool(parts[3].strip())
            if ssid not in networks or signal > networks[ssid].signal:
                networks[ssid] = WifiNetwork(
                    ssid=ssid, signal=signal, secured=secured, in_use=in_use
                )
        return sorted(networks.values(), key=lambda n: (-n.in_use, -n.signal))

    def current_ssid(self) -> str:
        """Return the SSID of the currently active WiFi connection, or ''."""
        result = subprocess.run(
            ["nmcli", "--terse", "--fields", "IN-USE,SSID", "dev", "wifi", "list"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            parts = line.split(":")
            if parts and parts[0].strip() == "*":
                return parts[1].strip() if len(parts) > 1 else ""
        return ""

    def connect(self, ssid: str, password: str) -> tuple[bool, str]:
        """Connect to *ssid* with optional *password*.

        Returns *(success, error_message)*.
        Timeout is 30 s — nmcli blocks until connected or failed.
        """
        cmd = ["nmcli", "dev", "wifi", "connect", ssid]
        if password:
            cmd += ["password", password]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return True, ""
            err = (result.stderr or result.stdout).strip()
            # Strip the verbose nmcli prefix from error messages
            err = err.replace("Error: ", "").strip()
            return False, err or "Connection failed"
        except subprocess.TimeoutExpired:
            return False, "Connection timed out after 30 s"
