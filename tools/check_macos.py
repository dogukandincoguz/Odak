"""Geçici veriyle gerçek Cocoa penceresini ve Dock tercihini doğrular."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile

if sys.platform != "darwin":
    raise SystemExit("Bu kontrol macOS içindir.")
os.environ["QT_QPA_PLATFORM"] = "cocoa"
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from odak.model import Store
from odak.startup import Startup
from odak.ui import MainWindow, configure_app


def activation_policy():
    runtime = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    runtime.objc_getClass.argtypes = [ctypes.c_char_p]
    runtime.objc_getClass.restype = ctypes.c_void_p
    runtime.sel_registerName.argtypes = [ctypes.c_char_p]
    runtime.sel_registerName.restype = ctypes.c_void_p
    pointer = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", runtime))
    application = pointer(runtime.objc_getClass(b"NSApplication"), runtime.sel_registerName(b"sharedApplication"))
    integer = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", runtime))
    return integer(application, runtime.sel_registerName(b"activationPolicy"))


app = QApplication([])
app.setQuitOnLastWindowClosed(False)
configure_app(app)
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    store = Store(root / "data/tasks.sqlite3")
    window = MainWindow(store, PROJECT, with_tray=True)
    window.timer.stop()
    window.show()
    QTest.qWait(100)
    assert window.isVisible()
    assert activation_policy() == 1, "Default accessory policy must hide the Dock icon"
    window.set_taskbar_visible(True)
    QTest.qWait(100)
    assert activation_policy() == 0, "Regular policy must show the Dock icon"
    window.set_taskbar_visible(False)
    QTest.qWait(100)
    assert activation_policy() == 1
    startup = Startup(PROJECT, root / "data", root / "LaunchAgents")
    startup.set_enabled(True)
    subprocess.run(["plutil", "-lint", str(startup.shortcut)], check=True)
    startup.set_enabled(False)
    assert not startup.enabled()
    window._size_timer.stop()
    window.hide()
    if window.tray:
        window.tray.hide()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    store.close()
print("Native Cocoa window, Dock transitions and LaunchAgent format passed.")
