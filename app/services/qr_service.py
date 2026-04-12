"""QR code PNG generation.

Requires the 'qrcode[pil]' package:
    pip install "qrcode[pil]"
"""
from __future__ import annotations

import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def generate_qr_png(url: str, output_path: Path) -> Path:
    """Generate a QR code PNG for *url* and write it to *output_path*.

    Returns *output_path*.
    Raises RuntimeError (wrapping ImportError) when qrcode / Pillow are
    not installed.
    """
    try:
        import qrcode  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "QR generation requires 'qrcode[pil]': "
            "pip install 'qrcode[pil]'"
        ) from exc

    qr = qrcode.QRCode(
        version=None,                                     # auto-select size
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path))
    LOGGER.debug("QR saved to %s  url=%s", output_path, url)
    return output_path
