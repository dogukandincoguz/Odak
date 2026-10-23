from __future__ import annotations

import math
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, time as datetime_time
from pathlib import Path

from .recurrence import next_scheduled, meeting_link, LEADS

UNDO_SECONDS = 10 * 60
ORDERED_LISTS = ("active", "overdue", "someday", "done", "trash")


@dataclass(frozen=True, slots=True, weakref_slot=True)
class Step:
    id: str
    title: str
    done: bool


@dataclass(frozen=True, slots=True, weakref_slot=True)
class Task:
    id: str
    title: str
    notes: str
    deadline: datetime | None
    has_time: bool
    completed_at: float | None
    deleted_at: float | None
    created_at: float
    today: str | None = None
    someday: bool = False
    steps: tuple[Step, ...] = ()
    today_position: int | None = None


@dataclass(frozen=True, slots=True, weakref_slot=True)
class Reminder:
    id: str
    title: str
    notes: str
    weekdays: tuple[int, ...]
    clock: str
    paused: bool
    next_at: datetime
    snooze_at: datetime | None
    deleted_at: float | None
    created_at: float
    kind: str = "weekly"
    interval: int = 1
    anchor_date: date = date(1970, 1, 1)
    month_day: int = 1
    ordinal: int = -1
    month_weekday: int = 4
    lead_minutes: int = 0
    link: str = ""
    notified_for: str | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True, weakref_slot=True)
class Template:
    id: str
    name: str
    title: str
    notes: str
    steps: tuple[str, ...]


def make_deadline(day: date | None, clock: datetime_time | None,
                  today: date | None = None) -> datetime | None:
    if day is None and clock is None:
        return None
    return datetime.combine(day or today or date.today(), clock or datetime_time(23, 59))


def category(task: Task, now: datetime | None = None) -> str:
    if task.deleted_at is not None:
        return "trash"
    if task.completed_at is not None:
        return "done"
    if task.someday:
        return "someday"
    if task.deadline is None:
        return "neutral"
    seconds = (task.deadline - (now or datetime.now())).total_seconds()
    if seconds <= 0:
        return "overdue"
    if seconds < 86400:
        return "urgent"
    if seconds <= 3 * 86400:
        return "soon"
    return "neutral"


def time_label(task: Task, now: datetime | None = None) -> str:
    if task.deadline is None:
        return "Deadline yok"
    seconds = (task.deadline - (now or datetime.now())).total_seconds()
    past = seconds <= 0
    minutes = max(1, math.ceil(abs(seconds) / 60))
    if minutes < 60:
        text = f"{minutes} dk"
    elif minutes < 1440:
        hours, mins = divmod(minutes, 60)
        text = f"{hours} sa" + (f" {mins} dk" if mins else "")
    else:
        days, hours = divmod(minutes // 60, 24)
        text = f"{days} gün" + (f" {hours} sa" if hours else "")
    return text + (" geçti" if past else " kaldı")


class Store:
    def __init__(self, path: Path):
        self.path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.ensure_schema()

    def ensure_schema(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL CHECK(length(trim(title)) > 0),
                notes TEXT NOT NULL DEFAULT '',
                deadline TEXT,
                has_time INTEGER NOT NULL DEFAULT 0,
                completed_at REAL,
                deleted_at REAL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS tasks_deleted ON tasks(deleted_at);
            CREATE TABLE IF NOT EXISTS task_order (
                scope TEXT NOT NULL, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                position INTEGER NOT NULL CHECK(position>=0), PRIMARY KEY(scope, task_id)
            );
            CREATE INDEX IF NOT EXISTS task_order_task ON task_order(task_id);
            CREATE TABLE IF NOT EXISTS steps (
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, position INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS steps_task ON steps(task_id);
            CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
                weekdays TEXT NOT NULL, clock TEXT NOT NULL, paused INTEGER NOT NULL DEFAULT 0,
                next_at TEXT NOT NULL, snooze_at TEXT, deleted_at REAL, created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS templates (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, title TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '', steps TEXT NOT NULL DEFAULT '[]', created_at REAL NOT NULL
            );
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(tasks)")}
        with self.db:
            if "today" not in columns:
                self.db.execute("ALTER TABLE tasks ADD COLUMN today TEXT")
            if "someday" not in columns:
                self.db.execute("ALTER TABLE tasks ADD COLUMN someday INTEGER NOT NULL DEFAULT 0")
            if "today_position" not in columns:
                self.db.execute("ALTER TABLE tasks ADD COLUMN today_position INTEGER")
            reminder_columns = {row[1] for row in self.db.execute("PRAGMA table_info(reminders)")}
            for name, definition in {
                "kind": "TEXT NOT NULL DEFAULT 'weekly'", "interval": "INTEGER NOT NULL DEFAULT 1",
                "anchor_date": "TEXT NOT NULL DEFAULT '1970-01-01'",
                "month_day": "INTEGER NOT NULL DEFAULT 1", "ordinal": "INTEGER NOT NULL DEFAULT -1",
                "month_weekday": "INTEGER NOT NULL DEFAULT 4", "lead_minutes": "INTEGER NOT NULL DEFAULT 0",
                "link": "TEXT NOT NULL DEFAULT ''", "notified_for": "TEXT", "expires_at": "TEXT",
            }.items():
                if name not in reminder_columns:
                    self.db.execute(f"ALTER TABLE reminders ADD COLUMN {name} {definition}")
            if "anchor_date" not in reminder_columns:
                self.db.execute("UPDATE reminders SET anchor_date=substr(next_at,1,10)")

    def save(self, title: str, notes: str = "", deadline: datetime | None = None,
             has_time: bool = False, task_id: str | None = None,
             steps: list[str] | None = None, someday: bool | None = None,
             today: bool | None = None) -> str:
        title = title.strip()
        if not title:
            raise ValueError("Görev başlığı boş olamaz.")
        if len(title) > 180:
            raise ValueError("Görev başlığı en fazla 180 karakter olabilir.")
        if steps is not None and any(len(s.strip()) > 180 for s in steps):
            raise ValueError("Her alt adım en fazla 180 karakter olabilir.")
        values = (title, notes.strip(), deadline.isoformat() if deadline else None,
                  int(has_time and deadline is not None))
        with self.db:
            if task_id:
                self.db.execute(
                    "UPDATE tasks SET title=?,notes=?,deadline=?,has_time=? WHERE id=? AND deleted_at IS NULL",
                    (*values, task_id))
            else:
                task_id = uuid.uuid4().hex
                self.db.execute(
                    "INSERT INTO tasks (title,notes,deadline,has_time,id,created_at) VALUES (?,?,?,?,?,?)",
                    (*values, task_id, time.time()))
            if someday is not None:
                self.db.execute("UPDATE tasks SET someday=?,today=CASE WHEN ? THEN NULL ELSE today END WHERE id=?",
                                (int(someday), int(someday), task_id))
            if today is not None:
                self._today_position(task_id, today)
                self.db.execute("UPDATE tasks SET today=CASE WHEN someday=0 THEN ? ELSE NULL END WHERE id=?",
                                (date.today().isoformat() if today else None, task_id))
            if steps is not None:
                old_steps = list(self.db.execute("SELECT * FROM steps WHERE task_id=? ORDER BY position", (task_id,)))
                self.db.execute("DELETE FROM steps WHERE task_id=?", (task_id,))
                for position, step_title in enumerate(s.strip() for s in steps if s.strip()):
                    match = next((s for s in old_steps if s["title"] == step_title), None)
                    identity = match["id"] if match else uuid.uuid4().hex
                    if match:
                        old_steps.remove(match)
                    self.db.execute("INSERT INTO steps VALUES (?,?,?,?,?)",
                        (identity, task_id, step_title, match["done"] if match else 0, position))
        return task_id

    def all(self, now: float | None = None) -> list[Task]:
        self.purge(now)
        rows = self.db.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        steps: dict[str, list[Step]] = {}
        for r in self.db.execute("SELECT * FROM steps ORDER BY position"):
            steps.setdefault(r["task_id"], []).append(Step(r["id"], r["title"], bool(r["done"])))
        return [Task(id=r["id"], title=r["title"], notes=r["notes"],
                     deadline=datetime.fromisoformat(r["deadline"]) if r["deadline"] else None,
                     has_time=bool(r["has_time"]), completed_at=r["completed_at"],
                     deleted_at=r["deleted_at"], created_at=r["created_at"],
                     today=r["today"], someday=bool(r["someday"]),
                     steps=tuple(steps.get(r["id"], ())), today_position=r["today_position"]) for r in rows]

    def _today_position(self, task_id, selected):
        if selected:
            self.db.execute("""UPDATE tasks SET today_position=(SELECT COALESCE(MAX(today_position),-1)+1
                FROM tasks WHERE today=?) WHERE id=? AND (today IS NULL OR today<>?)""",
                (date.today().isoformat(), task_id, date.today().isoformat()))

    def set_today(self, task_id: str, selected: bool):
        with self.db:
            self._today_position(task_id, selected)
            self.db.execute("UPDATE tasks SET today=?,someday=CASE WHEN ? THEN 0 ELSE someday END WHERE id=?",
                            (date.today().isoformat() if selected else None, int(selected), task_id))

    def reorder_today(self, identities: list[str]):
        selected = {r[0] for r in self.db.execute("""SELECT id FROM tasks WHERE today=? AND someday=0
            AND completed_at IS NULL AND deleted_at IS NULL""", (date.today().isoformat(),))}
        if len(identities) != len(set(identities)) or set(identities) != selected:
            raise ValueError("Bugün listesi değişti; sıralamayı yeniden dene.")
        with self.db:
            self.db.executemany("UPDATE tasks SET today_position=? WHERE id=?", enumerate(identities))

    def task_positions(self, scope: str) -> dict[str, int]:
        return {row["task_id"]: row["position"] for row in self.db.execute(
            "SELECT task_id,position FROM task_order WHERE scope=?", (scope,))}

    def reorder_tasks(self, scope: str, identities: list[str]):
        if scope == "today":
            return self.reorder_today(identities)
        if scope not in ORDERED_LISTS:
            raise ValueError("Geçersiz görev listesi.")
        selected = set()
        now = datetime.now()
        for task in self.all(now.timestamp()):
            kind = category(task, now)
            task_scope = kind if kind in ("overdue", "done", "trash", "someday") else "active"
            if task_scope == scope:
                selected.add(task.id)
        if len(identities) != len(set(identities)) or set(identities) != selected:
            raise ValueError("Görev listesi değişti; sıralamayı yeniden dene.")
        with self.db:
            self.db.execute("DELETE FROM task_order WHERE scope=?", (scope,))
            self.db.executemany("INSERT INTO task_order(scope,task_id,position) VALUES (?,?,?)",
                                ((scope, identity, position) for position, identity in enumerate(identities)))

    def templates(self) -> list[Template]:
        return [Template(r["id"], r["name"], r["title"], r["notes"], tuple(json.loads(r["steps"])))
                for r in self.db.execute("SELECT * FROM templates ORDER BY name COLLATE NOCASE, id")]

    def save_template(self, name: str, title: str, notes="", steps=None, template_id=None) -> str:
        steps = [s.strip() for s in (steps or []) if s.strip()]
        if not name.strip() or len(name.strip()) > 80 or not title.strip() or len(title.strip()) > 180:
            raise ValueError("Şablon adı 1–80, görev başlığı 1–180 karakter olmalı.")
        if any(len(s) > 180 for s in steps):
            raise ValueError("Her alt adım en fazla 180 karakter olabilir.")
        identity = template_id or uuid.uuid4().hex
        with self.db:
            self.db.execute("""INSERT INTO templates VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,title=excluded.title,notes=excluded.notes,steps=excluded.steps""",
                (identity, name.strip(), title.strip(), notes.strip(), json.dumps(steps, ensure_ascii=False), time.time()))
        return identity

    def delete_template(self, identity: str):
        with self.db:
            self.db.execute("DELETE FROM templates WHERE id=?", (identity,))

    def set_someday(self, task_id: str, selected: bool):
        with self.db:
            self.db.execute("UPDATE tasks SET someday=?,today=NULL WHERE id=?", (int(selected), task_id))

    def set_step(self, step_id: str, done: bool):
        with self.db:
            self.db.execute("UPDATE steps SET done=? WHERE id=?", (int(done), step_id))

    def complete(self, task_id: str, completed: bool):
        with self.db:
            self.db.execute("UPDATE tasks SET completed_at=? WHERE id=? AND deleted_at IS NULL",
                            (time.time() if completed else None, task_id))

    def delete(self, task_id: str, now: float | None = None):
        with self.db:
            self.db.execute("UPDATE tasks SET deleted_at=? WHERE id=? AND deleted_at IS NULL",
                            (time.time() if now is None else now, task_id))

    def restore(self, task_id: str, now: float | None = None) -> bool:
        stamp = time.time() if now is None else now
        with self.db:
            result = self.db.execute(
                "UPDATE tasks SET deleted_at=NULL WHERE id=? AND deleted_at>?",
                (task_id, stamp - UNDO_SECONDS))
        return result.rowcount > 0

    def purge(self, now: float | None = None):
        stamp = time.time() if now is None else now
        with self.db:
            self.db.execute("DELETE FROM tasks WHERE deleted_at IS NOT NULL AND deleted_at<=?",
                            (stamp - UNDO_SECONDS,))
            self.db.execute("DELETE FROM reminders WHERE deleted_at IS NOT NULL AND deleted_at<=?",
                            (stamp - UNDO_SECONDS,))
            self.db.execute("DELETE FROM reminders WHERE kind='once' AND deleted_at IS NULL AND expires_at<=?",
                            (datetime.fromtimestamp(stamp).isoformat(),))

    def save_reminder(self, title: str, notes: str, weekdays: list[int], clock: str,
                      reminder_id: str | None = None, now: datetime | None = None,
                      *, kind="weekly", interval=1, anchor_date=None, month_day=1,
                      ordinal=-1, month_weekday=4, lead_minutes=0, link="") -> str:
        if not title.strip() or len(title.strip()) > 180:
            raise ValueError("Hatırlatma başlığı 1–180 karakter olmalı.")
        if type(lead_minutes) is not int or lead_minutes not in LEADS:
            raise ValueError("Bildirim zamanı geçersiz.")
        link = meeting_link(link)
        now = now or datetime.now()
        old = self.db.execute("SELECT * FROM reminders WHERE id=? AND deleted_at IS NULL", (reminder_id,)).fetchone() if reminder_id else None
        if reminder_id and old is None:
            raise ValueError("Bu hatırlatma artık bulunamıyor.")
        anchor = anchor_date or (date.fromisoformat(old["anchor_date"]) if old else now.date())
        if isinstance(anchor, str):
            anchor = date.fromisoformat(anchor)
        days = sorted(set(weekdays)) if kind == "weekly" else []
        from .recurrence import validate_rule
        validate_rule(kind, days, clock, anchor, interval, month_day, ordinal, month_weekday)
        rule = dict(weekdays=json.dumps(days), clock=clock, kind=kind, interval=interval,
                    anchor_date=anchor.isoformat(), month_day=month_day, ordinal=ordinal,
                    month_weekday=month_weekday, lead_minutes=lead_minutes)
        unchanged = old and all(old[k] == v for k, v in rule.items())
        next_at = old["next_at"] if unchanged else next_scheduled(kind, days, clock, anchor, interval, month_day, ordinal, month_weekday, now)
        if next_at is None:
            raise ValueError("Tek seferlik hatırlatma için gelecekte bir tarih ve saat seç.")
        if isinstance(next_at, datetime):
            next_at = next_at.isoformat()
        with self.db:
            identity = reminder_id or uuid.uuid4().hex
            values = dict(title=title.strip(), notes=notes.strip(), link=link, **rule)
            if old:
                if not unchanged:
                    values.update(next_at=next_at, snooze_at=None, notified_for=None, expires_at=None)
                assignments = ",".join(f"{k}=?" for k in values)
                self.db.execute(f"UPDATE reminders SET {assignments} WHERE id=?", (*values.values(), identity))
            else:
                values.update(id=identity, next_at=next_at, created_at=time.time())
                columns = ",".join(values)
                self.db.execute(f"INSERT INTO reminders ({columns}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
        return identity

    def reminders(self, now: float | None = None) -> list[Reminder]:
        self.purge(now)
        return [Reminder(
            id=r["id"], title=r["title"], notes=r["notes"], weekdays=tuple(json.loads(r["weekdays"])),
            clock=r["clock"], paused=bool(r["paused"]), next_at=datetime.fromisoformat(r["next_at"]),
            snooze_at=datetime.fromisoformat(r["snooze_at"]) if r["snooze_at"] else None,
            deleted_at=r["deleted_at"], created_at=r["created_at"], kind=r["kind"], interval=r["interval"],
            anchor_date=date.fromisoformat(r["anchor_date"]), month_day=r["month_day"], ordinal=r["ordinal"],
            month_weekday=r["month_weekday"], lead_minutes=r["lead_minutes"], link=r["link"],
            notified_for=r["notified_for"], expires_at=datetime.fromisoformat(r["expires_at"]) if r["expires_at"] else None)
            for r in self.db.execute("SELECT * FROM reminders ORDER BY next_at")]

    @staticmethod
    def _next(reminder: Reminder, after: datetime):
        return next_scheduled(reminder.kind, reminder.weekdays, reminder.clock, reminder.anchor_date,
            reminder.interval, reminder.month_day, reminder.ordinal, reminder.month_weekday, after)

    def pause_reminder(self, reminder_id: str, paused: bool, now: datetime | None = None):
        reminder = next(r for r in self.reminders() if r.id == reminder_id)
        if reminder.kind == "once":
            raise ValueError("Tek seferlik hatırlatmanın tarihini düzenleyebilirsin.")
        moment = now or datetime.now()
        next_at = reminder.next_at if paused or reminder.next_at > moment else self._next(reminder, moment)
        notified_for = reminder.notified_for if next_at == reminder.next_at else None
        with self.db:
            self.db.execute("UPDATE reminders SET paused=?,next_at=?,snooze_at=NULL,notified_for=? WHERE id=?",
                            (int(paused), next_at.isoformat(), notified_for, reminder_id))

    def skip_reminder(self, reminder_id: str, now: datetime | None = None):
        reminder = next(r for r in self.reminders() if r.id == reminder_id)
        if reminder.kind == "once":
            raise ValueError("Tek seferlik hatırlatmalarda tekrar bulunmaz.")
        next_at = self._next(reminder, max(now or datetime.now(), reminder.next_at))
        with self.db:
            self.db.execute("UPDATE reminders SET next_at=?,snooze_at=NULL,notified_for=NULL WHERE id=?", (next_at.isoformat(), reminder_id))

    def snooze_reminder(self, reminder_id: str, now: datetime | None = None):
        reminder = next(r for r in self.reminders() if r.id == reminder_id)
        until = (now or datetime.now()) + timedelta(minutes=10)
        with self.db:
            self.db.execute("UPDATE reminders SET snooze_at=? WHERE id=? AND paused=0 AND deleted_at IS NULL",
                            (until.isoformat(), reminder_id))
            if reminder.kind == "once":
                expiry = max(reminder.next_at, until) + timedelta(hours=24)
                self.db.execute("UPDATE reminders SET expires_at=? WHERE id=?", (expiry.isoformat(), reminder_id))

    def delete_reminder(self, reminder_id: str):
        with self.db:
            self.db.execute("UPDATE reminders SET deleted_at=? WHERE id=?", (time.time(), reminder_id))

    def restore_reminder(self, reminder_id: str) -> bool:
        with self.db:
            result = self.db.execute("UPDATE reminders SET deleted_at=NULL WHERE id=? AND deleted_at>?",
                                    (reminder_id, time.time() - UNDO_SECONDS))
        return result.rowcount > 0

    def due_reminders(self, now: datetime | None = None) -> list[Reminder]:
        now = now or datetime.now()
        due = []
        for r in self.reminders(now.timestamp()):
            if r.paused or r.deleted_at is not None:
                continue
            event_key = r.next_at.isoformat()
            notice_at = r.next_at - timedelta(minutes=r.lead_minutes)
            scheduled = notice_at <= now and r.notified_for != event_key
            snoozed = r.snooze_at is not None and r.snooze_at <= now
            # Bildirim saati geçmiş olsa da yaklaşan etkinliği açılışta haber ver.
            fresh = scheduled and (now < r.next_at or (now - notice_at).total_seconds() <= 900)
            fresh |= snoozed and (now - r.snooze_at).total_seconds() <= 900
            if fresh:
                due.append(r)
            values = {}
            if scheduled:
                values["notified_for"] = event_key
                if r.kind == "once":
                    values["expires_at"] = (max(r.next_at, r.snooze_at or r.next_at) + timedelta(hours=24)).isoformat()
            if r.kind != "once" and r.next_at <= now:
                values.update(next_at=self._next(r, now).isoformat(), notified_for=None)
            if snoozed:
                values["snooze_at"] = None
            if values:
                with self.db:
                    assignments = ",".join(f"{k}=?" for k in values)
                    self.db.execute(f"UPDATE reminders SET {assignments} WHERE id=?", (*values.values(), r.id))
        self.purge(now.timestamp())
        return due

    def setting(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key: str, value):
        encoded = json.dumps(value, ensure_ascii=False)
        with self.db:
            self.db.execute("INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value WHERE settings.value<>excluded.value",
                            (key, encoded))

    def close(self):
        self.db.close()
