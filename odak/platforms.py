"""Kullanıcı verisi ve masaüstü ortamına özgü küçük uyarlamalar."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys


def default_data_directory(project: Path) -> Path:
    # Existing source installations keep their data; installed launchers pass --data-dir.
    if sys.platform == "win32" or (project / "data/odak.sqlite3").is_file():
        return project / "data"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Odak"
    configured = Path(os.environ.get("XDG_DATA_HOME", ""))
    root = configured if configured.is_absolute() else Path.home() / ".local/share"
    return root / "Odak"


def set_dock_visible(visible: bool):
    if sys.platform != "darwin":
        return
    # Qt manages the windows; only the macOS application activation policy is native.
    runtime = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    runtime.objc_getClass.argtypes = [ctypes.c_char_p]
    runtime.objc_getClass.restype = ctypes.c_void_p
    runtime.sel_registerName.argtypes = [ctypes.c_char_p]
    runtime.sel_registerName.restype = ctypes.c_void_p
    send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(
        ("objc_msgSend", runtime))
    application = send(runtime.objc_getClass(b"NSApplication"), runtime.sel_registerName(b"sharedApplication"))
    policy = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(
        ("objc_msgSend", runtime))
    if not policy(application, runtime.sel_registerName(b"setActivationPolicy:"), 0 if visible else 1):
        raise OSError("Dock görünürlüğü değiştirilemedi.")
