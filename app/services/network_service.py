"""Local network utilities."""
from __future__ import annotations

import logging
import socket

LOGGER = logging.getLogger(__name__)


def get_local_ip() -> str:
    """Return the primary LAN IP of this machine.

    Uses the UDP connect trick (no packet is sent) to determine which
    network interface would route to the internet — that is the 'primary'
    LAN address.  Falls back to 127.0.0.1 when no network is available.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
