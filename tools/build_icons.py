"""Render desktop icons from Odak's vector drawing: uv run python tools/build_icons.py."""
import os
from pathlib import Path
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication
from odak.ui import app_icon


def encoded_icon(size: int, format: str = "PNG") -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap = app_icon(size).pixmap(size, size)
    if pixmap.width() != size or not pixmap.save(buffer, format):
        raise RuntimeError(f"Cannot render {size}px {format} icon")
    return bytes(buffer.data())


def build_icons(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    pngs = {size: encoded_icon(size) for size in (16, 32, 64, 128, 256, 512, 1024)}
    sizes = (16, 20, 24, 32, 40, 48, 64, 72, 96, 128, 256)
    entries, images = [], []
    offset = 6 + 16 * len(sizes)
    for size in sizes:
        if size == 256:
            image = pngs[size]
        else:
            frame = encoded_icon(size, "ICO")
            length, position = struct.unpack_from("<II", frame, 14)
            image = frame[position:position + length]
        entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(image), offset))
        images.append(image)
        offset += len(image)
    (directory / "odak.ico").write_bytes(struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(entries + images))
    # Standard and Retina representations for macOS Finder and Dock.
    types = ((b"icp4", 16), (b"ic11", 32), (b"icp5", 32), (b"ic12", 64),
             (b"ic07", 128), (b"ic13", 256), (b"ic08", 256),
             (b"ic14", 512), (b"ic09", 512), (b"ic10", 1024))
    chunks = b"".join(struct.pack(">4sI", kind, len(pngs[size]) + 8) + pngs[size] for kind, size in types)
    (directory / "odak.icns").write_bytes(struct.pack(">4sI", b"icns", len(chunks) + 8) + chunks)
    (directory / "odak.png").write_bytes(pngs[256])


if __name__ == "__main__":
    app = QApplication([])
    build_icons(PROJECT / "assets")
    print("Windows ICO, Linux PNG and macOS ICNS generated at native resolutions.")
