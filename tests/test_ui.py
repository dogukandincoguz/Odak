import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from odak.model import Store
from odak.ui import MainWindow, TaskDialog, configure_app


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        configure_app(cls.app)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name) / "tasks.sqlite3")
        self.window = MainWindow(self.store, Path(__file__).resolve().parents[1], with_tray=False)
        self.window.timer.stop()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()
        self.store.close()
        self.directory.cleanup()

    def test_form_deadline_defaults_and_independent_toggles(self):
        dialog = TaskDialog(self.window)
        self.assertFalse(dialog.save_button.isEnabled())
        self.assertIsNone(dialog.values()["deadline"])
        dialog.title.setText("Bir iş")
        self.assertTrue(dialog.save_button.isEnabled())
        dialog.use_date.setChecked(True)
        self.assertTrue(dialog.date.isEnabled())
        self.assertEqual(dialog.values()["deadline"].hour, 23)
        self.assertEqual(dialog.values()["deadline"].minute, 59)
        dialog.use_date.setChecked(False)
        dialog.use_time.setChecked(True)
        self.assertEqual(dialog.values()["deadline"].date(), datetime.now().date())
        self.assertEqual(dialog.values()["deadline"].second, 0)
        self.assertEqual(dialog.values()["deadline"].microsecond, 0)
        dialog.deleteLater()

    def test_add_button_opens_form_and_saves_task(self):
        def fill_form():
            dialog = self.app.activeModalWidget()
            self.assertIsInstance(dialog, TaskDialog)
            QTest.keyClicks(dialog.title, "A new task")
            QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
        QTimer.singleShot(30, fill_form)
        add_button = self.window.add_task_button
        QTest.mouseClick(add_button, Qt.MouseButton.LeftButton)
        self.assertEqual(self.store.all()[0].title, "A new task")
        self.assertEqual(len(self.window.cards), 1)

    def test_sections_sorting_search_and_counts(self):
        now = datetime.now()
        self.store.save("Geçmiş iş", deadline=now - timedelta(hours=1))
        self.store.save("İki gün sonra", deadline=now + timedelta(days=2))
        self.store.save("Acil iş", deadline=now + timedelta(hours=4))
        self.store.save("Serbest iş")
        self.window.refresh(force=True)
        self.assertEqual([c.task.title for c in self.window.cards], ["Acil iş", "İki gün sonra", "Serbest iş"])
        self.assertEqual([c.kind for c in self.window.cards], ["urgent", "soon", "neutral"])
        self.assertEqual(self.window.stat_values["active"].text(), "4")
        QTest.mouseClick(self.window.tabs["overdue"], Qt.MouseButton.LeftButton)
        self.assertEqual(self.window.section_title.text(), "Deadline’ı geçenler")
        self.assertEqual([c.task.title for c in self.window.cards], ["Geçmiş iş"])
        self.window.set_tab("active")
        self.window.search.setText("iki gün")
        self.assertEqual(len(self.window.cards), 1)

    def test_click_complete_delete_and_restore(self):
        self.store.save("Tamamlanacak iş")
        self.window.refresh(force=True)
        # QToolButton erişilebilir adlarıyla gerçek tıklama yollarını dene.
        from PySide6.QtWidgets import QToolButton
        buttons = self.window.cards[0].findChildren(QToolButton)
        QTest.mouseClick(next(b for b in buttons if b.accessibleName() == "Tamamlandı işaretle"), Qt.MouseButton.LeftButton)
        self.assertEqual(len(self.window.cards), 0)
        self.window.set_tab("done")
        buttons = self.window.cards[0].findChildren(QToolButton)
        QTest.mouseClick(next(b for b in buttons if b.accessibleName().startswith("Sil")), Qt.MouseButton.LeftButton)
        self.window.set_tab("trash")
        QTest.mouseClick(self.window.cards[0].findChild(QToolButton), Qt.MouseButton.LeftButton)
        self.window.set_tab("done")
        self.assertEqual(len(self.window.cards), 1)

    def test_screen_anchor_and_always_on_top(self):
        rect = self.window.screen().availableGeometry()
        self.assertTrue(self.window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        self.assertEqual(self.window.y(), rect.top() + 16)
        self.assertLessEqual(self.window.geometry().right(), rect.right())
        self.assertGreaterEqual(self.window.geometry().bottom(), rect.top())

    def test_edit_form_preserves_literal_text_and_removes_deadline(self):
        self.store.save("<b>Başlık</b>", deadline=datetime.now() + timedelta(days=2), has_time=True)
        dialog = TaskDialog(self.window, self.store.all()[0])
        self.assertTrue(dialog.use_date.isChecked())
        self.assertTrue(dialog.use_time.isChecked())
        dialog.use_date.setChecked(False)
        dialog.use_time.setChecked(False)
        self.assertIsNone(dialog.values()["deadline"])
        self.assertEqual(dialog.values()["title"], "<b>Başlık</b>")
        dialog.deleteLater()

    def test_natural_date_requires_apply_and_then_sets_form_fields(self):
        dialog = TaskDialog(self.window)
        dialog.title.setText("Yarın 18.00 raporu gönder")
        self.assertIsNone(dialog.values()["deadline"])
        dialog.apply_suggestion()
        values = dialog.values()
        self.assertEqual(values["title"], "raporu gönder")
        self.assertEqual(values["deadline"].date(), date.today() + timedelta(days=1))
        self.assertEqual(values["deadline"].hour, 18)
        dialog.deleteLater()

    def test_today_selection_resets_by_date_and_someday_is_separate(self):
        identity = self.store.save("Bugünkü iş", today=True)
        self.store.save("Gelecekteki fikir", deadline=datetime(2000, 1, 1), someday=True)
        self.window.set_tab("today")
        self.assertEqual([c.task.title for c in self.window.cards], ["Bugünkü iş"])
        with self.store.db:
            self.store.db.execute("UPDATE tasks SET today=? WHERE id=?", ((date.today() - timedelta(days=1)).isoformat(), identity))
        self.window.refresh(force=True)
        self.assertEqual(self.window.cards, [])
        self.window.set_tab("someday")
        self.assertEqual([c.task.title for c in self.window.cards], ["Gelecekteki fikir"])
        self.window.set_tab("overdue")
        self.assertEqual(self.window.cards, [])

    def test_reminders_are_separate_and_notification_snoozes_without_tasks(self):
        from odak.panels import ReminderDialog
        dialog = ReminderDialog(self.window)
        self.assertFalse(dialog.save_button.isEnabled())
        dialog.title.setText("Toplantı")
        self.assertTrue(dialog.save_button.isEnabled())
        identity = self.store.save_reminder(**dialog.values())
        moment = self.store.reminders()[0].next_at
        due = self.store.due_reminders(moment)
        self.assertEqual(len(due), 1)
        self.store.snooze_reminder(identity, moment)
        self.assertEqual(self.store.all(), [])
        self.window.set_view("reminders")
        self.assertEqual(self.window.current_view, "reminders")
        self.assertEqual(self.window.page_stack.currentWidget(), self.window.reminder_panel)
        self.assertFalse(any(b.accessibleName() == "Tamamlandı işaretle" for b in self.window.reminder_panel.findChildren(QPushButton)))
        dialog.deleteLater()

    def test_focus_pause_resume_completion_and_persistence_without_session_history(self):
        from unittest.mock import Mock
        focus = self.window.focus_panel
        self.window.system_notice = Mock()
        focus.work.setValue(1)
        focus.toggle()
        self.assertTrue(focus.running)
        end = focus.end_at
        focus.tick(end + 1)
        self.assertFalse(focus.running)
        self.assertEqual(focus.phase, "break")
        self.window.system_notice.assert_called_once()
        focus.toggle()
        self.assertTrue(focus.running)
        focus.toggle()
        self.assertFalse(focus.running)
        keys = [r[0] for r in self.store.db.execute("SELECT key FROM settings")]
        self.assertEqual(sorted(keys), ["focus_preferences", "focus_session"])
        self.assertEqual(self.store.all(), [])

    def test_notification_snooze_dialog_keeps_regular_calendar(self):
        self.store.save_reminder("Toplantı", "not", [0], "14:00")
        reminder = self.store.reminders()[0]
        def snooze():
            dialog = self.app.activeModalWidget()
            button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "10 dakika sonra hatırlat")
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        QTimer.singleShot(30, snooze)
        self.window.reminder_panel.show_alert(reminder)
        updated = self.store.reminders()[0]
        self.assertEqual(updated.next_at, reminder.next_at)
        self.assertAlmostEqual((updated.snooze_at - datetime.now()).total_seconds(), 600, delta=2)
        self.assertEqual(self.store.all(), [])

    def test_large_history_is_shown_in_batches(self):
        for number in range(125):
            self.store.save(f"İş {number}")
        self.window.refresh(force=True)
        self.assertEqual(self.window.count_label.text(), "125 görev")
        self.assertEqual(len(self.window.cards), 100)
        self.window.show_more()
        self.assertEqual(len(self.window.cards), 125)


if __name__ == "__main__":
    unittest.main()
