import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

from odak.model import Store, category, make_deadline, time_label


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "tasks.sqlite3"
        self.store = Store(self.path)

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def task(self):
        return self.store.all()[0]

    def test_optional_deadline_and_persistence(self):
        identity = self.store.save("  Sunumu hazırla  ", "not")
        self.store.close()
        self.store = Store(self.path)
        task = self.task()
        self.assertEqual((task.id, task.title, task.notes, task.deadline),
                         (identity, "Sunumu hazırla", "not", None))

    def test_blank_title_rejected(self):
        with self.assertRaises(ValueError):
            self.store.save(" \n ")
        self.assertEqual(self.store.all(), [])

    def test_edit_keeps_identity_and_completion(self):
        identity = self.store.save("Eski")
        self.store.complete(identity, True)
        stamp = self.task().completed_at
        self.store.save("Yeni", "Detay", datetime(2030, 1, 1, 15), True, identity)
        task = self.task()
        self.assertEqual((task.id, task.title, task.completed_at), (identity, "Yeni", stamp))
        self.assertTrue(task.has_time)
        self.store.save("Yeni", task_id=identity)
        self.assertIsNone(self.task().deadline)

    def test_completion_can_be_reopened(self):
        identity = self.store.save("İş")
        self.store.complete(identity, True)
        self.assertEqual(category(self.task()), "done")
        self.store.complete(identity, False)
        self.assertEqual(category(self.task()), "neutral")

    def test_undo_survives_restart_and_preserves_completed_state(self):
        identity = self.store.save("İş")
        self.store.complete(identity, True)
        self.store.delete(identity, now=1000)
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(category(self.store.all(now=1599)[0]), "trash")
        self.assertTrue(self.store.restore(identity, now=1599))
        self.assertEqual(category(self.task()), "done")

    def test_undo_expires_at_exactly_ten_minutes(self):
        identity = self.store.save("İş")
        self.store.delete(identity, now=1000)
        self.assertFalse(self.store.restore(identity, now=1600))
        self.assertEqual(self.store.all(now=1600), [])

    def test_repeated_delete_does_not_extend_undo_window(self):
        identity = self.store.save("İş")
        self.store.delete(identity, now=1000)
        self.store.delete(identity, now=1400)
        self.assertEqual(self.store.all(now=1599)[0].deleted_at, 1000)
        self.assertEqual(self.store.all(now=1600), [])

    def test_deadline_boundaries(self):
        now = datetime(2030, 1, 1, 12)
        identity = self.store.save("İş")
        for seconds, expected in ((-1, "overdue"), (0, "overdue"), (1, "urgent"),
                                  (86399, "urgent"), (86400, "soon"),
                                  (259200, "soon"), (259201, "neutral")):
            with self.subTest(seconds=seconds):
                self.store.save("İş", deadline=now + timedelta(seconds=seconds), task_id=identity)
                self.assertEqual(category(self.task(), now), expected)

    def test_overdue_completed_task_stays_done(self):
        identity = self.store.save("İş", deadline=datetime(2000, 1, 1))
        self.store.complete(identity, True)
        self.assertEqual(category(self.task()), "done")

    def test_time_label(self):
        now = datetime(2030, 1, 1, 12)
        self.store.save("İş", deadline=now + timedelta(hours=1, minutes=5))
        self.assertEqual(time_label(self.task(), now), "1 sa 5 dk kaldı")


class DeadlineTests(unittest.TestCase):
    def test_no_date_or_time(self):
        self.assertIsNone(make_deadline(None, None))

    def test_date_only_means_end_of_day(self):
        self.assertEqual(make_deadline(date(2030, 4, 5), None), datetime(2030, 4, 5, 23, 59))

    def test_time_only_means_today(self):
        self.assertEqual(make_deadline(None, time(16, 30), today=date(2030, 4, 5)),
                         datetime(2030, 4, 5, 16, 30))

    def test_full_deadline(self):
        self.assertEqual(make_deadline(date(2030, 4, 5), time(10)), datetime(2030, 4, 5, 10))


if __name__ == "__main__":
    unittest.main()
