"""Windows'ta gerçek görev formunun önde ve tıklanabilir olduğunu doğrular.

Geçici veritabanı kullanır; mevcut görevlere dokunmaz.
"""
import ctypes
import os
import sys
import tempfile
import traceback
from contextlib import closing
from ctypes import wintypes
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "windows"
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from odak.model import Store
from odak.ui import MainWindow, TaskDialog, configure_app

user32 = ctypes.windll.user32
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.IsWindowEnabled.argtypes = [wintypes.HWND]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND

app = QApplication([])
configure_app(app)
app.setQuitOnLastWindowClosed(False)
with tempfile.TemporaryDirectory() as directory, closing(Store(Path(directory) / "native-check.sqlite3")) as store:
    window = MainWindow(store, PROJECT, with_tray=False)
    window.setWindowTitle("Odak - native UI check")
    window.move(100, 80)
    window.show()
    app.processEvents()
    failures = []

    def fill_form(editing=False):
        dialog = app.activeModalWidget()
        try:
            assert isinstance(dialog, TaskDialog), "Task form must be modal"
            hwnd = int(dialog.winId())
            style = user32.GetWindowLongW(hwnd, -20)
            assert style & 0x8, "Task form must stay above the always-on-top main window"
            assert style & 0x80 and not style & 0x40000, "Task form must stay out of taskbar"
            assert user32.IsWindowEnabled(hwnd), "Task form must accept input"
            assert not user32.IsWindowEnabled(int(window.winId())), "Main window should wait for the form"
            # Gerçek ekran koordinatında en öndeki pencereyi denetle.
            point = dialog.title.mapTo(dialog, dialog.title.rect().center())
            ratio = dialog.devicePixelRatioF()
            native_point = wintypes.POINT(round(point.x() * ratio), round(point.y() * ratio))
            user32.ClientToScreen(hwnd, ctypes.byref(native_point))
            hit = user32.WindowFromPoint(native_point)
            assert user32.GetAncestor(hit, 2) == hwnd, "Task form is obscured by another window"
            if editing:
                dialog.title.selectAll()
            QTest.keyClicks(dialog.title, "Edited native task" if editing else "Native task")
            QTest.mouseClick(dialog.use_date, Qt.MouseButton.LeftButton,
                             pos=QPoint(8, dialog.use_date.height() // 2))
            assert dialog.use_date.isChecked() != editing, "Date toggle must accept a click"
            QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
        except BaseException:
            failures.append(traceback.format_exc())
            if isinstance(dialog, TaskDialog):
                dialog.reject()

    QTimer.singleShot(200, fill_form)
    window.edit_task()
    if failures:
        raise AssertionError("\n".join(failures))
    assert len(store.all()) == 1 and store.all()[0].title == "Native task"
    assert store.all()[0].deadline is not None
    QTimer.singleShot(200, lambda: fill_form(editing=True))
    window.edit_task(store.all()[0])
    if failures:
        raise AssertionError("\n".join(failures))
    assert store.all()[0].title == "Edited native task"
    assert store.all()[0].deadline is None
    assert user32.IsWindowEnabled(int(window.winId()))
    window.timer.stop()
    window.hide()
print("Native Windows check: form on top, taskbar hidden, input, add, edit and save OK.")
