import json
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from odak.backups import Backups, export_json, import_json
from odak.model import Store, category
from odak.schedule import next_occurrence, suggest_date


class ScheduleTests(unittest.TestCase):
    def test_turkish_date_suggestion_is_explicit_and_preserves_task_text(self):
        now = datetime(2030, 1, 7, 10)  # Pazartesi
        examples = (("Yarın 18.00 raporu gönder", "raporu gönder", datetime(2030, 1, 8, 18), True),
                    ("Cuma kitap al", "kitap al", datetime(2030, 1, 11, 23, 59), False),
                    ("3 gün sonra taslağı bitir", "taslağı bitir", datetime(2030, 1, 10, 23, 59), False),
                    ("25.10.2030 saat 09:30 sunum", "sunum", datetime(2030, 10, 25, 9, 30), True),
                    ("YARIN İŞİ BİTİR", "İŞİ BİTİR", datetime(2030, 1, 8, 23, 59), False))
        for text, title, deadline, has_time in examples:
            with self.subTest(text=text):
                parsed = suggest_date(text, now)
                self.assertEqual((parsed.title, parsed.deadline, parsed.has_time), (title, deadline, has_time))
        self.assertIsNone(suggest_date("Raporu yaz", now))
        self.assertIsNone(suggest_date("31.02.2030 rapor", now))
        self.assertIsNone(suggest_date("yarın", now))

    def test_weekly_schedule_stays_on_calendar(self):
        monday = datetime(2030, 1, 7, 14)
        self.assertEqual(next_occurrence([0], "14:00", monday), datetime(2030, 1, 14, 14))
        self.assertEqual(next_occurrence([0, 3], "14:00", monday), datetime(2030, 1, 10, 14))
        self.assertEqual(next_occurrence(list(range(5)), "09:00", datetime(2030, 1, 11, 17)), datetime(2030, 1, 14, 9))
        with self.assertRaises(ValueError):
            next_occurrence([], "09:00", monday)


class PlanningStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "odak.sqlite3"
        self.store = Store(self.path)

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_steps_survive_edit_and_reorder_then_delete_cascades(self):
        identity = self.store.save("Sunum", steps=["Veriler", "Slaytlar"])
        step = self.store.all()[0].steps[0]
        self.store.set_step(step.id, True)
        self.store.save("Sunum", steps=["Slaytlar", "Veriler", "Prova"], task_id=identity)
        steps = self.store.all()[0].steps
        self.assertEqual((steps[1].id, steps[1].done), (step.id, True))
        self.store.delete(identity, now=1000)
        self.store.purge(now=1600)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM steps").fetchone()[0], 0)

    def test_today_and_someday_are_task_flags_without_daily_rows(self):
        identity = self.store.save("İş", deadline=datetime(2000, 1, 1), today=True)
        self.assertEqual(self.store.all()[0].today, date.today().isoformat())
        self.store.set_someday(identity, True)
        task = self.store.all()[0]
        self.assertIsNone(task.today)
        self.assertEqual(category(task), "someday")
        self.store.set_today(identity, True)
        self.assertEqual(category(self.store.all()[0]), "overdue")
        self.assertEqual(len(self.store.all()), 1)

    def reminder(self):
        return self.store.reminders()[0]

    def test_recurrence_notifies_once_and_never_generates_tasks_or_history(self):
        now = datetime(2030, 1, 7, 13)
        identity = self.store.save_reminder("Toplantı", "", [0], "14:00", now=now)
        for week in range(52):
            moment = datetime(2030, 1, 7, 14) + timedelta(weeks=week)
            self.assertEqual(len(self.store.due_reminders(moment)), 1)
            self.assertEqual(self.store.due_reminders(moment), [])
        self.assertEqual(self.reminder().id, identity)
        self.assertEqual(len(self.store.reminders()), 1)
        self.assertEqual(self.store.all(), [])

    def test_pause_skip_and_snooze_do_not_shift_weekly_calendar(self):
        now = datetime(2030, 1, 7, 13)
        identity = self.store.save_reminder("Toplantı", "", [0], "14:00", now=now)
        self.store.skip_reminder(identity, now)
        self.assertEqual(self.reminder().next_at, datetime(2030, 1, 14, 14))
        self.store.snooze_reminder(identity, now)
        self.assertEqual(self.reminder().snooze_at, now + timedelta(minutes=10))
        self.assertEqual(len(self.store.due_reminders(now + timedelta(minutes=10))), 1)
        self.assertEqual(self.reminder().next_at, datetime(2030, 1, 14, 14))
        self.assertIsNone(self.reminder().snooze_at)
        self.store.pause_reminder(identity, True, now)
        self.assertEqual(self.store.due_reminders(datetime(2030, 1, 7, 14)), [])
        self.store.pause_reminder(identity, False, now)
        self.assertFalse(self.reminder().paused)

    def test_missed_reminders_are_advanced_without_old_notification_flood(self):
        self.store.save_reminder("Toplantı", "", [0], "14:00", now=datetime(2030, 1, 7, 13))
        self.assertEqual(self.store.due_reminders(datetime(2030, 2, 1, 12)), [])
        self.assertGreater(self.reminder().next_at, datetime(2030, 2, 1, 12))

    def test_editing_reminder_notes_preserves_skipped_date_and_snooze(self):
        now = datetime(2030, 1, 7, 13)
        identity = self.store.save_reminder("Toplantı", "", [0], "14:00", now=now)
        self.store.skip_reminder(identity, now)
        self.store.snooze_reminder(identity, now)
        before = self.reminder()
        self.store.save_reminder("Yeni başlık", "Yeni not", [0], "14:00", identity, now)
        after = self.reminder()
        self.assertEqual((before.next_at, before.snooze_at), (after.next_at, after.snooze_at))

    def test_reminder_undo_has_same_ten_minute_window(self):
        identity = self.store.save_reminder("Toplantı", "", [0], "14:00")
        self.store.delete_reminder(identity)
        self.assertIsNotNone(self.reminder().deleted_at)
        self.assertTrue(self.store.restore_reminder(identity))
        self.assertIsNone(self.reminder().deleted_at)

    def test_json_roundtrip_merge_and_invalid_import_are_atomic(self):
        identity = self.store.save("Sunum", steps=["Veriler"], today=True)
        self.store.save_reminder("Toplantı", "", [0], "14:00")
        path = self.path.parent / "export.json"
        export_json(self.store, path)
        other = Store(self.path.parent / "other.sqlite3")
        try:
            self.assertEqual(import_json(other, path), 2)
            self.assertEqual(other.all()[0].steps[0].title, "Veriler")
            other.save("Yerel değişiklik", task_id=identity)
            self.assertEqual(import_json(other, path), 0)
            self.assertEqual(other.all()[0].title, "Yerel değişiklik")
            contents = json.loads(path.read_text(encoding="utf-8"))
            contents["tasks"][0]["created_at"] = "invalid"
            path.write_text(json.dumps(contents), encoding="utf-8")
            with self.assertRaises(ValueError):
                import_json(other, path)
            self.assertEqual(other.all()[0].title, "Yerel değişiklik")
        finally:
            other.close()

    def test_snapshots_keep_three_and_oldest_can_be_restored(self):
        self.store.save("Eski")
        backups = Backups(self.store)
        first = backups.snapshot()
        self.store.save("Yeni")
        backups.snapshot()
        backups.snapshot()
        backups.restore(first)
        self.assertEqual([task.title for task in self.store.all()], ["Eski"])
        self.assertEqual(len(list(backups.directory.glob("*.sqlite3"))), 3)
        self.assertIsNone(backups.snapshot(daily=True))


class MigrationTests(unittest.TestCase):
    def test_existing_database_is_migrated_without_losing_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.sqlite3"
            connection = sqlite3.connect(path)
            connection.executescript("""CREATE TABLE tasks (id TEXT PRIMARY KEY,title TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '',deadline TEXT,has_time INTEGER NOT NULL DEFAULT 0,completed_at REAL,deleted_at REAL,created_at REAL NOT NULL); INSERT INTO tasks VALUES ('old','Önceden kaydedilmiş görev','not',NULL,0,NULL,NULL,1);""")
            connection.close()
            store = Store(path)
            try:
                task = store.all()[0]
                self.assertEqual((task.id, task.title, task.notes), ("old", "Önceden kaydedilmiş görev", "not"))
                self.assertFalse(task.someday)
                self.assertIsNone(task.today)
                self.assertEqual(task.steps, ())
                store.ensure_schema()
                self.assertEqual(len(store.all()), 1)
            finally:
                store.close()
