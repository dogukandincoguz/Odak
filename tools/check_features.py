"""Gerçek Windows fare olaylarıyla sıralama, boyutlandırma ve form sürükleme.

Yalnız geçici veri kullanır. Fareyi birkaç saniye hareket ettirir.
"""
import ctypes
import os
import sys
import tempfile
import threading
import time
from contextlib import closing
from ctypes import wintypes
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "windows"
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from PySide6.QtCore import QCoreApplication, QEvent, QPoint
from PySide6.QtWidgets import QApplication
from odak.model import Store
from odak.ordering import TaskGrip
from odak.ui import MainWindow, TaskDialog, configure_app

user32 = ctypes.windll.user32
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]

app = QApplication([])
configure_app(app)
app.setQuitOnLastWindowClosed(False)


def physical(widget, point=None):
    window = widget.window()
    point = widget.mapTo(window, point or widget.rect().center())
    ratio = window.devicePixelRatioF()
    native = wintypes.POINT(round(point.x()*ratio), round(point.y()*ratio))
    user32.ClientToScreen(int(window.winId()), ctypes.byref(native))
    return native.x, native.y


def gesture(start, end):
    def mouse():
        time.sleep(.12)
        user32.SetCursorPos(*start)
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        try:
            time.sleep(.1)
            for step in range(1, 16):
                x = round(start[0]+(end[0]-start[0])*step/15)
                y = round(start[1]+(end[1]-start[1])*step/15)
                user32.SetCursorPos(x, y)
                time.sleep(.025)
            time.sleep(.1)
        finally:
            user32.mouse_event(0x0004, 0, 0, 0, 0)
    thread = threading.Thread(target=mouse, daemon=True)
    thread.start()
    until = time.monotonic()+2
    while time.monotonic() < until:
        app.processEvents()
        time.sleep(.01)
    thread.join(timeout=1)
    assert not thread.is_alive(), "Mouse gesture did not finish"
    app.processEvents()


original_cursor = wintypes.POINT()
user32.GetCursorPos(ctypes.byref(original_cursor))
try:
    with tempfile.TemporaryDirectory() as directory, closing(Store(Path(directory)/"features.sqlite3")) as store:
        identities = [store.save(title, today=True) for title in ("First", "Second")]
        window = MainWindow(store, PROJECT, with_tray=False)
        window.setWindowTitle("Odak - feature UI check")
        window.timer.stop()
        window.resize(540, min(1000,window.screen().availableGeometry().height()-80))
        window.move(100,60)
        window.set_tab("today")
        window.show()
        window.raise_()
        window.activateWindow()
        app.processEvents()
        until = time.monotonic()+.25
        while time.monotonic() < until:
            app.processEvents()
            time.sleep(.01)
        grip = window.cards[0].findChild(TaskGrip)
        last = window.cards[-1]
        start = physical(grip)
        end = physical(last, QPoint(last.width()//2,last.height()-3))
        gesture(start,end)
        assert [card.task.id for card in window.cards] == identities[1:]+identities[:1], "Native drag must reorder the Today cards"
        assert [task.id for task in sorted(store.all(),key=lambda t:t.today_position)] == identities[1:]+identities[:1]

        window.set_tab("active")
        app.processEvents()
        initial = [card.task.id for card in window.cards]
        grip = window.cards[-1].findChild(TaskGrip)
        first = window.cards[0]
        gesture(physical(grip), physical(first, QPoint(first.width()//2, 3)))
        expected = initial[-1:] + initial[:-1]
        assert [card.task.id for card in window.cards] == expected, "Native drag must reorder the main task list"
        assert sorted(store.task_positions("active"), key=store.task_positions("active").get) == expected
        window.set_tab("today")
        assert [card.task.id for card in window.cards] == identities[1:]+identities[:1], "Today must keep its own order"

        # The header, hint and gap above the first card are invisible drop targets.
        for tab in ("today", "active"):
            window.set_tab(tab)
            for target_widget, target_point in (
                (window.section_title, window.section_title.rect().center()),
                (window.section_hint, window.section_hint.rect().center()),
                (window.list_header, QPoint(window.list_header.width()//2, window.list_header.height()-3)),
            ):
                app.processEvents()
                initial = [card.task.id for card in window.cards]
                grip = window.cards[-1].findChild(TaskGrip)
                gesture(physical(grip), physical(target_widget, target_point))
                expected = initial[-1:] + initial[:-1]
                assert [card.task.id for card in window.cards] == expected, f"Header drop must prepend in {tab}"
                assert window.list_widget.indicator is None, "The drop indicator must disappear after release"

        geometry = window.geometry()
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
        user32.GetWindow.restype = wintypes.HWND
        window.set_taskbar_visible(True)
        app.processEvents()
        style = user32.GetWindowLongW(int(window.winId()), -20)
        owner = user32.GetWindow(int(window.winId()), 4)
        assert not style & 0x80 and (not owner or style & 0x40000), "Taskbar mode must expose an unowned application window"
        assert window.geometry() == geometry
        window.hide_to_tray()
        app.processEvents()
        assert window.isMinimized(), "Taskbar mode must minimize to the taskbar"
        window.reveal()
        window.set_taskbar_visible(False)
        app.processEvents()
        style = user32.GetWindowLongW(int(window.winId()), -20)
        assert style & 0x80 and not style & 0x40000, "Tray mode must hide the taskbar button"
        assert window.geometry() == geometry

        before = window.size()
        corner = window._resize_handles[-1]
        start = physical(corner)
        gesture(start,(start[0]+90,start[1]+60))
        assert window.width() > before.width() and window.height() > before.height(), "Native corner drag must resize"
        window.save_size()
        assert store.setting("window_size") == [window.width(),window.height()]

        dialog = TaskDialog(window)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        app.processEvents()
        before = dialog.pos()
        start = physical(dialog.header, QPoint(dialog.header.width()-65,dialog.header.height()//2))
        gesture(start,(start[0]+60,start[1]+45))
        assert dialog.pos() != before, "Custom dialog header must drag"
        dialog.reject()
        dialog.deleteLater()
        window._size_timer.stop()
        window.hide()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        app.processEvents()
finally:
    user32.SetCursorPos(original_cursor.x,original_cursor.y)

print("Native Windows feature check: main/Today drag order, invisible header drops, taskbar modes, corner resize and custom header move OK.")
