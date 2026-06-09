"""Local network utilities."""
from __future__ import annotations

import logging
import shutil
import socket
import subprocess

LOGGER = logging.getLogger(__name__)


def get_local_ip() -> str:
    """Return the primary LAN IP of this machine.

    Primary: the UDP connect trick (no packet sent) — the source IP that would
    route to the internet.  But the deployment is a documented ISOLATED LAN
    with no default gateway, where that connect() fails and we'd return
    127.0.0.1 — making the login/QR URL ``http://127.0.0.1:8765`` unreachable
    from phones.  So fall back to the host's real LAN IPv4 (via ``hostname -I``)
    before giving up on loopback.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass

    # Gateway-less isolated LAN: take the first non-loopback IPv4 the host has.
    if shutil.which("hostname"):
        try:
            out = subprocess.run(
                ["hostname", "-I"], capture_output=True, text=True, timeout=3,
            )
            for token in out.stdout.split():
                if "." in token and not token.startswith("127."):
                    return token
        except (OSError, subprocess.SubprocessError):
            pass

    LOGGER.warning("get_local_ip: no non-loopback IPv4 found; QR links may be unreachable")
    return "127.0.0.1"
