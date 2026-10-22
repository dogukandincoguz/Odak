import json
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from odak.backups import export_json, import_json
from odak.model import Store
from odak.recurrence import meeting_link, next_scheduled


class CalendarTests(unittest.TestCase):
    def test_fortnightly_rule_is_anchored_to_calendar_weeks(self):
        anchor = date(2030, 1, 7)
        self.assertEqual(next_scheduled("weekly", [0, 2], "14:00", anchor, 2,
            after=datetime(2030,1,8)), datetime(2030,1,9,14))
        self.assertEqual(next_scheduled("weekly", [0], "14:00", anchor, 2,
            after=datetime(2030,1,8)), datetime(2030,1,21,14))

    def test_monthly_day_skips_absent_dates_and_last_day_handles_leap_year(self):
        self.assertEqual(next_scheduled("monthly_day", [], "09:00", date(2030,1,1), month_day=31,
            after=datetime(2030,1,31,9)), datetime(2030,3,31,9))
        self.assertEqual(next_scheduled("monthly_day", [], "09:00", date(2028,1,1), month_day=0,
            after=datetime(2028,2,1)), datetime(2028,2,29,9))
        self.assertEqual(next_scheduled("monthly_day", [], "09:00", date(2030,1,1), 2, month_day=15,
            after=datetime(2030,1,15,9)), datetime(2030,3,15,9))

    def test_first_and_last_weekdays_in_month(self):
        self.assertEqual(next_scheduled("monthly_weekday", [], "12:00", date(2030,1,1), ordinal=-1, month_weekday=4,
            after=datetime(2030,1,1)), datetime(2030,1,25,12))
        self.assertEqual(next_scheduled("monthly_weekday", [], "12:00", date(2030,1,1), ordinal=1, month_weekday=0,
            after=datetime(2030,1,1)), datetime(2030,1,7,12))

    def test_once_and_invalid_rules_and_links(self):
        self.assertIsNone(next_scheduled("once", [], "09:00", date(2030,1,1), after=datetime(2030,1,2)))
        for kwargs in (dict(interval=0),dict(interval=True),dict(month_day=32),dict(ordinal=5),dict(month_weekday=7)):
            with self.assertRaises(ValueError):
                next_scheduled("weekly", [0], "09:00", date(2030,1,1), **kwargs)
        for link in ("file:///C:/secret", "javascript:alert(1)", "https://", "https://example.com/a b"):
            with self.assertRaises(ValueError):
                meeting_link(link)
        self.assertEqual(meeting_link(" https://meet.example.com/abc "), "https://meet.example.com/abc")


class ExpansionStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)/"tasks.sqlite3"
        self.store = Store(self.path)
        self.now = datetime(2030,1,7,13)

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_early_notice_once_across_restart_pause_and_event_time(self):
        identity = self.store.save_reminder("Toplantı", "", [0], "14:00", now=self.now, lead_minutes=10)
        self.assertEqual(self.store.due_reminders(self.now.replace(minute=49)), [])
        self.assertEqual(len(self.store.due_reminders(self.now.replace(minute=50))), 1)
        self.assertEqual(self.store.reminders()[0].next_at, self.now.replace(hour=14))
        self.store.close()
        self.store = Store(self.path)
        self.store.pause_reminder(identity, True, self.now.replace(minute=51))
        self.store.pause_reminder(identity, False, self.now.replace(minute=52))
        self.assertEqual(self.store.due_reminders(self.now.replace(minute=53)), [])
        self.assertEqual(self.store.due_reminders(self.now.replace(hour=14)), [])
        self.assertEqual(self.store.reminders()[0].next_at, datetime(2030,1,14,14))
        self.assertEqual(self.store.all(), [])

    def test_once_snoozes_then_cleans_up_without_history(self):
        identity = self.store.save_reminder("Kargoyu ara", "", [], "14:00", now=self.now,
            kind="once", anchor_date=self.now.date())
        moment = self.now.replace(hour=14)
        self.assertEqual(len(self.store.due_reminders(moment)), 1)
        self.assertEqual(self.store.due_reminders(moment), [])
        self.store.snooze_reminder(identity, moment+timedelta(minutes=2))
        self.assertEqual(self.store.due_reminders(moment+timedelta(minutes=11)), [])
        self.assertEqual(len(self.store.due_reminders(moment+timedelta(minutes=12))), 1)
        self.store.purge((moment+timedelta(hours=24,minutes=11)).timestamp())
        self.assertEqual(len(self.store.reminders()), 1)
        self.store.purge((moment+timedelta(hours=24,minutes=12)).timestamp())
        self.assertEqual(self.store.reminders(), [])
        self.assertEqual(self.store.all(), [])

    def test_missed_once_is_discarded_without_notification(self):
        self.store.save_reminder("Eski", "", [], "14:00", now=self.now, kind="once", anchor_date=self.now.date())
        self.assertEqual(self.store.due_reminders(self.now+timedelta(days=3)), [])
        self.assertEqual(self.store.reminders(), [])

    def test_new_nearby_event_with_past_lead_time_notifies_immediately(self):
        self.store.save_reminder("Yaklaşan toplantı", "", [], "14:00", now=self.now.replace(minute=50),
            kind="once", anchor_date=self.now.date(), lead_minutes=30)
        self.assertEqual(len(self.store.due_reminders(self.now.replace(minute=50))), 1)
        self.assertEqual(self.store.due_reminders(self.now.replace(minute=51)), [])

    def test_once_can_be_edited_after_delivery_without_renotifying(self):
        identity = self.store.save_reminder("Bir kez", "", [], "14:00", now=self.now, kind="once", anchor_date=self.now.date())
        self.store.due_reminders(self.now.replace(hour=14))
        self.store.save_reminder("Yeni başlık", "not", [], "14:00", identity, self.now.replace(hour=15),
            kind="once", anchor_date=self.now.date(), link="https://example.com/meet")
        self.assertEqual(self.store.due_reminders(self.now.replace(hour=15)), [])
        self.assertEqual(self.store.reminders()[0].link, "https://example.com/meet")
        with self.assertRaises(ValueError):
            self.store.save_reminder("Geçmiş", "", [], "12:00", now=self.now, kind="once", anchor_date=self.now.date())

    def test_monthly_skip_pause_and_notes_preserve_calendar(self):
        identity = self.store.save_reminder("Ay sonu", "", [], "14:00", now=self.now,
            kind="monthly_weekday", ordinal=-1, month_weekday=4, lead_minutes=30)
        self.assertEqual(self.store.reminders()[0].next_at, datetime(2030,1,25,14))
        self.store.skip_reminder(identity, self.now)
        self.assertEqual(self.store.reminders()[0].next_at, datetime(2030,2,22,14))
        self.store.pause_reminder(identity, True, self.now)
        self.store.pause_reminder(identity, False, self.now)
        self.assertEqual(self.store.reminders()[0].next_at, datetime(2030,2,22,14))

    def test_templates_have_independent_steps_and_never_generate_tasks(self):
        template = self.store.save_template("Sunum", "Sunumu hazırla", "not", ["Veriler", "Prova"])
        self.assertEqual(self.store.all(), [])
        source = self.store.templates()[0]
        a = self.store.save(source.title, source.notes, steps=list(source.steps))
        b = self.store.save(source.title, source.notes, steps=list(source.steps))
        self.store.set_step(self.store.all()[0].steps[0].id, True)
        self.assertNotEqual(self.store.all()[0].steps[0].id, self.store.all()[1].steps[0].id)
        self.store.save_template("Yeni ad", "Yeni başlık", steps=["Tek adım"], template_id=template)
        self.assertEqual(len(self.store.templates()), 1)
        self.store.delete_template(template)
        self.assertEqual(self.store.templates(), [])
        self.assertEqual({t.id for t in self.store.all()}, {a,b})

    def test_today_order_survives_edit_restart_and_rejects_stale_list(self):
        a = self.store.save("A", today=True, deadline=self.now)
        b = self.store.save("B", today=True)
        c = self.store.save("C", today=True)
        self.store.reorder_today([c,a,b])
        self.store.save("Düzenlendi", task_id=a, today=True, deadline=self.now)
        self.store.close()
        self.store = Store(self.path)
        tasks = sorted(self.store.all(),key=lambda t:t.today_position)
        self.assertEqual([t.id for t in tasks],[c,a,b])
        self.assertEqual(tasks[1].deadline, self.now)
        for identities in ([c,a,a], [c,a]):
            with self.assertRaises(ValueError):
                self.store.reorder_today(identities)
        d = self.store.save("D")
        self.store.set_today(d, True)
        self.assertEqual(max(self.store.all(),key=lambda t:t.today_position).id,d)

    def test_extended_json_roundtrip_and_bad_rule_import_are_atomic(self):
        a = self.store.save("A", today=True)
        b = self.store.save("B", today=True)
        self.store.reorder_today([b,a])
        self.store.save_template("Hazırlık", "Hazırlan", steps=["Kontrol"])
        self.store.save_reminder("Toplantı", "", [0], "14:00", now=self.now,
            interval=2, lead_minutes=10, link="https://example.com/meet")
        path = self.path.parent/"export.json"
        export_json(self.store,path)
        other = Store(self.path.parent/"other.sqlite3")
        try:
            self.assertEqual(import_json(other,path),4)
            self.assertEqual(import_json(other,path),0)
            self.assertEqual(other.templates()[0].steps,("Kontrol",))
            reminder = other.reminders()[0]
            self.assertEqual((reminder.interval,reminder.lead_minutes,reminder.link),(2,10,"https://example.com/meet"))
            self.assertEqual([t.id for t in sorted(other.all(),key=lambda t:t.today_position)],[b,a])
            contents = json.loads(path.read_text(encoding="utf-8"))
            contents["reminders"][0]["interval"] = 0
            contents["tasks"][0]["id"] = "a"*32
            path.write_text(json.dumps(contents),encoding="utf-8")
            with self.assertRaises(ValueError):
                import_json(other,path)
            self.assertEqual(len(other.all()),2)
        finally:
            other.close()

    def test_old_weekly_schema_migrates_schedule_without_losing_records(self):
        path = self.path.parent/"legacy.sqlite3"
        connection = sqlite3.connect(path)
        connection.executescript("""CREATE TABLE reminders(id TEXT PRIMARY KEY,title TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '',
            weekdays TEXT NOT NULL,clock TEXT NOT NULL,paused INTEGER NOT NULL DEFAULT 0,next_at TEXT NOT NULL,
            snooze_at TEXT,deleted_at REAL,created_at REAL NOT NULL);
            INSERT INTO reminders VALUES('old','Toplantı','not','[0]','14:00',0,'2030-01-07T14:00:00',NULL,NULL,1);""")
        connection.close()
        old = Store(path)
        try:
            old.ensure_schema()
            reminder = old.reminders()[0]
            self.assertEqual((reminder.id,reminder.anchor_date,reminder.interval),("old",date(2030,1,7),1))
            self.assertEqual(len(old.due_reminders(datetime(2030,1,7,14))),1)
        finally:
            old.close()
