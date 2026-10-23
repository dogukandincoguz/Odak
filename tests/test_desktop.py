import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import sys
import tempfile
import time
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from odak.backups import export_json, import_json
from odak.model import Store
from odak.ordering import TaskGrip
from odak.startup import Startup
from odak.ui import MainWindow, configure_app

PROJECT = Path(__file__).resolve().parents[1]


class ListOrderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = Store(self.root / "tasks.sqlite3")

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def test_each_list_keeps_its_order_and_today_is_independent(self):
        a = self.store.save("A", today=True)
        b = self.store.save("B", today=True)
        c = self.store.save("C")
        self.store.reorder_tasks("active", [c, a, b])
        self.store.reorder_tasks("today", [b, a])
        self.store.save("Edited A", task_id=a, today=True)
        self.store.close()
        self.store = Store(self.root / "tasks.sqlite3")
        self.assertEqual(self.store.task_positions("active"), {c: 0, a: 1, b: 2})
        self.assertEqual([t.id for t in sorted((t for t in self.store.all() if t.today), key=lambda t:t.today_position)], [b, a])
        self.store.set_someday(c, True)
        self.store.reorder_tasks("someday", [c])
        self.assertEqual(self.store.task_positions("someday"), {c: 0})
        self.assertEqual(self.store.task_positions("active")[a], 1)

    def test_stale_duplicate_and_wrong_scope_order_cannot_partially_change_the_list(self):
        a, b = self.store.save("A"), self.store.save("B")
        self.store.reorder_tasks("active", [b, a])
        for scope, identities in (("active", [a, a]), ("active", [a]), ("overdue", [a, b]), ("invalid", [a])):
            with self.subTest(scope=scope, identities=identities):
                with self.assertRaises(ValueError):
                    self.store.reorder_tasks(scope, identities)
                self.assertEqual(self.store.task_positions("active"), {b: 0, a: 1})

    def test_purge_cascades_order_rows_without_changing_other_tasks(self):
        a, b = self.store.save("A"), self.store.save("B")
        self.store.reorder_tasks("active", [b, a])
        self.store.delete(a, now=time.time() - 601)
        self.store.purge()
        self.assertEqual(self.store.task_positions("active"), {b: 0})

    def test_json_preserves_order_and_merge_import_remains_exportable(self):
        a, b = self.store.save("A"), self.store.save("B")
        self.store.reorder_tasks("active", [b, a])
        exported = self.root / "export.json"
        export_json(self.store, exported)
        with closing(Store(self.root / "other.sqlite3")) as other:
            existing = other.save("Existing")
            other.reorder_tasks("active", [existing])
            import_json(other, exported)
            self.assertEqual(other.task_positions("active"), {existing:0, b:1, a:2})
            export_json(other, exported)
            with closing(Store(self.root / "third.sqlite3")) as third:
                import_json(third, exported)
                self.assertEqual(third.task_positions("active"), {existing:0, b:1, a:2})
        data = json.loads(exported.read_text(encoding="utf-8"))
        data["task_order"][0]["task_id"] = "f" * 32
        exported.write_text(json.dumps(data), encoding="utf-8")
        with closing(Store(self.root / "invalid.sqlite3")) as other:
            with self.assertRaises(ValueError):
                import_json(other, exported)
            self.assertEqual(other.all(), [])


class DesktopUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        configure_app(cls.app)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = Store(self.root / "tasks.sqlite3")
        self.window = MainWindow(self.store, PROJECT, with_tray=False)
        self.window.startup = Startup(PROJECT, self.root / "data", self.root / "isolated startup")
        self.window.timer.stop()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window._size_timer.stop()
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()
        self.store.close()
        self.temporary.cleanup()

    def test_main_list_can_override_deadline_order_and_keep_new_tasks_at_the_end(self):
        a = self.store.save("Urgent", deadline=datetime.now() + timedelta(hours=2))
        b = self.store.save("Later", deadline=datetime.now() + timedelta(days=2))
        c = self.store.save("No deadline")
        self.window.refresh(force=True)
        self.assertEqual([card.task.id for card in self.window.cards], [a,b,c])
        grip = self.window.cards[-1].findChild(TaskGrip)
        self.assertIsNotNone(grip)
        QTest.keyClick(grip, Qt.Key.Key_Up)
        self.window.move_task(c, a)
        self.assertEqual([card.task.id for card in self.window.cards], [c,a,b])
        d = self.store.save("New urgent task", deadline=datetime.now() + timedelta(hours=1))
        self.window.refresh(force=True)
        self.assertEqual([card.task.id for card in self.window.cards], [c,a,b,d])
        self.window.set_tab("today")
        self.window.set_tab("active")
        self.assertEqual([card.task.id for card in self.window.cards], [c,a,b,d])
        self.window.search.setText("Urgent")
        self.assertTrue(all(card.findChild(TaskGrip) is None for card in self.window.cards))

    def test_taskbar_action_changes_window_type_without_moving_and_survives_restart(self):
        geometry = self.window.geometry()
        menu = self.window.create_menu()
        action = next(action for action in menu.actions() if action.text() == ("Dock'ta göster" if sys.platform == "darwin" else "Görev çubuğunda göster"))
        self.assertFalse(action.isChecked())
        action.trigger()
        self.app.processEvents()
        self.assertEqual(self.window.windowFlags() & Qt.WindowType.WindowType_Mask, Qt.WindowType.Window)
        self.assertTrue(self.window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        self.assertEqual(self.window.geometry(), geometry)
        self.assertIs(self.store.setting("taskbar_visible"), True)
        self.window.hide_to_tray()
        self.assertTrue(self.window.isMinimized())
        self.window.reveal()
        other = MainWindow(self.store, PROJECT, with_tray=False)
        other.timer.stop()
        self.assertTrue(other.taskbar_visible)
        other.hide()
        other.deleteLater()
        self.window.set_taskbar_visible(False)
        self.app.processEvents()
        self.assertEqual(self.window.windowFlags() & Qt.WindowType.WindowType_Mask, Qt.WindowType.Tool)
        self.assertEqual(self.window.geometry(), geometry)
        menu.deleteLater()

    def test_startup_menu_action_creates_and_removes_only_the_isolated_shortcut(self):
        platforms = ["linux", "darwin"] + (["win32"] if sys.platform == "win32" else [])
        for platform in platforms:
            with self.subTest(platform=platform):
                self.window.startup = Startup(PROJECT, self.root / "data", self.root / platform, platform=platform)
                menu = self.window.create_menu()
                action = next(action for action in menu.actions() if action.text().startswith("Başlangıçta çalıştırma:"))
                self.assertTrue(action.isEnabled())
                self.assertFalse(action.isCheckable())
                self.assertEqual(action.text(), "Başlangıçta çalıştırma: devre dışı")
                with patch.object(self.window, "report_error") as error:
                    action.trigger()
                    self.assertFalse(error.called, error.call_args)
                self.assertTrue(self.window.startup.enabled())
                untouched = self.window.startup.shortcut.parent / "other-launcher"
                untouched.write_bytes(b"untouched")
                menu.deleteLater()
                menu = self.window.create_menu()
                action = next(action for action in menu.actions() if action.text().startswith("Başlangıçta çalıştırma:"))
                self.assertEqual(action.text(), "Başlangıçta çalıştırma: etkin")
                self.assertFalse(action.isCheckable())
                action.trigger()
                self.assertFalse(self.window.startup.enabled())
                self.assertEqual(untouched.read_bytes(), b"untouched")
                menu.deleteLater()

    def test_startup_failure_keeps_the_real_status_and_reports_the_error(self):
        self.window.startup = Startup(PROJECT, self.root / "data", self.root / "startup", platform="linux")
        menu = self.window.create_menu()
        action = next(action for action in menu.actions() if action.text().startswith("Başlangıçta çalıştırma:"))
        with patch.object(self.window.startup, "set_enabled", side_effect=OSError("read only")), \
             patch.object(self.window, "report_error") as error, patch.object(self.window, "notify") as notify:
            action.trigger()
            error.assert_called_once()
            notify.assert_not_called()
        self.assertFalse(self.window.startup.enabled())
        menu.deleteLater()
        menu = self.window.create_menu()
        self.assertIn("Başlangıçta çalıştırma: devre dışı", [action.text() for action in menu.actions()])
        menu.deleteLater()
